"""
main.py
-------
Startpunkt der Anwendung. Initialisiert Logging und startet das GUI.

Ausführen im Quellcode-Modus:
    python main.py

Als eigenständige EXE bauen:
    python build.py
"""

import sys
import traceback

from app.logger import setup_logger


def main():
    logger = setup_logger()
    logger.info("Anwendung wird gestartet ...")

    try:
        # Import hier, damit ein Fehler beim GUI-Import ebenfalls sauber geloggt wird
        from app.gui import AudioDownloaderApp

        app = AudioDownloaderApp()
        app.mainloop()
    except Exception:
        # Absoluter Sicherheitsnetz: Die Anwendung darf niemals kommentarlos
        # abstürzen. Der vollständige Traceback landet im Log.
        logger.critical("Unbehandelter Fehler beim Start der Anwendung:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
