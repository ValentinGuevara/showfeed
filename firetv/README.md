# ShowFeed — Fire TV Player (V1)

Fullscreen Android TV / Fire OS app that loads the Raspberry Pi player UI in a WebView.

Product pitch: [https://lyrionix.fr/showfeed/](https://lyrionix.fr/showfeed/)

```
Fire TV Stick  →  http://<pi-ip>:8080/  →  approved photos & clips
```

## Requirements

- Fire TV Stick (or any Android TV device, API 25+)
- Raspberry Pi running the [SHOWFEED Pi stack](../pi/) on the same LAN
- Sideload install (V1 is not published on the Amazon Appstore)

## Features (V1)

- Leanback launcher icon on Fire TV home
- Immersive fullscreen WebView
- Configurable Pi URL (Menu / Info remote button → Settings)
- Cleartext HTTP allowed for local LAN
- Keeps the screen on during playback

## Default URL

`http://192.168.50.10:8080/`

Change it on the device (Menu → Settings) or edit `app/src/main/res/values/strings.xml` (`default_player_url`) before building.

## Build

Open `firetv/` in Android Studio, or:

```bash
cd firetv
./gradlew :app:assembleDebug
```

APK output:

```
app/build/outputs/apk/debug/app-debug.apk
```

## Install on a Fire TV Stick

1. Enable **ADB debugging** and **Apps from Unknown Sources** on the Stick  
2. Connect:

```bash
adb connect <fire-tv-ip>:5555
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

3. Launch **SHOWFEED Player** from the Apps row  
4. Press **Menu** on the remote → set the Pi URL if needed  

## Project layout

```
firetv/
  app/src/main/java/fr/lyrionix/showfeed/player/
    MainActivity.kt       # WebView kiosk
    SettingsActivity.kt   # Pi URL
    Prefs.kt
  app/src/main/AndroidManifest.xml
```

## Out of scope (later)

- Native ExoPlayer / offline cache
- Auto-start on boot as device owner
- Appstore release / signed production track
