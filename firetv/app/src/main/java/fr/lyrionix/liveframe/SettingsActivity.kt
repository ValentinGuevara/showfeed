package fr.lyrionix.liveframe

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AppCompatActivity

class SettingsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val urlInput = findViewById<EditText>(R.id.urlInput)
        val saveButton = findViewById<Button>(R.id.saveButton)

        urlInput.setText(Prefs.getPlayerUrl(this))
        urlInput.setSelection(urlInput.text.length)

        saveButton.setOnClickListener {
            var url = urlInput.text.toString().trim()
            if (url.isNotEmpty() && !url.endsWith("/")) {
                url = "$url/"
            }
            if (url.isNotEmpty()) {
                Prefs.setPlayerUrl(this, url)
            }
            finish()
        }
    }
}
