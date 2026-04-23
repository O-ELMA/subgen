import os
import platform
import sys
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import tkinterdnd2
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False

import customtkinter as ctk

from config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, OUTPUT_DIR
from ai_engine import transcribe


MEDIA_FILETYPES = [
    ("Media files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mp3 *.wav *.flac *.aac *.ogg *.opus *.m4a *.wma *.aiff *.alac *.wv *.tta"),
    ("All files", "*.*")
]


# =============================================================================
# THEME
# =============================================================================
THEME = {
    # Backgrounds
    "bg": "#1a1b26",
    "card": "#24283b",
    "surface": "#1f2335",
    "input": "#16161e",
    # Accents
    "accent_teal": "#7dcfff",
    "accent_lavender": "#bb9af7",
    "accent_pink": "#f7768e",
    "accent_green": "#73daca",
    "accent_orange": "#ff9e64",
    # Text
    "text_primary": "#c0caf5",
    "text_secondary": "#565f89",
    "text_muted": "#414868",
    # Borders
    "border": "#414868",
    "border_hover": "#7dcfff",
    # Geometry
    "corner_radius_large": 16,
    "corner_radius_medium": 12,
    "corner_radius_small": 8,
    "pad_large": 32,
    "pad_medium": 20,
    "pad_small": 12,
    # Typography
    "font_family": "Inter" if platform.system() != "Darwin" else "SF Pro Text",
    "font_fallback": "Roboto" if platform.system() != "Darwin" else "Helvetica Neue",
    "font_mono": "JetBrains Mono" if platform.system() != "Darwin" else "Menlo",
    "font_mono_fallback": "Consolas" if platform.system() == "Windows" else "Monaco",
}


def _font(size=13, weight="normal", mono=False):
    """Build a CTkFont using the theme typeface."""
    family = THEME["font_mono"] if mono else THEME["font_family"]
    return ctk.CTkFont(family=family, size=size, weight=weight)


class _SegmentedButton(ctk.CTkFrame):
    """Custom segmented button with independent text colors for selected/unselected states."""

    def __init__(self, master, values, command=None, **kwargs):
        fg = kwargs.pop("fg_color", THEME["surface"])
        corner = kwargs.pop("corner_radius", THEME["corner_radius_small"])
        super().__init__(master, fg_color=fg, corner_radius=corner)

        self.values = list(values)
        self.command = command
        self.selected_value = values[0] if values else None

        self._sel_color = kwargs.pop("selected_color", THEME["accent_teal"])
        self._sel_hover = kwargs.pop("selected_hover_color", self._sel_color)
        self._unsel_color = kwargs.pop("unselected_color", THEME["surface"])
        self._unsel_hover = kwargs.pop("unselected_hover_color", THEME["border"])
        self._txt_color = kwargs.pop("text_color", THEME["text_primary"])
        self._sel_txt = kwargs.pop("selected_text_color", THEME["bg"])
        self._font = kwargs.pop("font", _font(size=12))
        self._width = kwargs.pop("width", None)
        self._height = kwargs.pop("height", 32)

        self.buttons = {}
        for val in values:
            btn_kwargs = {
                "text": val,
                "command": lambda v=val: self._select(v),
                "font": self._font,
                "height": self._height,
                "corner_radius": corner,
                "border_width": 0,
            }
            if self._width is not None:
                btn_kwargs["width"] = self._width
            btn = ctk.CTkButton(self, **btn_kwargs)
            btn.pack(side="left", padx=1, pady=1)
            self.buttons[val] = btn

        self._update_appearance()

    def _select(self, value):
        if self.selected_value == value:
            return
        self.selected_value = value
        self._update_appearance()
        if self.command:
            self.command(value)

    def _update_appearance(self):
        for val, btn in self.buttons.items():
            if val == self.selected_value:
                btn.configure(
                    fg_color=self._sel_color,
                    hover_color=self._sel_hover,
                    text_color=self._sel_txt,
                )
            else:
                btn.configure(
                    fg_color=self._unsel_color,
                    hover_color=self._unsel_hover,
                    text_color=self._txt_color,
                )

    def set(self, value):
        if value in self.buttons:
            self.selected_value = value
            self._update_appearance()

    def get(self):
        return self.selected_value

    def configure_state(self, state):
        for btn in self.buttons.values():
            btn.configure(state=state)


