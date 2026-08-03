from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import ProcessingResult, process_folder
from src.excel_branch_merger.version import APP_NAME, __version__


# Keep the canvas and PNG assets sharp on Windows with display scaling enabled.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


class CanvasButton:
    """Canvas button with predictable pixel geometry."""

    def __init__(
        self,
        canvas: tk.Canvas,
        owner: "ExcelBranchMergerApp",
        name: str,
        box: tuple[int, int, int, int],
        text: str,
        command: Callable[[], None],
        *,
        icon: Image.Image | None = None,
        role: str = "outline-blue",
        enabled: bool = True,
        font_size: int = 12,
        icon_size: int = 20,
        icon_left: int = 14,
        radius: int = 8,
    ) -> None:
        self.canvas = canvas
        self.owner = owner
        self.name = name
        self.x, self.y, self.w, self.h = box
        self.text = text
        self.command = command
        self.icon = icon
        self.role = role
        self.enabled = enabled
        self.hovered = False
        self.font_size = font_size
        self.icon_size = icon_size
        self.icon_left = icon_left
        self.radius = radius
        self.tag = f"button::{name}"
        self._image_item: int | None = None
        self._text_item: int | None = None
        self._icon_item: int | None = None

        self._render()
        self.canvas.tag_bind(self.tag, "<Button-1>", self._click)
        self.canvas.tag_bind(self.tag, "<Enter>", self._enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._leave)

    def _render(self) -> None:
        image = self.owner.make_button_image(
            self.w,
            self.h,
            role=self.role,
            hovered=self.hovered,
            enabled=self.enabled,
            radius=self.radius,
        )
        photo = ImageTk.PhotoImage(image)
        self.owner._image_refs[f"button::{self.name}"] = photo

        if self._image_item is None:
            self._image_item = self.canvas.create_image(
                self.x,
                self.y,
                anchor="nw",
                image=photo,
                tags=(self.tag,),
            )
        else:
            self.canvas.itemconfigure(self._image_item, image=photo)

        colors = self.owner.button_colors(self.role, self.enabled)
        icon_width = 0
        if self.icon is not None:
            size = min(self.icon_size, self.h - 12)
            icon = self.icon.copy().resize((size, size), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon)
            self.owner._image_refs[f"button-icon::{self.name}"] = icon_photo
            icon_x = self.x + self.icon_left
            icon_y = self.y + self.h // 2
            icon_width = size + 9

            if self._icon_item is None:
                self._icon_item = self.canvas.create_image(
                    icon_x,
                    icon_y,
                    anchor="w",
                    image=icon_photo,
                    tags=(self.tag,),
                )
            else:
                self.canvas.coords(self._icon_item, icon_x, icon_y)
                self.canvas.itemconfigure(self._icon_item, image=icon_photo)

        text_x = self.x + (self.w + icon_width) // 2 - (5 if icon_width else 0)
        text_y = self.y + self.h // 2
        if self._text_item is None:
            self._text_item = self.canvas.create_text(
                text_x,
                text_y,
                text=self.text,
                fill=colors["text"],
                font=("Segoe UI", -self.font_size, "bold"),
                anchor="center",
                tags=(self.tag,),
            )
        else:
            self.canvas.coords(self._text_item, text_x, text_y)
            self.canvas.itemconfigure(self._text_item, fill=colors["text"])

        self.canvas.tag_raise(self.tag)

    def _click(self, _event: tk.Event[tk.Misc]) -> None:
        if self.enabled:
            self.command()

    def _enter(self, _event: tk.Event[tk.Misc]) -> None:
        if self.enabled:
            self.hovered = True
            self._render()
            self.canvas.configure(cursor="hand2")

    def _leave(self, _event: tk.Event[tk.Misc]) -> None:
        self.hovered = False
        self._render()
        self.canvas.configure(cursor="")

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.hovered = False
        self._render()


