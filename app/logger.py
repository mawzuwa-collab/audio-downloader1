"""
logger.py
---------
Zentrales Logging. Schreibt in eine Log-Datei UND in eine Queue,
aus der das GUI-Log-Fenster thread-sicher lesen kann.
"""

import logging
import queue
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config import LOG_DIR

# Thread-sichere Queue, die vom GUI-Thread periodisch geleert wird
log_queue: "queue.Queue[str]" = queue.Queue()


class QueueLogHandler(logging.Handler):
    """Leitet jede Log-Nachricht zusätzlich in die GUI-Queue weiter."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            log_queue.put_nowait(msg)
        except Exception:
            pass  # Logging darf nie selbst einen Fehler werfen


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("AudioDownloader")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # bereits initialisiert

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )

    # Datei-Handler mit Rotation (max 2 MB, 3 Backups)
    log_file = LOG_DIR / f"session_{datetime.now():%Y%m%d_%H%M%S}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Queue-Handler für die GUI
    queue_handler = QueueLogHandler()
    queue_handler.setFormatter(formatter)
    queue_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(queue_handler)

    return logger
