# ShowFeed — Cahier des charges

**Produit :** ShowFeed (Lyrionix / Valentin Guevara)  
**Statut :** V1 logicielle livrée (Pi + Fire TV + sim + régie). Features ci‑dessous = backlog à générer / implémenter.  
**Repo :** https://github.com/ValentinGuevara/showfeed  
**Pitch :** https://lyrionix.fr/showfeed/

---

## 1. Vision produit

Pipeline événementiel : **capture pro → triage local → écrans brandés live**.  
Différenciation vs murs UGC : photographe / caméraman, LAN dédié, SSD, pas de cloud obligatoire sur le chemin écran.

---

## 2. Déjà livré (V1) — ne pas refaire

| Bloc | Emplacement | Comportement |
|---|---|---|
| Inbox Samba → SSD | `pi/install/`, `watcher` | Écriture stable puis triage |
| Triage basique | `pi/showfeed/triage.py` | Ext, taille, doublon, largeur |
| Gate qualité local | `pi/showfeed/moderation.py` | Flou / expo (Pillow), **pas** de LLM |
| Filtres + burn-in | `pi/showfeed/process.py` | Contraste/netteté + titre/logo |
| Player + idle | `player.html`, config `idle_*` | Boucle playlist ; idle si vide |
| Régie | `/regie`, `ops.py` | Alertes hold/disque/inbox + forcer écran / requeue |
| Sim Master CUE | `pi/sim/` | Timeline fausse prod sur Mac |
| Fire TV | `firetv/` | WebView kiosk |

Dossiers média : `inbox/` → `approved/` \| `hold/` (+ `archive/` originaux).

---

## 3. Backlog prioritaire — Modération IA cloud + filet local + crédits

> **À implémenter (~1 semaine, génération Claude OK).**  
> Ne casse pas le chemin offline : une soirée sans uplink doit continuer à tourner.

### 3.1 Objectif

Enrichir la décision **hold vs approved** avec une **IA vision cloud** (Gemini et/ou ChatGPT Vision) quand c’est possible, avec :

1. **Fallback local** si perte de connexion / timeout / erreur API  
2. **Système de crédits** pour plafonner le coût par event / client  
3. **Visibilité régie** (crédits restants, mode cloud vs local)

### 3.2 Règle de décision (contrat unique)

```
fichier inbox (après triage basique OK)
        │
        ▼
  crédits > 0  ET  uplink OK  ET  timeout non dépassé
        │                    │
       oui                  non
        │                    │
        ▼                    ▼
  appel Vision cloud    gate local actuel
  (Gemini / OpenAI)     (moderation.py Pillow)
        │                    │
        └────────┬───────────┘
                 ▼
         hold  |  approved
                 │
                 ▼
         process (filtres + branding) si approved
```

- Même sortie qu’aujourd’hui : `TriageResult` / hold / approved.  
- `/regie` reste valide (Forcer écran, requeue).  
- **Jamais** bloquer le player sur un appel cloud : timeout strict (cible **2–3 s**).

### 3.3 Provider cloud

- Config : `moderation.cloud.provider: gemini | openai`  
- Clés **hors repo** : env `SHOWFEED_GEMINI_API_KEY` / `SHOWFEED_OPENAI_API_KEY` (ou fichier local gitignoré)  
- Prompt système : juger qualité event (flou, sous/sur-expo, dos, raté évident, OK écran) → JSON strict `{ "decision": "approved"|"hold", "reason": "...", "score": 0-1 }`  
- Images : JPEG downscalé avant envoi (ex. max 1280 px) pour coûter moins  
- Vidéos V1 : **skip cloud** (gate local ou hold manuel) sauf spec ultérieure

### 3.4 Fallback local

Déclencheurs → bascule locale **sans consommer de crédit** (ou crédit non débité si l’appel n’a pas abouti) :

- Pas de DNS / pas de route / HTTP ≠ 2xx  
- Timeout  
- Réponse JSON invalide  
- Crédits épuisés (voir 3.5)