class ExcelBranchMergerApp(tk.Tk):
    """Excel Branch Merger interface for a fixed 952 x 636 client area."""

    WIDTH = 952
    HEIGHT = 636
    WINDOW_CHROME_HEIGHT = 38

    BG = "#F4F7FC"
    TEXT = "#101828"
    MUTED = "#5B6982"
    BORDER = "#D9E4F4"
    BLUE = "#2563EB"
    BLUE_DARK = "#1D55D4"
    GREEN = "#15803D"
    ORANGE = "#EA580C"

    def __init__(self) -> None:
        super().__init__()
        self.base_dir = Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "assets"
        self.config_path = self.base_dir / "config.json"

        self.input_var = tk.StringVar(value=str(self.base_dir / "input"))
        self.output_var = tk.StringVar(value=str(self.base_dir / "output"))
        self._result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._last_result: ProcessingResult | None = None
        self._image_refs: dict[str, ImageTk.PhotoImage] = {}
        self._buttons: dict[str, CanvasButton] = {}
        self._metric_items: dict[str, int] = {}

        self.title(APP_NAME)
        self.resizable(False, False)
        self.configure(bg=self.BG)

        try:
            self.tk.call("tk", "scaling", 1.0)
        except tk.TclError:
            pass

        self._set_centered_geometry()
        self._load_assets()
        self._set_window_icon()
        self._build_canvas()
        self.after(100, self._poll_worker)

    def _set_centered_geometry(self) -> None:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - self.WIDTH) // 2)
        y = max(0, (screen_h - self.HEIGHT - self.WINDOW_CHROME_HEIGHT) // 2)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _load_assets(self) -> None:
        def load(name: str) -> Image.Image:
            return Image.open(self.assets_dir / name).convert("RGBA")

        self.asset_header = load("header_background.png")
        self.asset_logo = load("app_logo.png")
        self.asset_folder_title = load("folders_section_icon.png")
        self.asset_folder_row = load("folder_icon.png")
        self.asset_play = load("process_icon.png")
        self.asset_metric_files = load("metric_files.png")
        self.asset_metric_valid = load("metric_valid.png")
        self.asset_metric_error = load("metric_error.png")
        self.asset_metric_duplicates = load("metric_duplicates.png")
        self.asset_results = load("results_section_icon.png")
        self.asset_report = load("report_icon.png")
        self.asset_error = load("error_icon.png")
        self.asset_output = load("output_folder_icon.png")
        self.asset_status = load("status_success_icon.png")

    def _set_window_icon(self) -> None:
        icon = self.asset_logo.copy().resize((28, 29), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(icon)
        self._image_refs["window-icon"] = photo
        self.iconphoto(True, photo)

    def _build_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.BG,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=False)

        base = self._make_base_background()
        base_photo = ImageTk.PhotoImage(base)
        self._image_refs["base"] = base_photo
        self.canvas.create_image(0, 0, anchor="nw", image=base_photo)

        self._draw_header_content()
        self._draw_folder_content()
        self._draw_metrics()
        self._draw_results()
        self._draw_status("Ready to process Excel files.", state="ready")

    def _make_base_background(self) -> Image.Image:
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG)
        draw = ImageDraw.Draw(image)

        header = self.asset_header.copy().resize((932, 112), Image.Resampling.LANCZOS)
        header = self._rounded_image(header, 11)
        image.paste(header.convert("RGB"), (10, 8), header.getchannel("A"))

        self._draw_card(draw, (12, 130, 940, 332), radius=11)

        metric_cards = [
            (12, 344, 238, 430),
            (246, 344, 472, 430),
            (480, 344, 706, 430),
            (714, 344, 940, 430),
        ]
        for card in metric_cards:
            self._draw_card(draw, card, radius=10)

        self._draw_card(draw, (12, 442, 940, 568), radius=11)

        for y in (178, 223):
            draw.rounded_rectangle(
                (190, y, 810, y + 36),
                radius=7,
                fill="#FFFFFF",
                outline="#C9D8EE",
                width=1,
            )

        draw.line((30, 269, 922, 269), fill="#DDE6F3", width=1)
        return image

    def _draw_card(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        radius: int,
    ) -> None:
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(
            (x1, y1 + 3, x2, y2 + 3),
            radius=radius,
            fill="#E7EDF6",
        )
        draw.rounded_rectangle(
            box,
            radius=radius,
            fill="#FFFFFF",
            outline=self.BORDER,
            width=1,
        )

    @staticmethod
    def _rounded_image(image: Image.Image, radius: int) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, image.width, image.height),
            radius=radius,
            fill=255,
        )
        output = image.copy()
        output.putalpha(mask)
        return output

    def _draw_header_content(self) -> None:
        logo = self.asset_logo.copy().resize((64, 67), Image.Resampling.LANCZOS)
        self._place_image("logo", logo, 39, 29)

        self.canvas.create_text(
            120,
            32,
            text=APP_NAME,
            fill="#FFFFFF",
            font=("Segoe UI", -30, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(
            120,
            75,
            text=f"Desktop Excel consolidation and validation tool   •   Version {__version__}",
            fill="#DFE8FF",
            font=("Segoe UI", -13),
            anchor="nw",
        )

    def _draw_folder_content(self) -> None:
        self._place_image(
            "folder-title",
            self.asset_folder_title.resize((25, 25), Image.Resampling.LANCZOS),
            30,
            145,
        )
        self.canvas.create_text(
            63,
            158,
            text="Folders",
            fill=self.TEXT,
            font=("Segoe UI", -19, "bold"),
            anchor="w",
        )

        self._place_image(
            "input-icon",
            self.asset_folder_row.resize((21, 21), Image.Resampling.LANCZOS),
            31,
            186,
        )
        self._place_image(
            "output-icon",
            self.asset_folder_row.resize((21, 21), Image.Resampling.LANCZOS),
            31,
            231,
        )
        self.canvas.create_text(
            62,
            197,
            text="Input folder",
            fill=self.MUTED,
            font=("Segoe UI", -12),
            anchor="w",
        )
        self.canvas.create_text(
            62,
            242,
            text="Output folder",
            fill=self.MUTED,
            font=("Segoe UI", -12),
            anchor="w",
        )

        self.input_entry = tk.Entry(
            self,
            textvariable=self.input_var,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#FFFFFF",
            fg="#1F2937",
            insertbackground="#1F2937",
            font=("Segoe UI", -12),
        )
        self.input_entry.place(x=203, y=188, width=594, height=17)

        self.output_entry = tk.Entry(
            self,
            textvariable=self.output_var,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#FFFFFF",
            fg="#1F2937",
            insertbackground="#1F2937",
            font=("Segoe UI", -12),
        )
        self.output_entry.place(x=203, y=233, width=594, height=17)

        self._buttons["browse-input"] = CanvasButton(
            self.canvas,
            self,
            "browse-input",
            (820, 178, 108, 36),
            "Browse",
            self._choose_input,
            icon=self.asset_folder_row,
            role="outline-blue",
            font_size=12,
            icon_size=20,
            icon_left=13,
            radius=8,
        )
        self._buttons["browse-output"] = CanvasButton(
            self.canvas,
            self,
            "browse-output",
            (820, 223, 108, 36),
            "Browse",
            self._choose_output,
            icon=self.asset_folder_row,
            role="outline-blue",
            font_size=12,
            icon_size=20,
            icon_left=13,
            radius=8,
        )

        self._buttons["process"] = CanvasButton(
            self.canvas,
            self,
            "process",
            (30, 282, 190, 40),
            "Process Excel Files",
            self._start_processing,
            icon=self.asset_play,
            role="primary",
            font_size=13,
            icon_size=22,
            icon_left=18,
            radius=9,
        )

        self.progress_x = 245
        self.progress_y = 297
        self.progress_w = 600
        self.progress_h = 10
        self.progress_bg = self._create_round_bar(
            self.progress_x,
            self.progress_y,
            self.progress_w,
            self.progress_h,
            "#E0E9F8",
        )
        self.progress_fg = self._create_round_bar(
            self.progress_x,
            self.progress_y,
            0,
            self.progress_h,
            self.BLUE,
        )
        self.progress_text = self.canvas.create_text(
            918,
            302,
            text="0%",
            fill=self.BLUE,
            font=("Segoe UI", -12, "bold"),
            anchor="e",
        )
        self._set_round_bar_width(
            self.progress_fg,
            self.progress_x,
            self.progress_y,
            0,
            self.progress_h,
        )

    def _draw_metrics(self) -> None:
        definitions = [
            ("files", 12, self.asset_metric_files, "Files processed"),
            ("valid", 246, self.asset_metric_valid, "Valid rows"),
            ("errors", 480, self.asset_metric_error, "Error rows"),
            ("duplicates", 714, self.asset_metric_duplicates, "Duplicates removed"),
        ]

        for key, x, icon, label in definitions:
            icon_img = icon.copy().resize((60, 60), Image.Resampling.LANCZOS)
            self._place_image(f"metric-{key}", icon_img, x + 17, 360)

            item = self.canvas.create_text(
                x + 82,
                365,
                text="0",
                fill="#050B16",
                font=("Segoe UI", -26, "bold"),
                anchor="nw",
            )
            self._metric_items[key] = item
            self.canvas.create_text(
                x + 82,
                399,
                text=label,
                fill=self.MUTED,
                font=("Segoe UI", -11),
                anchor="nw",
            )

    def _draw_results(self) -> None:
        self._place_image(
            "results-icon",
            self.asset_results.resize((24, 24), Image.Resampling.LANCZOS),
            30,
            454,
        )
        self.canvas.create_text(
            63,
            466,
            text="Results",
            fill=self.TEXT,
            font=("Segoe UI", -18, "bold"),
            anchor="w",
        )
        self.canvas.create_text(
            30,
            490,
            text="Open generated reports after processing completes.",
            fill=self.MUTED,
            font=("Segoe UI", -11),
            anchor="w",
        )

        self._buttons["report"] = CanvasButton(
            self.canvas,
            self,
            "report",
            (30, 514, 205, 34),
            "Open Consolidated Report",
            lambda: self._open_result("report"),
            icon=self.asset_report,
            role="outline-blue",
            enabled=False,
            font_size=11,
            icon_size=18,
            icon_left=13,
            radius=7,
        )
        self._buttons["error"] = CanvasButton(
            self.canvas,
            self,
            "error",
            (247, 514, 168, 34),
            "Open Error Report",
            lambda: self._open_result("error"),
            icon=self.asset_error,
            role="outline-orange",
            enabled=False,
            font_size=11,
            icon_size=18,
            icon_left=13,
            radius=7,
        )
        self._buttons["output"] = CanvasButton(
            self.canvas,
            self,
            "output",
            (427, 514, 175, 34),
            "Open Output Folder",
            lambda: self._open_path(Path(self.output_var.get())),
            icon=self.asset_output,
            role="outline-green",
            enabled=True,
            font_size=11,
            icon_size=18,
            icon_left=13,
            radius=7,
        )

    def _draw_status(self, text: str, state: str) -> None:
        if hasattr(self, "status_bg"):
            self.canvas.delete(self.status_bg)
            self.canvas.delete(self.status_icon_item)
            self.canvas.delete(self.status_text_item)
            self.canvas.delete(self.status_version_item)

        if state == "error":
            fill, border, color, icon = "#FFF4F2", "#F4C7C2", "#B42318", self.asset_error
        elif state == "processing":
            fill, border, color, icon = "#F2F6FF", "#CCDDFB", self.BLUE, self.asset_play
        else:
            fill, border, color, icon = "#F1FAF3", "#CDE9D2", self.GREEN, self.asset_status

        bg = self._rounded_rect_image(928, 44, fill, border, 9)
        bg_photo = ImageTk.PhotoImage(bg)
        self._image_refs["status-bg"] = bg_photo
        self.status_bg = self.canvas.create_image(12, 580, anchor="nw", image=bg_photo)

        icon_img = icon.copy().resize((22, 22), Image.Resampling.LANCZOS)
        icon_photo = ImageTk.PhotoImage(icon_img)
        self._image_refs["status-icon-dynamic"] = icon_photo
        self.status_icon_item = self.canvas.create_image(27, 591, anchor="nw", image=icon_photo)
        self.status_text_item = self.canvas.create_text(
            59,
            602,
            text=text,
            fill=color,
            font=("Segoe UI", -11, "bold"),
            anchor="w",
        )
        self.status_version_item = self.canvas.create_text(
            927,
            602,
            text=f"{APP_NAME} v{__version__}",
            fill=self.MUTED,
            font=("Segoe UI", -10),
            anchor="e",
        )

    def _place_image(self, key: str, image: Image.Image, x: int, y: int) -> int:
        photo = ImageTk.PhotoImage(image)
        self._image_refs[key] = photo
        return self.canvas.create_image(x, y, anchor="nw", image=photo)

    def make_button_image(
        self,
        width: int,
        height: int,
        role: str,
        hovered: bool,
        enabled: bool,
        radius: int,
    ) -> Image.Image:
        colors = self.button_colors(role, enabled)
        if hovered and enabled:
            colors = colors.copy()
            colors["fill"] = colors["hover"]

        image = Image.new("RGBA", (width + 6, height + 7), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        if role == "primary" and enabled:
            shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (3, 4, width + 2, height + 3),
                radius=radius,
                fill=(30, 78, 175, 55),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(2))
            image.alpha_composite(shadow)

        draw.rounded_rectangle(
            (1, 1, width - 1, height - 1),
            radius=radius,
            fill=colors["fill"],
            outline=colors["border"],
            width=1,
        )
        return image

    def button_colors(self, role: str, enabled: bool) -> dict[str, str]:
        if not enabled:
            return {
                "fill": "#F5F7FB",
                "hover": "#F5F7FB",
                "border": "#D6DEEB",
                "text": "#A7B2C5",
            }
        if role == "primary":
            return {
                "fill": self.BLUE,
                "hover": self.BLUE_DARK,
                "border": self.BLUE,
                "text": "#FFFFFF",
            }
        if role == "outline-orange":
            return {
                "fill": "#FFFFFF",
                "hover": "#FFF7F2",
                "border": "#F26A35",
                "text": self.ORANGE,
            }
        if role == "outline-green":
            return {
                "fill": "#FFFFFF",
                "hover": "#F2FBF4",
                "border": "#58B777",
                "text": self.GREEN,
            }
        return {
            "fill": "#FFFFFF",
            "hover": "#F3F7FF",
            "border": "#8FB1FF",
            "text": self.BLUE,
        }

    @staticmethod
    def _rounded_rect_image(
        width: int,
        height: int,
        fill: str,
        border: str,
        radius: int,
    ) -> Image.Image:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (0, 0, width - 1, height - 1),
            radius=radius,
            fill=fill,
            outline=border,
            width=1,
        )
        return image

    def _create_round_bar(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: str,
    ) -> tuple[int, int, int]:
        radius = height // 2
        left = self.canvas.create_oval(
            x,
            y,
            x + height,
            y + height,
            fill=color,
            outline=color,
        )
        rect = self.canvas.create_rectangle(
            x + radius,
            y,
            x + max(radius, width - radius),
            y + height,
            fill=color,
            outline=color,
        )
        right = self.canvas.create_oval(
            x + max(0, width - height),
            y,
            x + width,
            y + height,
            fill=color,
            outline=color,
        )
        return left, rect, right

    def _set_round_bar_width(
        self,
        items: tuple[int, int, int],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        left, rect, right = items
        if width <= 0:
            self.canvas.itemconfigure(left, state="hidden")
            self.canvas.itemconfigure(rect, state="hidden")
            self.canvas.itemconfigure(right, state="hidden")
            return

        self.canvas.itemconfigure(left, state="normal")
        self.canvas.itemconfigure(rect, state="normal")
        self.canvas.itemconfigure(right, state="normal")
        radius = height // 2

        if width <= height:
            self.canvas.coords(left, x, y, x + width, y + height)
            self.canvas.coords(rect, x, y, x, y)
            self.canvas.coords(right, x, y, x + width, y + height)
        else:
            self.canvas.coords(left, x, y, x + height, y + height)
            self.canvas.coords(rect, x + radius, y, x + width - radius, y + height)
            self.canvas.coords(right, x + width - height, y, x + width, y + height)

    def _update_progress(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        width = int(self.progress_w * percent / 100)
        self._set_round_bar_width(
            self.progress_fg,
            self.progress_x,
            self.progress_y,
            width,
            self.progress_h,
        )
        self.canvas.itemconfigure(self.progress_text, text=f"{percent}%")

    def _choose_input(self) -> None:
        selected = filedialog.askdirectory(
            title="Select input folder",
            initialdir=self.input_var.get(),
        )
        if selected:
            self.input_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(
            title="Select output folder",
            initialdir=self.output_var.get(),
        )
        if selected:
            self.output_var.set(selected)

    def _start_processing(self) -> None:
        input_dir = Path(self.input_var.get()).expanduser()
        output_dir = Path(self.output_var.get()).expanduser()
        if not input_dir.is_dir():
            messagebox.showerror(APP_NAME, "Please select a valid input folder.")
            return

        self._last_result = None
        self._buttons["process"].set_enabled(False)
        self._buttons["report"].set_enabled(False)
        self._buttons["error"].set_enabled(False)
        self._update_progress(0)
        self._draw_status("Processing Excel files...", state="processing")

        worker = threading.Thread(
            target=self._run_processing,
            args=(input_dir, output_dir),
            daemon=True,
        )
        worker.start()

    def _run_processing(self, input_dir: Path, output_dir: Path) -> None:
        try:
            config = load_config(self.config_path)
            result = process_folder(
                input_dir,
                output_dir,
                config,
                progress_callback=self._emit_progress,
            )
            self._result_queue.put(("success", result))
        except Exception as exc:
            self._result_queue.put(("error", exc))

    def _emit_progress(self, current: int, total: int, filename: str) -> None:
        self._result_queue.put(("progress", (current, total, filename)))

    def _poll_worker(self) -> None:
        try:
            while True:
                status, payload = self._result_queue.get_nowait()
                if status == "progress":
                    current, total, filename = payload  # type: ignore[misc]
                    percent = int(current * 100 / total) if total else 0
                    self._update_progress(percent)
                    self._draw_status(
                        f"Processing {filename} ({current}/{total})",
                        state="processing",
                    )
                elif status == "success":
                    self._handle_success(payload)
                else:
                    self._handle_error(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_worker)

    def _handle_success(self, payload: object) -> None:
        result = payload
        assert isinstance(result, ProcessingResult)
        self._last_result = result
        self._buttons["process"].set_enabled(True)
        self._buttons["report"].set_enabled(True)
        self._buttons["error"].set_enabled(True)
        self._update_progress(100)

        values = {
            "files": result.files_processed,
            "valid": result.valid_rows,
            "errors": result.error_rows,
            "duplicates": result.duplicates_removed,
        }
        for key, value in values.items():
            self.canvas.itemconfigure(self._metric_items[key], text=str(value))
        self._draw_status("Processing completed successfully.", state="success")

    def _handle_error(self, payload: object) -> None:
        self._buttons["process"].set_enabled(True)
        self._update_progress(0)
        self._draw_status(
            "Processing failed. Review the error message.",
            state="error",
        )
        messagebox.showerror(APP_NAME, str(payload))

    def _open_result(self, kind: str) -> None:
        if self._last_result is None:
            return
        path = (
            self._last_result.report_path
            if kind == "report"
            else self._last_result.error_path
        )
        self._open_path(path)

    @staticmethod
    def _open_path(path: Path) -> None:
        path = path.resolve()
        if not path.exists():
            messagebox.showerror(APP_NAME, f"File or folder not found:\n{path}")
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Unable to open:\n{path}\n\n{exc}")


def main() -> None:
    app = ExcelBranchMergerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
