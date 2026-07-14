"""
utils.py
--------
Allgemeine Hilfsfunktionen: Dateinamen bereinigen, Duplikate erkennen,
Zeit-/Größenformatierung für die Anzeige im GUI.
"""

import re
from pathlib import Path

# Zeichen, die unter Windows in Dateinamen verboten oder problematisch sind
_INVALID_CHARS = r'<>:"/\\|?*\x00-\x1f'
_INVALID_PATTERN = re.compile(f"[{_INVALID_CHARS}]")


def sanitize_filename(name: str, max_length: int = 150) -> str:
    """Entfernt/ersetzt ungültige Zeichen und kürzt zu lange Namen."""
    if not name:
        name = "unbenannt"

    cleaned = _INVALID_PATTERN.sub("", name)
    cleaned = cleaned.strip(" .")  # Windows mag keine Punkte/Leerzeichen am Ende
    cleaned = re.sub(r"\s+", " ", cleaned)  # mehrfache Leerzeichen zusammenfassen

    if not cleaned:
        cleaned = "unbenannt"

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()

    return cleaned


def get_unique_path(directory: Path, filename: str) -> Path:
    """
    Gibt einen Dateipfad zurück, der garantiert noch nicht existiert.
    Hängt bei Kollision '(1)', '(2)', ... an den Dateinamen an.
    """
    base = Path(filename).stem
    ext = Path(filename).suffix
    candidate = directory / f"{base}{ext}"

    counter = 1
    while candidate.exists():
        candidate = directory / f"{base} ({counter}){ext}"
        counter += 1

    return candidate


def format_bytes(num_bytes: float) -> str:
    """Formatiert Bytes menschenlesbar, z.B. 1.4 MB."""
    if num_bytes is None:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def format_eta(seconds: float) -> str:
    """Formatiert Sekunden als mm:ss oder hh:mm:ss."""
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_speed(bytes_per_sec: float) -> str:
    if not bytes_per_sec:
        return "-- KB/s"
    return f"{format_bytes(bytes_per_sec)}/s"
