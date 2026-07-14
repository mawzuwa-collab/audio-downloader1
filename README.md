# Audio Downloader

Moderne Windows-Desktop-Anwendung mit dunklem UI (Spotify/Discord-Stil) zum
Herunterladen von Audio aus unterstützten, legalen Quellen (z. B. Bandcamp,
SoundCloud-Freigaben, Podcast-/Direktlinks, Creative-Commons-Archive).

> **Wichtig:** Bitte nur Inhalte herunterladen, an denen du die Rechte besitzt
> oder die unter einer entsprechenden Lizenz stehen. Die Nutzung liegt in der
> Verantwortung des Anwenders.

## Projektstruktur

```
AudioDownloader/
├── main.py              # Einstiegspunkt
├── build.py              # PyInstaller-Build-Skript -> .exe
├── installer.iss          # Inno-Setup-Skript -> Windows-Installer
├── requirements.txt
├── app/
│   ├── gui.py             # CustomTkinter-Oberfläche
│   ├── downloader.py       # Download-Kern (Threading, yt-dlp)
│   ├── metadata.py         # ID3/MP4/FLAC-Tags, Cover
│   ├── config.py           # Konfigurationsdatei (config.json)
│   ├── logger.py           # Logging (Datei + GUI-Queue)
│   └── utils.py            # Dateinamen, Formatierung
└── assets/
    ├── icon.ico            # Windows-Icon
    └── icon.png
```

## Voraussetzungen

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) im PATH (wird von yt-dlp für die
  Audiokonvertierung benötigt)
- Windows 10/11 für den finalen EXE-Betrieb

## Installation & Start (Entwicklung)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

## Als eigenständige .exe bauen

```bash
python build.py
```

Ergebnis: `dist/AudioDownloader.exe` (One-File-Build, kein Konsolenfenster).
FFmpeg muss entweder im System-PATH liegen oder manuell neben die EXE gelegt
werden (z. B. `ffmpeg/ffmpeg.exe` – siehe `installer.iss`).

## Windows-Installer erstellen

1. [Inno Setup](https://jrsoftware.org/isinfo.php) installieren
2. `python build.py` ausführen (erzeugt `dist/AudioDownloader.exe`)
3. `iscc installer.iss` ausführen
4. Ergebnis liegt in `installer_output/AudioDownloader_Setup.exe`

## Funktionsübersicht

- **UI:** Dunkles Theme, grüne Akzentfarbe, abgerundete Elemente,
  responsive Grid-Layouts, ausklappbares Einstellungs-Panel
- **Ablauf:** Link einfügen → Download-Button → Windows-Explorer-Dialog zur
  Ordnerwahl → automatischer Start
- **Live-Infos:** aktueller Titel, Fortschritt %, Geschwindigkeit, Restzeit,
  heruntergeladene Datenmenge, verbleibende Titel
- **Fehlerresilienz:** fehlerhafte/nicht verfügbare Titel werden übersprungen
  und geloggt, der Rest läuft ungestört weiter – die App stürzt nie ab
- **Dateiverwaltung:** Sonderzeichen-Bereinigung, Duplikat­erkennung,
  automatisches Überspringen/Überschreiben (konfigurierbar), Cover- und
  Metadaten-Einbettung (Titel, Interpret, Album)
- **Formate:** MP3, M4A, FLAC, WAV mit wählbarer Qualität
- **Performance:** paralleler Download via `ThreadPoolExecutor`
  (konfigurierbare Anzahl gleichzeitiger Downloads), GUI bleibt durch
  striktes Multithreading + `after()`-Callbacks jederzeit responsiv
- **Abschluss-Dialog:** Anzahl erfolgreicher/übersprungener/fehlerhafter
  Titel, Gesamtdauer, Button „Ordner öffnen“
- **Persistenz:** Einstellungen werden in `%APPDATA%\AudioDownloader\config.json`
  gespeichert, Logs in `%APPDATA%\AudioDownloader\logs\`
- **Auto-Update vorbereitet:** `current_version` und `auto_update_check` in
  der Config sind als Anknüpfungspunkt für eine spätere Update-Prüfung
  (z. B. GitHub-Releases-API) angelegt

## Getestete Komponenten

Im Rahmen der Entwicklung wurden folgende Teile automatisiert verifiziert:
- Syntaxprüfung aller Module
- Import & Grundfunktionen von Config, Utils, Metadata, Downloader, Logger
- GUI-Aufbau inkl. Einstellungs-Panel und Log-Fenster (via virtuellem X-Display)

Ein realer End-to-End-Download wurde in dieser Umgebung nicht ausgeführt, da
kein Internetzugriff auf beliebige Zielseiten sowie kein Windows-System zur
Verfügung stehen. Vor dem produktiven Einsatz empfiehlt sich ein Testlauf mit
einer echten, legalen Beispiel-URL.

## Bekannte Einschränkungen

- WAV unterstützt kein Cover-Bild (Format-Limitierung)
- FLAC-Verfügbarkeit hängt von der Quelle ab
- FFmpeg wird nicht mitgeliefert und muss separat bereitgestellt werden
  (Lizenzgründe / Paketgröße)
