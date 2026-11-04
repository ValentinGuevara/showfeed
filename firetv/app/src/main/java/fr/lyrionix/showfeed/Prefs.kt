package fr.lyrionix.showfeed

import android.content.Context

object Prefs {
    private const val NAME = "showfeed_player"
    private const val KEY_URL = "player_url"

    fun getPlayerUrl(context: Context): String {
        val prefs = context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_URL, null)
            ?: context.getString(R.string.default_player_url)
    }

    fun setPlayerUrl(context: Context, url: String) {
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_URL, url.trim())
            .apply()
    }
}
