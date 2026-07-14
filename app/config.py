"""
config.py
---------
Verwaltet die Konfigurationsdatei (config.json) der Anwendung.
Speichert Benutzereinstellungen dauerhaft zwischen Programmstarts.
"""

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path

# Speicherort der Konfigurationsdatei im Benutzerverzeichnis (AppData unter Windows)
APP_NAME = "AudioDownloader"
CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_DIR = CONFIG_DIR / "logs"


@dataclass
class AppConfig:
    """Enthält alle vom Benutzer einstellbaren Optionen."""

    # Zielformat: mp3 | m4a | flac | wav
    audio_format: str = "mp3"

    # Qualität in kbps (nur relevant für verlustbehaftete Formate)
    audio_quality: str = "192"  # 128 / 192 / 256 / 320

    # Verhalten bei bereits existierenden Dateien
    overwrite_existing: bool = False
    skip_existing: bool = True

    # Parallele Downloads
    parallel_downloads: bool = True
    max_concurrent_downloads: int = 3

    # zuletzt verwendeter Zielordner (wird pro Download neu abgefragt,
    # aber als Vorschlag im Explorer-Dialog verwendet)
    last_output_dir: str = str(Path.home() / "Downloads")

    # Auto-Update-Vorbereitung (Platzhalter für zukünftige Update-Logik)
    auto_update_check: bool = True
    current_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "AppConfig":
        # Nur bekannte Felder übernehmen, damit alte/neue Configs kompatibel bleiben
        valid_keys = AppConfig.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return AppConfig(**filtered)


class ConfigManager:
    """Kapselt das Laden und Speichern der AppConfig auf der Festplatte."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.config: AppConfig = self._load()

    def _load(self) -> AppConfig:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AppConfig.from_dict(data)
            except (json.JSONDecodeError, OSError):
                # Beschädigte Config -> Standardwerte verwenden, nicht abstürzen
                return AppConfig()
        return AppConfig()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=4, ensure_ascii=False)
        except OSError:
            pass  # Speichern darf niemals die App zum Absturz bringen

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save()
