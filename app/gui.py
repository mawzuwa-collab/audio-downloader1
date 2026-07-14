"""
gui.py
------
Grafische Oberfläche der Anwendung mit CustomTkinter.
Dunkles Theme, grüne Akzentfarbe, abgerundete Elemente, responsive
Layouts. Die GUI selbst führt keine blockierende Arbeit aus - alle
Downloads laufen über den DownloadManager in Hintergrund-Threads.
"""

import os
import queue
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .config import ConfigManager
from .downloader import DownloadManager, TrackProgress, DownloadSummary
from .logger import log_queue, setup_logger
from .utils import format_bytes, format_eta, format_speed

logger = setup_logger()

# ---------------------------------------------------------------------- #
# Farbschema (Spotify/Discord-inspiriert)
# ---------------------------------------------------------------------- #
COLOR_BG = "#121212"
COLOR_SURFACE = "#1e1e1e"
COLOR_SURFACE_LIGHT = "#282828"
COLOR_ACCENT = "#1DB954"       # klassisches Grün
COLOR_ACCENT_HOVER = "#17a34a"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_MUTED = "#b3b3b3"
COLOR_ERROR = "#e74c3c"
COLOR_WARN = "#f1c40f"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class AudioDownloaderApp(ctk.CTk):
    """Hauptfenster der Anwendung."""

    def __init__(self):
        super().__init__()

        self.title("Audio Downloader")
        self.geometry("900x700")
        self.minsize(760, 600)
        self.configure(fg_color=COLOR_BG)

        self.config_manager = ConfigManager()
        self.download_manager: DownloadManager | None = None
        self.is_downloading = False

        self._build_layout()
        self._poll_log_queue()

    # ------------------------------------------------------------------ #
    # Layout-Aufbau
    # ------------------------------------------------------------------ #

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_input_section()
        self._build_progress_section()
        self._build_log_section()
        self._build_settings_panel()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header, text="🎵  Audio Downloader",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT,
        )
        title.grid(row=0, column=0, sticky="w")

        settings_btn = ctk.CTkButton(
            header, text="⚙ Einstellungen", width=140, corner_radius=20,
            fg_color=COLOR_SURFACE_LIGHT, hover_color=COLOR_SURFACE,
            text_color=COLOR_TEXT, command=self._toggle_settings,
        )
        settings_btn.grid(row=0, column=1, sticky="e")

    def _build_input_section(self):
        frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=16)
        frame.grid(row=1, column=0, sticky="ew", padx=24, pady=10)
        frame.grid_columnconfigure(0, weight=1)

        self.link_entry = ctk.CTkEntry(
            frame, placeholder_text="Link zu einer unterstützten Audioquelle einfügen ...",
            height=48, corner_radius=14, font=ctk.CTkFont(size=15),
            fg_color=COLOR_SURFACE_LIGHT, border_width=0, text_color=COLOR_TEXT,
        )
        self.link_entry.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=16)

        self.download_btn = ctk.CTkButton(
            frame, text="⬇  Download", height=48, width=160, corner_radius=14,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            command=self._on_download_clicked,
        )
        self.download_btn.grid(row=0, column=1, padx=(8, 8), pady=16)

        self.cancel_btn = ctk.CTkButton(
            frame, text="✕ Abbrechen", height=48, width=120, corner_radius=14,
            font=ctk.CTkFont(size=14), fg_color=COLOR_ERROR, hover_color="#c0392b",
            command=self._on_cancel_clicked, state="disabled",
        )
        self.cancel_btn.grid(row=0, column=2, padx=(0, 16), pady=16)

    def _build_progress_section(self):
        frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=16)
        frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=10)
        frame.grid_columnconfigure(0, weight=1)
        self._progress_frame = frame

        self.current_title_label = ctk.CTkLabel(
            frame, text="Kein aktiver Download", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        )
        self.current_title_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 4))

        self.status_label = ctk.CTkLabel(
            frame, text="Bereit", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_MUTED, anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(
            frame, height=14, corner_radius=8, progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE_LIGHT,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))

        self.overall_progress_bar = ctk.CTkProgressBar(
            frame, height=8, corner_radius=6, progress_color=COLOR_ACCENT_HOVER,
            fg_color=COLOR_SURFACE_LIGHT,
        )
        self.overall_progress_bar.set(0)
        self.overall_progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))

        # Info-Grid: Geschwindigkeit / ETA / heruntergeladen / verbleibend
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 18))
        for i in range(4):
            info_frame.grid_columnconfigure(i, weight=1)

        self.speed_label = self._info_stat(info_frame, "Geschwindigkeit", "-- KB/s", 0)
        self.eta_label = self._info_stat(info_frame, "Restzeit", "--:--", 1)
        self.downloaded_label = self._info_stat(info_frame, "Heruntergeladen", "0 B", 2)
        self.remaining_label = self._info_stat(info_frame, "Verbleibend", "0 Titel", 3)

        self.open_folder_btn = ctk.CTkButton(
            frame, text="📂 Ordner öffnen", height=38, corner_radius=12,
            fg_color=COLOR_SURFACE_LIGHT, hover_color=COLOR_ACCENT,
            command=self._open_output_folder, state="disabled",
        )
        self.open_folder_btn.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 16))

    def _info_stat(self, parent, label_text, value_text, col):
        box = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE_LIGHT, corner_radius=12)
        box.grid(row=0, column=col, sticky="ew", padx=6)
        ctk.CTkLabel(
            box, text=label_text, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED,
        ).pack(pady=(10, 0))
        value_label = ctk.CTkLabel(
            box, text=value_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT,
        )
        value_label.pack(pady=(0, 10))
        return value_label

    def _build_log_section(self):
        frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=16)
        frame.grid(row=3, column=0, sticky="nsew", padx=24, pady=(10, 20))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            frame, text="Protokoll", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 4))

        self.log_box = ctk.CTkTextbox(
            frame, height=140, corner_radius=10, fg_color=COLOR_BG,
            text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=12, family="Consolas"),
            wrap="word",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.log_box.configure(state="disabled")

    def _build_settings_panel(self):
        """Ausklappbares Overlay-Panel für die Einstellungen."""
        self.settings_visible = False
        panel = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=16, width=320)
        self.settings_panel = panel

        cfg = self.config_manager.config

        ctk.CTkLabel(
            panel, text="Einstellungen", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_TEXT,
        ).pack(padx=20, pady=(20, 10), anchor="w")

        ctk.CTkLabel(panel, text="Format", text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor="w")
        self.format_menu = ctk.CTkOptionMenu(
            panel, values=["mp3", "m4a", "flac", "wav"], fg_color=COLOR_SURFACE_LIGHT,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            command=lambda v: self.config_manager.update(audio_format=v),
        )
        self.format_menu.set(cfg.audio_format)
        self.format_menu.pack(padx=20, pady=(4, 14), fill="x")

        ctk.CTkLabel(panel, text="Qualität (kbps)", text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor="w")
        self.quality_menu = ctk.CTkOptionMenu(
            panel, values=["128", "192", "256", "320"], fg_color=COLOR_SURFACE_LIGHT,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            command=lambda v: self.config_manager.update(audio_quality=v),
        )
        self.quality_menu.set(cfg.audio_quality)
        self.quality_menu.pack(padx=20, pady=(4, 14), fill="x")

        self.overwrite_var = tk.BooleanVar(value=cfg.overwrite_existing)
        ctk.CTkCheckBox(
            panel, text="Vorhandene Dateien automatisch überschreiben", variable=self.overwrite_var,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_TEXT,
            command=lambda: self.config_manager.update(overwrite_existing=self.overwrite_var.get()),
        ).pack(padx=20, pady=6, anchor="w")

        self.skip_var = tk.BooleanVar(value=cfg.skip_existing)
        ctk.CTkCheckBox(
            panel, text="Vorhandene Dateien überspringen", variable=self.skip_var,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_TEXT,
            command=lambda: self.config_manager.update(skip_existing=self.skip_var.get()),
        ).pack(padx=20, pady=6, anchor="w")

        self.parallel_var = tk.BooleanVar(value=cfg.parallel_downloads)
        ctk.CTkCheckBox(
            panel, text="Parallele Downloads aktivieren", variable=self.parallel_var,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_TEXT,
            command=lambda: self.config_manager.update(parallel_downloads=self.parallel_var.get()),
        ).pack(padx=20, pady=6, anchor="w")

        ctk.CTkLabel(panel, text="Max. gleichzeitige Downloads", text_color=COLOR_TEXT_MUTED).pack(
            padx=20, pady=(10, 0), anchor="w"
        )
        self.concurrent_slider = ctk.CTkSlider(
            panel, from_=1, to=8, number_of_steps=7, progress_color=COLOR_ACCENT,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            command=self._on_concurrent_change,
        )
        self.concurrent_slider.set(cfg.max_concurrent_downloads)
        self.concurrent_slider.pack(padx=20, pady=(4, 4), fill="x")
        self.concurrent_value_label = ctk.CTkLabel(
            panel, text=str(cfg.max_concurrent_downloads), text_color=COLOR_TEXT
        )
        self.concurrent_value_label.pack(padx=20, pady=(0, 16), anchor="w")

        ctk.CTkButton(
            panel, text="Schließen", fg_color=COLOR_SURFACE_LIGHT, hover_color=COLOR_ACCENT,
            command=self._toggle_settings,
        ).pack(padx=20, pady=(0, 20), fill="x")

    def _on_concurrent_change(self, value):
        value = int(value)
        self.concurrent_value_label.configure(text=str(value))
        self.config_manager.update(max_concurrent_downloads=value)

    def _toggle_settings(self):
        if self.settings_visible:
            self.settings_panel.place_forget()
        else:
            self.settings_panel.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=70)
        self.settings_visible = not self.settings_visible

    # ------------------------------------------------------------------ #
    # Event-Handler
    # ------------------------------------------------------------------ #

    def _on_download_clicked(self):
        url = self.link_entry.get().strip()
        if not url:
            messagebox.showwarning("Kein Link", "Bitte zuerst einen Link einfügen.")
            return
        if self.is_downloading:
            return

        # Windows-Explorer-Dialog zur Ordnerauswahl
        chosen_dir = filedialog.askdirectory(
            title="Zielordner auswählen", initialdir=self.config_manager.config.last_output_dir
        )
        if not chosen_dir:
            return  # Benutzer hat abgebrochen

        self.config_manager.update(last_output_dir=chosen_dir)
        self._start_download(url, chosen_dir)

    def _start_download(self, url: str, output_dir: str):
        self.is_downloading = True
        self._set_ui_downloading_state(True)
        self._append_log("INFO", f"Starte Download nach: {output_dir}")

        self.download_manager = DownloadManager(
            config=self.config_manager.config,
            on_overall_progress=self._on_overall_progress,
            on_track_progress=self._on_track_progress,
            on_log=self._append_log,
            on_finished=self._on_finished,
        )
        self._current_output_dir = output_dir
        self.download_manager.start(url, output_dir)

    def _on_cancel_clicked(self):
        if self.download_manager:
            self.download_manager.cancel()
        self.cancel_btn.configure(state="disabled")

    def _set_ui_downloading_state(self, downloading: bool):
        self.download_btn.configure(state="disabled" if downloading else "normal")
        self.cancel_btn.configure(state="normal" if downloading else "disabled")
        self.link_entry.configure(state="disabled" if downloading else "normal")

    # ------------------------------------------------------------------ #
    # Callbacks aus dem Download-Thread (werden thread-sicher über
    # `after()` in den GUI-Thread eingeplant)
    # ------------------------------------------------------------------ #

    def _on_overall_progress(self, done: int, total: int):
        self.after(0, self._update_overall_progress, done, total)

    def _update_overall_progress(self, done: int, total: int):
        ratio = (done / total) if total else 0
        self.overall_progress_bar.set(ratio)
        remaining = max(total - done, 0)
        self.remaining_label.configure(text=f"{remaining} Titel")
        self.status_label.configure(text=f"{done} von {total} Titeln abgeschlossen")

    def _on_track_progress(self, progress: TrackProgress):
        self.after(0, self._update_track_progress, progress)

    def _update_track_progress(self, progress: TrackProgress):
        self.current_title_label.configure(text=f"🎧 {progress.title}")
        self.progress_bar.set(min(progress.percent / 100, 1.0))
        self.speed_label.configure(text=format_speed(progress.speed))
        self.eta_label.configure(text=format_eta(progress.eta))
        self.downloaded_label.configure(text=format_bytes(progress.downloaded_bytes))

    def _on_finished(self, summary: DownloadSummary):
        self.after(0, self._show_summary, summary)

    def _show_summary(self, summary: DownloadSummary):
        self.is_downloading = False
        self._set_ui_downloading_state(False)
        self.open_folder_btn.configure(state="normal")
        self.current_title_label.configure(text="Download abgeschlossen")
        self.progress_bar.set(1.0)

        minutes, seconds = divmod(int(summary.total_duration_sec), 60)
        text = (
            f"✅ {summary.successful} erfolgreich   "
            f"⏭ {summary.skipped} übersprungen   "
            f"⚠ {summary.failed} Fehler   "
            f"⏱ {minutes:02d}:{seconds:02d} Min."
        )
        self.status_label.configure(text=text)

        messagebox.showinfo(
            "Download abgeschlossen",
            f"Erfolgreich: {summary.successful}\n"
            f"Übersprungen: {summary.skipped}\n"
            f"Fehler: {summary.failed}\n"
            f"Dauer: {minutes:02d}:{seconds:02d} Min.",
        )

    def _open_output_folder(self):
        path = getattr(self, "_current_output_dir", None)
        if path and Path(path).exists():
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])

    # ------------------------------------------------------------------ #
    # Log-Fenster
    # ------------------------------------------------------------------ #

    def _append_log(self, level: str, message: str):
        """Kann aus jedem Thread aufgerufen werden - landet über die
        Queue immer sicher im GUI-Thread."""
        log_queue.put(f"[{level}] {message}")

    def _poll_log_queue(self):
        """Wird periodisch im GUI-Thread aufgerufen, um neue Logeinträge
        aus der Queue anzuzeigen (Standard-Pattern für Thread-sicheres
        Tkinter-Logging)."""
        try:
            while True:
                msg = log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", msg + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.after(150, self._poll_log_queue)
