"""
build.py
--------
Erstellt eine eigenständige Windows-.exe mittels PyInstaller.

Voraussetzungen:
    pip install -r requirements.txt

Ausführen:
    python build.py

Ergebnis:
    dist/AudioDownloader.exe
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ICON_PATH = ROOT / "assets" / "icon.ico"


def main():
    # Alte Build-Artefakte entfernen
    for folder in ("build", "dist"):
        target = ROOT / folder
        if target.exists():
            shutil.rmtree(target)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "AudioDownloader",
        "--noconfirm",
        "--onefile",
        "--windowed",              # keine Konsole im Hintergrund
        "--clean",
        "--add-data", f"assets{';' if sys.platform == 'win32' else ':'}assets",
    ]

    if ICON_PATH.exists():
        cmd += ["--icon", str(ICON_PATH)]

    cmd.append(str(ROOT / "main.py"))

    print("Starte PyInstaller-Build ...")
    subprocess.run(cmd, check=True)
    print("\nFertig! Die EXE befindet sich in: dist/AudioDownloader.exe")
    print("Hinweis: ffmpeg.exe muss zusätzlich im PATH oder neben der EXE liegen,")
    print("damit die Audio-Konvertierung funktioniert.")


if __name__ == "__main__":
    main()
