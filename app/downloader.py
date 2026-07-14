"""
downloader.py
-------------
Kernlogik des Downloads. Läuft komplett in Hintergrund-Threads, damit
die Oberfläche jederzeit flüssig bleibt. Kommuniziert mit dem GUI-Thread
ausschließlich über Callback-Funktionen (thread-sicher, da nur einfache
Datenobjekte übergeben werden).
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .config import AppConfig
from .metadata import write_metadata
from .utils import sanitize_filename, get_unique_path, format_speed, format_eta, format_bytes

logger = logging.getLogger("AudioDownloader")


@dataclass
class TrackProgress:
    """Momentaufnahme des Fortschritts eines einzelnen Titels."""
    title: str = ""
    percent: float = 0.0
    downloaded_bytes: float = 0.0
    total_bytes: float = 0.0
    speed: float = 0.0
    eta: float = 0.0


@dataclass
class DownloadSummary:
    """Zusammenfassung am Ende des gesamten Downloadvorgangs."""
    successful: int = 0
    skipped: int = 0
    failed: int = 0
    total_duration_sec: float = 0.0
    output_dir: str = ""


class DownloadCancelled(Exception):
    """Wird intern verwendet, um einen Abbruch sauber zu signalisieren."""


class DownloadManager:
    """
    Orchestriert den Download eines oder mehrerer Titel von einer URL
    (Einzeltrack, Album oder Playlist - abhängig davon, was yt-dlp aus
    dem Link extrahieren kann).
    """

    def __init__(
        self,
        config: AppConfig,
        on_overall_progress: Callable[[int, int], None],
        on_track_progress: Callable[[TrackProgress], None],
        on_log: Callable[[str, str], None],
        on_finished: Callable[[DownloadSummary], None],
    ):
        self.config = config
        self.on_overall_progress = on_overall_progress   # (fertige, gesamt)
        self.on_track_progress = on_track_progress        # (TrackProgress)
        self.on_log = on_log                               # (level, nachricht)
        self.on_finished = on_finished                     # (DownloadSummary)

        self._cancel_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()

        self._successful = 0
        self._skipped = 0
        self._failed = 0
        self._completed_count = 0
        self._total_count = 0

    # ------------------------------------------------------------------ #
    # Öffentliche Steuerung
    # ------------------------------------------------------------------ #

    def cancel(self):
        """Bricht alle laufenden und ausstehenden Downloads ab."""
        self._cancel_event.set()
        self.on_log("WARNUNG", "Abbruch angefordert - laufende Titel werden gestoppt ...")

    def start(self, url: str, output_dir: str):
        """Startet den Download in einem eigenen Hintergrund-Thread."""
        thread = threading.Thread(
            target=self._run, args=(url, output_dir), daemon=True
        )
        thread.start()

    # ------------------------------------------------------------------ #
    # Interner Ablauf
    # ------------------------------------------------------------------ #

    def _run(self, url: str, output_dir: str):
        start_time = time.time()
        self._cancel_event.clear()
        self._successful = self._skipped = self._failed = self._completed_count = 0

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        try:
            entries = self._extract_entries(url)
        except Exception as exc:
            self.on_log("FEHLER", f"Link konnte nicht analysiert werden: {exc}")
            self.on_finished(DownloadSummary(0, 0, 1, time.time() - start_time, str(out_path)))
            return

        if not entries:
            self.on_log("FEHLER", "Keine herunterladbaren Titel unter diesem Link gefunden.")
            self.on_finished(DownloadSummary(0, 0, 0, time.time() - start_time, str(out_path)))
            return

        self._total_count = len(entries)
        self.on_log("INFO", f"{self._total_count} Titel gefunden. Download startet ...")
        self.on_overall_progress(0, self._total_count)

        max_workers = self.config.max_concurrent_downloads if self.config.parallel_downloads else 1
        max_workers = max(1, min(max_workers, 8))

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        futures: list[Future] = []

        for entry_url in entries:
            if self._cancel_event.is_set():
                break
            futures.append(self._executor.submit(self._download_single, entry_url, out_path))

        for f in futures:
            f.result()  # wartet auf Abschluss, Exceptions werden intern behandelt

        self._executor.shutdown(wait=True)

        summary = DownloadSummary(
            successful=self._successful,
            skipped=self._skipped,
            failed=self._failed,
            total_duration_sec=time.time() - start_time,
            output_dir=str(out_path),
        )
        self.on_log(
            "INFO",
            f"Fertig: {summary.successful} erfolgreich, {summary.skipped} übersprungen, "
            f"{summary.failed} Fehler.",
        )
        self.on_finished(summary)

    def _extract_entries(self, url: str) -> list[str]:
        """
        Ermittelt alle Einzel-URLs (bei Playlists/Alben) ohne bereits
        herunterzuladen. Gibt eine flache Liste von Track-URLs zurück.
        """
        ydl_opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return []

        if "entries" in info and info["entries"]:
            result = []
            for entry in info["entries"]:
                if entry is None:
                    continue
                entry_url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
                if entry_url:
                    result.append(entry_url)
            return result

        # Einzelner Titel, kein Playlist-Objekt
        return [url]

    def _download_single(self, url: str, out_dir: Path):
        """Lädt genau einen Titel herunter - läuft im Thread-Pool."""
        if self._cancel_event.is_set():
            return

        track_progress = TrackProgress(title="Wird ermittelt ...")
        self.on_track_progress(track_progress)

        def progress_hook(d):
            if self._cancel_event.is_set():
                raise DownloadCancelled()

            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                percent = (downloaded / total * 100) if total else 0.0
                tp = TrackProgress(
                    title=d.get("info_dict", {}).get("title", track_progress.title),
                    percent=percent,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    speed=d.get("speed") or 0.0,
                    eta=d.get("eta") or 0.0,
                )
                self.on_track_progress(tp)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.config.audio_format,
                    "preferredquality": self.config.audio_quality,
                }
            ],
            "progress_hooks": [progress_hook],
            "overwrites": self.config.overwrite_existing,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                raw_title = info.get("title", "unbekannter_titel")
                artist = info.get("artist") or info.get("uploader")
                album = info.get("album")

                clean_title = sanitize_filename(raw_title)
                target_ext = f".{self.config.audio_format}"
                expected_file = out_dir / f"{clean_title}{target_ext}"

                # Bereits vorhandene Datei erkennen
                if expected_file.exists():
                    if self.config.skip_existing and not self.config.overwrite_existing:
                        self.on_log("INFO", f"Übersprungen (bereits vorhanden): {clean_title}")
                        with self._lock:
                            self._skipped += 1
                            self._completed_count += 1
                        self.on_overall_progress(self._completed_count, self._total_count)
                        return
                    elif not self.config.overwrite_existing:
                        # Weder überschreiben noch überspringen konfiguriert -> eindeutigen Namen erzeugen
                        expected_file = get_unique_path(out_dir, expected_file.name)

                # Ausgabe-Template auf den sauberen, eindeutigen Namen setzen
                ydl_opts["outtmpl"] = str(expected_file.with_suffix("")) + ".%(ext)s"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                    ydl2.download([url])

                # Cover-Daten laden, falls vorhanden (Thumbnail wurde mitgeschrieben)
                cover_bytes = self._find_and_read_thumbnail(out_dir, expected_file.stem)

                write_metadata(
                    expected_file, title=raw_title, artist=artist, album=album,
                    cover_bytes=cover_bytes,
                )

                self.on_log("ERFOLG", f"Heruntergeladen: {clean_title}")
                with self._lock:
                    self._successful += 1

        except DownloadCancelled:
            self.on_log("WARNUNG", "Titel abgebrochen.")
        except Exception as exc:
            # Genau dieser Titel schlägt fehl - der Rest läuft ungestört weiter
            self.on_log("FEHLER", f"Übersprungen wegen Fehler ({url}): {exc}")
            with self._lock:
                self._failed += 1
        finally:
            with self._lock:
                self._completed_count += 1
            self.on_overall_progress(self._completed_count, self._total_count)

    @staticmethod
    def _find_and_read_thumbnail(out_dir: Path, stem: str) -> Optional[bytes]:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            thumb_path = out_dir / f"{stem}{ext}"
            if thumb_path.exists():
                try:
                    data = thumb_path.read_bytes()
                    thumb_path.unlink(missing_ok=True)  # temporäre Thumbnail-Datei aufräumen
                    return data
                except OSError:
                    return None
        return None