Le gate Pillow existant reste le filet. Option future : ONNX local (hors scope immédiat si trop long).

### 3.5 Système de crédits

| Concept | Spec |
|---|---|
| Unité | 1 crédit = 1 appel Vision réussi sur 1 still |
| Pool | Par event / install : `ops.credits_total` (ex. 500) |
| État | Persisté sur SSD : `media_root/ops/credits.json` (`remaining`, `used`, `total`, `reset_at`) |
| Débit | Après réponse cloud OK uniquement |
| À 0 | Mode local forcé jusqu’à reset manuel |
| Soft warn | Alerte `/regie` à ≤ 20 % restants |
| Critical | Alerte à 0 + message « cloud off — local only » |
| Reset | Bouton régie « Reset crédits » (confirm) + endpoint `POST /api/ops/credits/reset` |
| Top-up | `POST /api/ops/credits/add` `{ "amount": N }` (LAN only, pas d’auth V1 documée) |

Affichage `/regie` : `Crédits IA : 372 / 500 · mode: cloud|local`.

Estimation coût (optionnelle, affichage only) : `credits_used * estimated_cost_per_call` dans config.

### 3.6 Config (exemple à ajouter)

```yaml
moderation:
  enabled: true
  backend: auto          # auto | cloud | local
  # ... seuils locaux existants ...
  cloud:
    provider: gemini     # gemini | openai
    timeout_seconds: 2.5
    max_edge_px: 1280
    model: ""            # override optionnel

ops:
  hold_warn_count: 3
  disk_warn_percent: 85
  inbox_stuck_seconds: 30
  credits_total: 500
  credits_warn_percent: 20
  estimated_usd_per_credit: 0.002
```

### 3.7 API / régie à étendre

- `GET /api/ops` : ajouter `credits: { total, remaining, used, mode }` + alertes `credits_low` / `credits_empty` / `cloud_unreachable`  
- `POST /api/ops/credits/reset`  
- `POST /api/ops/credits/add`  
- UI `/regie` : jauge crédits + badge mode

### 3.8 Sim / tests

- Master CUE : mode `cloud` mock (fixture JSON) + cas timeout → assert fallback local  
- Smoke : 0 crédit → aucun appel HTTP sortant  
- Ne jamais committer de clés API

### 3.9 Hors scope de ce lot

- Facturation client finale / Stripe  
- Modération vidéo cloud  
- Auth forte sur `/regie` (LAN event assume trusted)  
- Remplacer le gate local

### 3.10 Critères d’acceptation

1. Uplink OK + crédits > 0 → stills passent par le cloud ; `used` s’incrémente.  
2. Couper le net ou forcer timeout → approved/hold via local, show continue, idle OK.  
3. Crédits à 0 → local only + alerte régie ; pas d’appel cloud.  
4. Reset crédits depuis `/regie` remet le pool.  
5. Clés absentes → comportement = local (pas de crash watcher).

---

## 4. Autres sujets backlog (rappel)

- Native Fire TV / boot kiosk  
- Souvenir QR + Apple Pay (uplink 4G optionnel)  
- Multi-stick provisioning  
- Banque fixtures labellisées + eval precision/recall (complément sim)

---

## 5. Contraintes transverses

- Isolation client : un build / un descripteur ; pas de credentials croisés  
- Ne pas committer `*.p8`, Firebase, clés Tailscale, clés LLM, mots de passe  
- Docs techniques EN dans les README ; pitch FR  
- Proprietary — all rights reserved  

---

## 6. Prompt court pour génération (Claude)

```
Implémente le lot §3 de docs/CAHIER_DES_CHARGES.md dans le repo ShowFeed :
moderation backend auto (cloud Gemini/OpenAI + fallback Pillow),
crédits persistés + UI /regie + endpoints ops, timeout strict, sim mock.
Respecte le code existant (triage.py, moderation.py, ops.py, regie.html).
Pas de clés en dur. Critères d’acceptation §3.10.
```
