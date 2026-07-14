"""
metadata.py
-----------
Schreibt Metadaten (Titel, Interpret, Album, Cover) in die fertigen
Audiodateien - je nach Format mit dem passenden Mutagen-Backend.
"""

import logging
from pathlib import Path
from typing import Optional

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE

logger = logging.getLogger("AudioDownloader")


def write_metadata(
    filepath: Path,
    title: str,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    cover_bytes: Optional[bytes] = None,
) -> None:
    """
    Schreibt Metadaten in die Datei. Fehler werden geloggt, aber nie
    weitergeworfen - ein fehlgeschlagener Tag-Schreibvorgang darf den
    Download-Prozess nicht abbrechen.
    """
    ext = filepath.suffix.lower()
    try:
        if ext == ".mp3":
            _write_mp3(filepath, title, artist, album, cover_bytes)
        elif ext == ".m4a":
            _write_mp4(filepath, title, artist, album, cover_bytes)
        elif ext == ".flac":
            _write_flac(filepath, title, artist, album, cover_bytes)
        elif ext == ".wav":
            _write_wav(filepath, title, artist, album)
        else:
            logger.debug(f"Kein Metadaten-Handler für Format {ext}")
    except Exception as exc:  # bewusst breit gefangen - darf nie crashen
        logger.warning(f"Metadaten konnten nicht geschrieben werden ({filepath.name}): {exc}")


def _write_mp3(filepath, title, artist, album, cover_bytes):
    try:
        tags = EasyID3(filepath)
    except ID3NoHeaderError:
        tags = EasyID3()
        tags.save(filepath)
        tags = EasyID3(filepath)

    tags["title"] = title
    if artist:
        tags["artist"] = artist
    if album:
        tags["album"] = album
    tags.save(filepath)

    if cover_bytes:
        audio = ID3(filepath)
        audio["APIC"] = APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes
        )
        audio.save(filepath)


def _write_mp4(filepath, title, artist, album, cover_bytes):
    audio = MP4(filepath)
    audio["\xa9nam"] = [title]
    if artist:
        audio["\xa9ART"] = [artist]
    if album:
        audio["\xa9alb"] = [album]
    if cover_bytes:
        audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


def _write_flac(filepath, title, artist, album, cover_bytes):
    audio = FLAC(filepath)
    audio["title"] = title
    if artist:
        audio["artist"] = artist
    if album:
        audio["album"] = album

    if cover_bytes:
        pic = Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.data = cover_bytes
        audio.clear_pictures()
        audio.add_picture(pic)

    audio.save()


def _write_wav(filepath, title, artist, album):
    # WAV unterstützt nur eingeschränkt Metadaten (INFO-Chunk), kein Cover
    audio = WAVE(filepath)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["TIT2"] = title if title else ""
    audio.save()