def _collect_files(path, filter_mode):
    """Collect media files from a path based on filter mode."""
    path = os.path.abspath(path)

    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            return [path]
        return []

    if os.path.isdir(path):
        extensions = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        if filter_mode == "audio":
            extensions = AUDIO_EXTENSIONS
        elif filter_mode == "video":
            extensions = VIDEO_EXTENSIONS

        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.splitext(f)[1].lower() in extensions
        )
        return files

    return []


# =============================================================================
# APP
# =============================================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SUBGEN - AI Subtitle Generator")
        self.geometry("1100x850")
        self.minsize(950, 750)
        self.configure(fg_color=THEME["bg"])

        # --- State -----------------------------------------------------------
        self.mode = "Folder"          # "Folder" or "Files"
        self.folder_path = ""
        self.folder_files = []        # curated list of files from folder
        self.selected_files = []
        self.filter_mode = "Both"     # "Audio", "Video", or "Both"
        self.is_running = False
        self.stop_event = threading.Event()
        self.queue = queue.Queue()
        self.current_file_idx = 0
        self.total_files = 0
        self.timer_id = None

        # --- Build UI --------------------------------------------------------
        self._create_widgets()
        self._setup_layout()

        # --- Start polling queue ---------------------------------------------
        self.after(100, self._poll_queue)

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------
    def _create_widgets(self):
        # -- Root container (transparent, handles padding) -------------------
        self.container = ctk.CTkFrame(self, fg_color="transparent")

        # -- Header -----------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="SUBGEN 🦾",
            font=_font(size=32, weight="bold"),
            text_color=THEME["text_primary"],
        )
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="AI Subtitle Generator",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )
        self.mode_segment = _SegmentedButton(
            self.header_frame,
            values=["Folder Mode", "Files Mode"],
            command=self._on_mode_change,
            font=_font(size=12, weight="bold"),
            fg_color=THEME["surface"],
            selected_color=THEME["accent_teal"],
            selected_hover_color="#9de0ff",
            unselected_color=THEME["surface"],
            unselected_hover_color=THEME["border"],
            text_color=THEME["text_primary"],
            selected_text_color=THEME["bg"],
            corner_radius=THEME["corner_radius_small"],
        )
        self.mode_segment.set("Folder Mode")

        # -- Main Card --------------------------------------------------------
        self.main_card = ctk.CTkFrame(
            self.container,
            fg_color=THEME["card"],
            corner_radius=THEME["corner_radius_large"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.main_card.grid_columnconfigure(0, weight=1)
        self.main_card.grid_rowconfigure(0, weight=1)

        # Content frame inside main card
        self.content_frame = ctk.CTkFrame(self.main_card, fg_color="transparent")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # -- Folder mode widgets ----------------------------------------------
        self.folder_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.folder_frame.grid_columnconfigure(0, weight=0)
        self.folder_frame.grid_columnconfigure(1, weight=1)
        self.folder_frame.grid_rowconfigure(0, weight=1)

        self.folder_drop_frame = ctk.CTkFrame(
            self.folder_frame,
            width=320,
            height=220,
            fg_color=THEME["surface"],
            corner_radius=THEME["corner_radius_medium"],
            border_width=2,
            border_color=THEME["border"],
        )
        self.folder_drop_frame.pack_propagate(False)

        self.folder_drop_icon = ctk.CTkLabel(
            self.folder_drop_frame,
            text="📁",
            font=_font(size=36),
            text_color=THEME["accent_teal"],
        )
        self.folder_drop_label = ctk.CTkLabel(
            self.folder_drop_frame,
            text="Drop a folder here or click to browse",
            font=_font(size=14),
            text_color=THEME["text_secondary"],
            wraplength=300,
            justify="center",
        )
        self.folder_path_label = ctk.CTkLabel(
            self.folder_drop_frame,
            text="No folder selected",
            font=_font(size=11),
            text_color=THEME["text_muted"],
            wraplength=300,
            justify="center",
        )

        self.folder_filter_label = ctk.CTkLabel(
            self.folder_frame,
            text="Process:",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )
        self.folder_filter_segment = _SegmentedButton(
            self.folder_frame,
            values=["Audio", "Video", "Both"],
            command=self._on_filter_change,
            width=100,
            font=_font(size=12),
            fg_color=THEME["surface"],
            selected_color=THEME["accent_lavender"],
            selected_hover_color="#d0b9fa",
            unselected_color=THEME["surface"],
            unselected_hover_color=THEME["border"],
            text_color=THEME["text_primary"],
            selected_text_color=THEME["bg"],
            corner_radius=THEME["corner_radius_small"],
        )
        self.folder_filter_segment.set("Both")

        self.folder_count_label = ctk.CTkLabel(
            self.folder_frame,
            text="0 files found",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )

        self.folder_list_frame = ctk.CTkScrollableFrame(
            self.folder_frame,
            height=200,
            fg_color="transparent",
            corner_radius=THEME["corner_radius_small"],
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["text_secondary"],
        )

        # -- Files mode widgets -----------------------------------------------
        self.files_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.files_frame.grid_columnconfigure(0, weight=0)
        self.files_frame.grid_columnconfigure(1, weight=1)
        self.files_frame.grid_rowconfigure(0, weight=1)

        self.files_drop_frame = ctk.CTkFrame(
            self.files_frame,
            width=320,
            height=220,
            fg_color=THEME["surface"],
            corner_radius=THEME["corner_radius_medium"],
            border_width=2,
            border_color=THEME["border"],
        )
        self.files_drop_frame.pack_propagate(False)

        self.files_drop_icon = ctk.CTkLabel(
            self.files_drop_frame,
            text="📄",
            font=_font(size=28),
            text_color=THEME["accent_lavender"],
        )
        self.files_drop_label = ctk.CTkLabel(
            self.files_drop_frame,
            text="Drop audio/video files here or click to browse",
            font=_font(size=14),
            text_color=THEME["text_secondary"],
            wraplength=300,
            justify="center",
        )
        self.files_drop_spacer = ctk.CTkLabel(
            self.files_drop_frame,
            text="",
            font=_font(size=11),
            text_color=THEME["text_muted"],
            wraplength=300,
            justify="center",
        )

        self.files_list_frame = ctk.CTkScrollableFrame(
            self.files_frame,
            height=200,
            fg_color="transparent",
            corner_radius=THEME["corner_radius_small"],
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["text_secondary"],
        )
        self.files_count_label = ctk.CTkLabel(
            self.files_frame,
            text="0 files selected",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )

        # -- Progress Card ----------------------------------------------------
        self.progress_card = ctk.CTkFrame(
            self.container,
            fg_color=THEME["card"],
            corner_radius=THEME["corner_radius_large"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.progress_card.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(
            self.progress_card,
            text="Ready",
            font=_font(size=13, weight="bold"),
            text_color=THEME["text_primary"],
        )

        self.timer_label = ctk.CTkLabel(
            self.progress_card,
            text="",
            font=_font(size=13),
            text_color=THEME["text_secondary"],
        )

        self.overall_progress_label = ctk.CTkLabel(
            self.progress_card,
            text="Overall:",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )
        self.overall_progress_bar = ctk.CTkProgressBar(
            self.progress_card,
            width=400,
            fg_color=THEME["surface"],
            progress_color=THEME["accent_teal"],
            corner_radius=THEME["corner_radius_small"],
        )
        self.overall_progress_bar.set(0)

        self.current_progress_label = ctk.CTkLabel(
            self.progress_card,
            text="Current File:",
            font=_font(size=12),
            text_color=THEME["text_secondary"],
        )
        self.current_progress_bar = ctk.CTkProgressBar(
            self.progress_card,
            width=400,
            fg_color=THEME["surface"],
            progress_color=THEME["accent_lavender"],
            corner_radius=THEME["corner_radius_small"],
        )
        self.current_progress_bar.set(0)

        self.log_textbox = ctk.CTkTextbox(
            self.progress_card,
            height=180,
            wrap="word",
            state="disabled",
            font=_font(size=11, mono=True),
            fg_color=THEME["input"],
            text_color=THEME["accent_teal"],
            border_color=THEME["border"],
            border_width=1,
            corner_radius=THEME["corner_radius_small"],
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["text_secondary"],
        )

        # -- Action Frame -----------------------------------------------------
        self.action_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.transcribe_button = ctk.CTkButton(
            self.action_frame,
            text="Transcribe",
            command=self._start_transcription,
            font=_font(size=14, weight="bold"),
            fg_color=THEME["accent_teal"],
            hover_color="#9de0ff",
            text_color=THEME["bg"],
            width=160,
            height=34,
            corner_radius=THEME["corner_radius_small"],
        )
        self.stop_button = ctk.CTkButton(
            self.action_frame,
            text="Stop",
            command=self._stop_transcription,
            font=_font(size=14, weight="bold"),
            fg_color=THEME["accent_pink"],
            hover_color="#ff9eb4",
            text_color=THEME["bg"],
            text_color_disabled=THEME["bg"],
            width=160,
            height=34,
            corner_radius=THEME["corner_radius_small"],
            state="disabled",
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _setup_layout(self):
        # Root grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Container
        self.container.grid(row=0, column=0, sticky="nsew", padx=40, pady=30)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(1, weight=1)  # main card expands
        self.container.grid_rowconfigure(2, weight=0)

        # Header
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.mode_segment.grid(row=0, column=1, rowspan=2, sticky="e")

        # Main Card
        self.main_card.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=THEME["pad_large"], pady=THEME["pad_large"])

        # Folder mode layout
        self.folder_drop_frame.grid(row=0, column=0, sticky="new", pady=(0, 12))
        self.folder_drop_icon.pack(expand=True, pady=(20, 4))
        self.folder_drop_label.pack()
        self.folder_path_label.pack(pady=(4, 20))
        self.folder_filter_label.grid(row=1, column=0, sticky="w", pady=(4, 6))
        self.folder_filter_segment.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.folder_count_label.grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.folder_list_frame.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=(20, 0))

        # Files mode layout
        self.files_drop_frame.grid(row=0, column=0, sticky="new", pady=(0, 12))
        self.files_drop_icon.pack(expand=True, pady=(20, 4))
        self.files_drop_label.pack()
        self.files_drop_spacer.pack(pady=(4, 20))
        self.files_count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.files_list_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(20, 0))

        self._show_folder_mode()

        # Progress Card
        self.progress_card.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        self.status_label.grid(row=0, column=0, padx=(THEME["pad_large"], 12), pady=(THEME["pad_large"], 8), sticky="w")
        self.timer_label.grid(row=0, column=1, padx=(0, THEME["pad_large"]), pady=(THEME["pad_large"], 8), sticky="e")
        self.overall_progress_label.grid(row=1, column=0, padx=(THEME["pad_large"], 12), pady=6, sticky="w")
        self.overall_progress_bar.grid(row=1, column=1, padx=(0, THEME["pad_large"]), pady=6, sticky="ew")
        self.current_progress_label.grid(row=2, column=0, padx=(THEME["pad_large"], 12), pady=6, sticky="w")
        self.current_progress_bar.grid(row=2, column=1, padx=(0, THEME["pad_large"]), pady=6, sticky="ew")
        self.log_textbox.grid(row=3, column=0, columnspan=2, padx=THEME["pad_large"], pady=(10, THEME["pad_large"]), sticky="ew")

        # Action buttons
        self.action_frame.grid(row=3, column=0, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(3, weight=1)
        self.transcribe_button.grid(row=0, column=1, padx=8)
        self.stop_button.grid(row=0, column=2, padx=8)

        # -- Bindings ---------------------------------------------------------
        self.folder_drop_frame.bind("<Button-1>", lambda e: self._browse_folder())
        self.folder_drop_label.bind("<Button-1>", lambda e: self._browse_folder())
        self.folder_path_label.bind("<Button-1>", lambda e: self._browse_folder())
        self.files_drop_frame.bind("<Button-1>", lambda e: self._browse_files())
        self.files_drop_label.bind("<Button-1>", lambda e: self._browse_files())

        # Drop hover effects
        for drop_frame in (self.folder_drop_frame, self.files_drop_frame):
            drop_frame.bind("<Enter>", lambda e, f=drop_frame: f.configure(border_color=THEME["border_hover"]))
            drop_frame.bind("<Leave>", lambda e, f=drop_frame: f.configure(border_color=THEME["border"]))

        # Drag and drop
        if TKDND_AVAILABLE:
            try:
                self.drop_target_register(tkdnd2.DND_FILES)
                self.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                try:
                    self.tk.eval('package require tkdnd')
                    self.tk.call('dnd', 'bindtarget', self._w, 'DND_Files', '<Drop>')
                    self.bind('<<Drop:DND_Files>>', self._on_drop)
                except Exception as e:
                    self._log(f"Drag and drop initialization failed: {e}")

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------
    def _show_folder_mode(self):
        self.folder_frame.grid(row=0, column=0, sticky="nsew")
        self.files_frame.grid_forget()
        self.mode = "Folder"

    def _show_files_mode(self):
        self.files_frame.grid(row=0, column=0, sticky="nsew")
        self.folder_frame.grid_forget()
        self.mode = "Files"

    def _on_mode_change(self, value):
        if value == "Folder Mode":
            self._show_folder_mode()
        else:
            self._show_files_mode()

    def _on_filter_change(self, value):
        self.filter_mode = value
        if self.folder_path:
            self._update_folder_count()

    def _set_ui_locked(self, locked):
        """Lock or unlock UI components during transcription."""
        state = "disabled" if locked else "normal"
        self.mode_segment.configure_state(state)
        self.folder_filter_segment.configure_state(state)

        # Disable/enable remove buttons in file lists
        for list_frame in (self.folder_list_frame, self.files_list_frame):
            for row in list_frame.winfo_children():
                for widget in row.winfo_children():
                    if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "✕":
                        widget.configure(state=state)

        # Unbind/rebind drop frame clicks and update visuals
        if locked:
            self.folder_drop_frame.configure(border_color=THEME["text_muted"])
            self.files_drop_frame.configure(border_color=THEME["text_muted"])
            self.folder_drop_label.configure(text="Processing...", text_color=THEME["text_muted"])
            self.files_drop_label.configure(text="Processing...", text_color=THEME["text_muted"])

            self.folder_drop_frame.unbind("<Button-1>")
            self.folder_drop_label.unbind("<Button-1>")
            self.folder_path_label.unbind("<Button-1>")
            self.files_drop_frame.unbind("<Button-1>")
            self.files_drop_label.unbind("<Button-1>")
        else:
            self.folder_drop_frame.configure(border_color=THEME["border"])
            self.files_drop_frame.configure(border_color=THEME["border"])
            self.folder_drop_label.configure(
                text="Drop a folder here or click to browse",
                text_color=THEME["text_secondary"],
            )
            self.files_drop_label.configure(
                text="Drop audio/video files here or click to browse",
                text_color=THEME["text_secondary"],
            )

            self.folder_drop_frame.bind("<Button-1>", lambda e: self._browse_folder())
            self.folder_drop_label.bind("<Button-1>", lambda e: self._browse_folder())
            self.folder_path_label.bind("<Button-1>", lambda e: self._browse_folder())
            self.files_drop_frame.bind("<Button-1>", lambda e: self._browse_files())
            self.files_drop_label.bind("<Button-1>", lambda e: self._browse_files())

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------
    def _browse_folder(self):
        if self.is_running:
            return
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path = folder
            self.folder_path_label.configure(text=folder)
            self._update_folder_count()

    def _update_folder_count(self):
        files = _collect_files(self.folder_path, self.filter_mode.lower() if self.filter_mode != "Both" else None)
        self.folder_files = files
        count = len(files)
        self.folder_count_label.configure(text=f"{count} file{'s' if count != 1 else ''} found")
        self._update_folder_list()

    def _update_folder_list(self):
        for widget in self.folder_list_frame.winfo_children():
            widget.destroy()

        for idx, path in enumerate(self.folder_files):
            row_frame = ctk.CTkFrame(
                self.folder_list_frame,
                fg_color=THEME["surface"],
                corner_radius=THEME["corner_radius_small"],
                height=32,
            )
            row_frame.pack(fill="x", pady=3)
            row_frame.pack_propagate(False)

            filename = os.path.basename(path)
            label = ctk.CTkLabel(
                row_frame,
                text=filename,
                font=_font(size=11),
                text_color=THEME["text_primary"],
            )
            label.pack(side="left", padx=(12, 10))

            remove_btn = ctk.CTkButton(
                row_frame,
                text="✕",
                width=22,
                height=22,
                font=_font(size=10, weight="bold"),
                fg_color=THEME["accent_pink"],
                hover_color="#ff9eb4",
                text_color=THEME["bg"],
                corner_radius=THEME["corner_radius_small"],
                command=lambda i=idx: self._remove_folder_file(i),
            )
            remove_btn.pack(side="right", padx=8, pady=4)

    def _remove_folder_file(self, idx):
        if self.is_running:
            return
        if 0 <= idx < len(self.folder_files):
            self.folder_files.pop(idx)
            self._update_folder_list()
            count = len(self.folder_files)
            self.folder_count_label.configure(text=f"{count} file{'s' if count != 1 else ''} found")

    def _browse_files(self):
        if self.is_running:
            return
        files = filedialog.askopenfilenames(
            title="Select Media Files",
            filetypes=MEDIA_FILETYPES
        )
        if files:
            self._add_files(files)

    def _add_files(self, file_paths):
        for path in file_paths:
            if path not in self.selected_files:
                ext = os.path.splitext(path)[1].lower()
                if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                    self.selected_files.append(path)
        self._update_files_list()

    def _update_files_list(self):
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()

        for idx, path in enumerate(self.selected_files):
            row_frame = ctk.CTkFrame(
                self.files_list_frame,
                fg_color=THEME["surface"],
                corner_radius=THEME["corner_radius_small"],
                height=36,
            )
            row_frame.pack(fill="x", pady=3)
            row_frame.pack_propagate(False)

            filename = os.path.basename(path)
            label = ctk.CTkLabel(
                row_frame,
                text=filename,
                font=_font(size=11),
                text_color=THEME["text_primary"],
            )
            label.pack(side="left", padx=(12, 10))

            remove_btn = ctk.CTkButton(
                row_frame,
                text="✕",
                width=22,
                height=22,
                font=_font(size=10, weight="bold"),
                fg_color=THEME["accent_pink"],
                hover_color="#ff9eb4",
                text_color=THEME["bg"],
                corner_radius=THEME["corner_radius_small"],
                command=lambda i=idx: self._remove_file(i),
            )
            remove_btn.pack(side="right", padx=8, pady=4)

        self.files_count_label.configure(
            text=f"{len(self.selected_files)} file{'s' if len(self.selected_files) != 1 else ''} selected"
        )

    def _remove_file(self, idx):
        if self.is_running:
            return
        if 0 <= idx < len(self.selected_files):
            self.selected_files.pop(idx)
            self._update_files_list()

    def _on_drop(self, event):
        if self.is_running:
            return

        data = event.data
        paths = self._parse_drop_data(data)

        if not paths:
            return

        if self.mode == "Folder":
            if len(paths) == 1 and os.path.isdir(paths[0]):
                self.folder_path = paths[0]
                self.folder_path_label.configure(text=paths[0])
                self._update_folder_count()
            else:
                first_file = paths[0]
                if os.path.isfile(first_file):
                    folder = os.path.dirname(first_file)
                    self.folder_path = folder
                    self.folder_path_label.configure(text=folder)
                    self._update_folder_count()
        else:
            valid_files = []
            for path in paths:
                if os.path.isfile(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                        valid_files.append(path)
                elif os.path.isdir(path):
                    files = _collect_files(path, None)
                    valid_files.extend(files)
            self._add_files(valid_files)

    def _parse_drop_data(self, data):
        if not data:
            return []

        raw_paths = []

        # Unix / macOS tkdnd often returns newline-separated paths or file:// URIs
        if '\n' in data and '{' not in data:
            raw_paths = data.split('\n')
        else:
            # Windows-style brace-wrapped paths with spaces
            current = ""
            in_braces = False
            for char in data:
                if char == '{':
                    in_braces = True
                    current = ""
                elif char == '}':
                    in_braces = False
                    if current:
                        raw_paths.append(current)
                    current = ""
                elif char == ' ' and not in_braces:
                    if current:
                        raw_paths.append(current)
                        current = ""
                else:
                    current += char
            if current:
                raw_paths.append(current)

        paths = []
        for path in raw_paths:
            path = path.strip()
            if not path:
                continue
            # Strip file:// URI prefix (Unix DnD sometimes returns these)
            if path.startswith("file://"):
                path = path[7:]
            elif path.startswith("file:/"):
                path = path[6:]
            paths.append(path)

        return paths

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", msg + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    # ------------------------------------------------------------------
    # Transcription control
    # ------------------------------------------------------------------
    def _start_transcription(self):
        if self.is_running:
            return

        files_to_process = []
        if self.mode == "Folder":
            if not self.folder_path:
                messagebox.showerror("Error", "No folder selected.")
                return
            files_to_process = self.folder_files.copy()
        else:
            files_to_process = self.selected_files.copy()

        if not files_to_process:
            messagebox.showerror("Error", "No files to process.")
            return

        self.is_running = True
        self._set_ui_locked(True)
        self.stop_event.clear()
        self.current_file_idx = 0
        self.total_files = len(files_to_process)

        self.transcribe_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_label.configure(text=f"Processing 1/{self.total_files}...")
        self.overall_progress_bar.set(0)
        self.current_progress_bar.set(0)

        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

        self._log(f"Starting transcription of {self.total_files} file(s)...")

        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(files_to_process,),
            daemon=True
        )
        thread.start()

    def _transcribe_worker(self, files):
        for idx, path in enumerate(files):
            if self.stop_event.is_set():
                self.queue.put(("stopped", None))
                return

            self.current_file_idx = idx + 1
            estimated_sec = self._estimate_processing_time(path)
            self.queue.put(("file_start", {"idx": idx + 1, "total": len(files), "path": path, "estimated_sec": estimated_sec}))

            try:
                elapsed, merged = transcribe(
                    path,
                    progress_callback=self._progress_callback,
                    stop_event=self.stop_event
                )
                self.queue.put(("file_done", {"path": path, "elapsed": elapsed}))
            except InterruptedError:
                self.queue.put(("stopped", None))
                return
            except Exception as e:
                self.queue.put(("error", {"path": path, "error": str(e)}))

        self.queue.put(("all_done", None))

    def _progress_callback(self, data):
        self.queue.put(("progress", data))

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self.queue.get_nowait()

                if msg_type == "file_start":
                    self.status_label.configure(
                        text=f"Processing {data['idx']}/{data['total']}: {os.path.basename(data['path'])}",
                        text_color=THEME["accent_teal"],
                    )
                    self.current_progress_bar.set(0)
                    self._log(f"[{data['idx']}/{data['total']}] Processing: {os.path.basename(data['path'])}")
                    self._start_timer(data.get("estimated_sec", 0))

                elif msg_type == "progress":
                    self._handle_progress(data)

                elif msg_type == "file_done":
                    self._stop_timer()
                    self.overall_progress_bar.set(self.current_file_idx / self.total_files)
                    self._log(f"✅ Done: {os.path.basename(data['path'])} ({data['elapsed']:.1f} min)")
                    self._show_notification(data['path'])

                elif msg_type == "error":
                    self._stop_timer()
                    self._log(f"ERROR: {os.path.basename(data['path'])} - {data['error']}")

                elif msg_type == "all_done":
                    self._stop_timer()
                    self._finish_transcription("All done!")

                elif msg_type == "stopped":
                    self._stop_timer()
                    self._finish_transcription("Stopped by user.")

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    def _handle_progress(self, data):
        stage = data.get("stage", "")

        if stage == "chunking":
            self.current_progress_bar.set(0)
        elif stage == "model_loading":
            self.current_progress_bar.set(0.05)
        elif stage == "model_loaded":
            self.current_progress_bar.set(0.1)
        elif stage == "chunk":
            current = data.get("current", 0)
            total = data.get("total", 1)
            if total > 0:
                progress = 0.1 + (0.7 * current / total)
                self.current_progress_bar.set(progress)
        elif stage == "llm":
            self.current_progress_bar.set(0.9)
        elif stage == "srt":
            self.current_progress_bar.set(0.95)
        elif stage == "done":
            self.current_progress_bar.set(1.0)

    def _finish_transcription(self, status_msg):
        self.is_running = False
        self._set_ui_locked(False)
        self.transcribe_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text=status_msg, text_color=THEME["text_primary"])
        self._log(status_msg)

    def _stop_transcription(self):
        if self.is_running:
            self.stop_event.set()
            self.status_label.configure(text="Stopping...", text_color=THEME["accent_pink"])
            self._log("Stop requested by user...")

    def _estimate_processing_time(self, path):
        """Estimate processing time in seconds (3 min processing per 1 min audio)."""
        try:
            from pydub.utils import mediainfo_json
            info = mediainfo_json(path)
            duration_sec = float(info["format"]["duration"])
            return int(duration_sec * 3)
        except Exception:
            return 0

    def _start_timer(self, estimated_sec):
        self._stop_timer()
        self.remaining_sec = estimated_sec
        if self.remaining_sec <= 0:
            self.timer_label.configure(text="Just a few more minutes...")
            return
        self._update_timer_label()
        self.timer_id = self.after(1000, self._tick_timer)

    def _tick_timer(self):
        self.remaining_sec -= 1
        if self.remaining_sec > 0:
            self._update_timer_label()
            self.timer_id = self.after(1000, self._tick_timer)
        else:
            self.timer_label.configure(text="Just a few more minutes...")
            self.timer_id = None

    def _update_timer_label(self):
        m, s = divmod(self.remaining_sec, 60)
        self.timer_label.configure(text=f"~{m:02d}:{s:02d} left")

    def _stop_timer(self):
        if getattr(self, "timer_id", None):
            self.after_cancel(self.timer_id)
            self.timer_id = None
        self.remaining_sec = 0
        self.timer_label.configure(text="")

    def _show_notification(self, filepath):
        top = ctk.CTkToplevel(self)
        top.title("")
        top.geometry("360x90")
        top.resizable(False, False)
        top.configure(fg_color=THEME["bg"])

        # overrideredirect behaves poorly on macOS; use transient + topmost instead
        if platform.system() == "Darwin":
            top.transient(self)
            top.attributes('-topmost', True)
        else:
            top.overrideredirect(True)
            top.lift()
            top.attributes('-topmost', True)

        top.update_idletasks()
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        x = max(10, screen_width - 390)
        y = max(10, screen_height - 130)
        top.geometry(f"360x90+{x}+{y}")

        frame = ctk.CTkFrame(
            top,
            fg_color=THEME["card"],
            corner_radius=THEME["corner_radius_medium"],
            border_width=1,
            border_color=THEME["border"],
        )
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        done_label = ctk.CTkLabel(
            frame,
            text="✓ Done",
            font=_font(size=16, weight="bold"),
            text_color=THEME["accent_green"],
        )
        done_label.pack(pady=(12, 2))

        filename_label = ctk.CTkLabel(
            frame,
            text=os.path.basename(filepath),
            font=_font(size=12),
            text_color=THEME["text_primary"],
        )
        filename_label.pack()

        top.after(4000, top.destroy)


# =============================================================================
# Entry point
# =============================================================================
def run_gui():
    """Entry point to run the GUI application."""
    ctk.set_appearance_mode("System")  # Respect OS dark/light setting
    ctk.set_default_color_theme("dark-blue")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
