import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from PIL import Image, ImageTk
import oracledb
import datetime
import json
import os
import sys
import threading

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
APP_BG = "#eef3f9"
CARD_BG = "#ffffff"
ACCENT = "#0f766e"
ACCENT_HOVER = "#0b5f59"
TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#475569"

if sys.platform == "darwin":
    os.environ["TK_SILENCE_DEPRECATION"] = "1"
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"


class ImageCropApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Image Pre Process - Batch Crop")
        self.master.geometry("1280x860")
        self.master.minsize(1120, 760)
        self.master.configure(bg=APP_BG)

        self.project_dir = Path(__file__).resolve().parent
        self.input_dir = self.project_dir / "input"
        self.output_dir = self.project_dir / "output"
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self.current_image_path: Path | None = None
        self.original_image: Image.Image | None = None
        self.preview_image: Image.Image | None = None
        self.tk_preview_image = None

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.crop_rect_original = None
        self.drag_start_canvas = None
        self.selection_rect_id = None

        # output 预览相关
        self.output_preview_window = None
        self.preview_container = None
        self.output_nav_frame = None
        self.page_info_var = tk.StringVar(value="")
        self.output_images = []
        self.output_page = 0
        self.output_thumbs = []
        self.render_after_id = None

        self.status_var = tk.StringVar(value="请选择一张参考图片后进行框选。")
        self.coord_var = tk.StringVar(value="当前坐标：未选择")
        self.file_var = tk.StringVar(value="参考图片：未加载")

        # 上传目录，默认 input
        self.upload_dir = self.input_dir
        self.upload_dir_var = tk.StringVar(value=f"上传目录：{self.upload_dir}")
        self.task_running = False
        self.action_buttons = []
        self.busy_buttons = []
        self.task_progress = None
        self.load_request_id = 0

        self._init_styles()
        self._build_ui()

    def _init_styles(self):
        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=APP_BG)
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("Title.TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=("PingFang SC", 20, "bold"))
        style.configure("Subtitle.TLabel", background=APP_BG, foreground=TEXT_SECONDARY, font=("PingFang SC", 11))
        style.configure("CardTitle.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=("PingFang SC", 12, "bold"))
        style.configure("MetaTitle.TLabel", background=CARD_BG, foreground=TEXT_SECONDARY, font=("PingFang SC", 10))
        style.configure("MetaValue.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=("PingFang SC", 10))
        style.configure("Help.TLabel", background=CARD_BG, foreground=TEXT_SECONDARY, font=("PingFang SC", 10))
        style.configure("Status.TLabel", background=CARD_BG, foreground="#0c4a6e", font=("PingFang SC", 10))

        style.configure(
            "Primary.TButton",
            font=("PingFang SC", 10, "bold"),
            foreground="#ffffff",
            background=ACCENT,
            borderwidth=0,
            padding=(12, 9),
        )
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_HOVER), ("disabled", "#95c5bf")],
            foreground=[("disabled", "#eaf7f5")],
        )

        style.configure(
            "Secondary.TButton",
            font=("PingFang SC", 10),
            foreground=TEXT_PRIMARY,
            background="#e2e8f0",
            borderwidth=0,
            padding=(10, 8),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#cbd5e1"), ("disabled", "#edf2f7")],
            foreground=[("disabled", "#94a3b8")],
        )

        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#dbe6f2",
            background=ACCENT,
            bordercolor="#dbe6f2",
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _create_card(self, parent, title: str):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill=tk.BOTH, expand=True)
        return card, body

    def _build_ui(self):
        app_frame = ttk.Frame(self.master, style="App.TFrame", padding=16)
        app_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(app_frame, style="App.TFrame")
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="Image Pre Process", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="批量裁剪与上传工具 · 现代化工作台",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        content = ttk.Panedwindow(app_frame, orient=tk.HORIZONTAL)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(content, style="App.TFrame", padding=(0, 0, 12, 0), width=330)
        left_panel.pack_propagate(False)
        right_panel = ttk.Frame(content, style="App.TFrame")
        content.add(left_panel, weight=1)
        content.add(right_panel, weight=4)

        controls_card, controls_body = self._create_card(left_panel, "快捷操作")
        controls_card.pack(fill=tk.X, pady=(0, 12))

        self.btn_load = ttk.Button(controls_body, text="加载参考图片", command=self.load_image, style="Secondary.TButton")
        self.btn_load.pack(fill=tk.X, pady=(0, 8))
        self.btn_clear = ttk.Button(controls_body, text="清除选区", command=self.clear_selection, style="Secondary.TButton")
        self.btn_clear.pack(fill=tk.X, pady=(0, 8))
        self.btn_batch_crop = ttk.Button(controls_body, text="批量裁剪 input", command=self.batch_crop, style="Primary.TButton")
        self.btn_batch_crop.pack(fill=tk.X, pady=(0, 8))
        self.btn_preview = ttk.Button(controls_body, text="预览 output", command=self.open_output_preview, style="Secondary.TButton")
        self.btn_preview.pack(fill=tk.X, pady=(0, 8))
        self.btn_select_upload_dir = ttk.Button(
            controls_body,
            text="选择上传目录",
            command=self.select_upload_dir,
            style="Secondary.TButton",
        )
        self.btn_select_upload_dir.pack(fill=tk.X, pady=(0, 8))
        self.btn_upload = ttk.Button(controls_body, text="上传到数据库", command=self.upload_to_db, style="Primary.TButton")
        self.btn_upload.pack(fill=tk.X)

        self.action_buttons = [
            self.btn_load,
            self.btn_clear,
            self.btn_batch_crop,
            self.btn_preview,
            self.btn_upload,
            self.btn_select_upload_dir,
        ]
        self.busy_buttons = [
            self.btn_batch_crop,
            self.btn_upload,
        ]

        info_card, info_body = self._create_card(left_panel, "任务信息")
        info_card.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(info_body, text="参考图片", style="MetaTitle.TLabel").pack(anchor="w")
        ttk.Label(info_body, textvariable=self.file_var, style="MetaValue.TLabel", wraplength=280).pack(anchor="w", fill=tk.X, pady=(2, 8))
        ttk.Label(info_body, text="上传目录", style="MetaTitle.TLabel").pack(anchor="w")
        ttk.Label(info_body, textvariable=self.upload_dir_var, style="MetaValue.TLabel", wraplength=280).pack(anchor="w", fill=tk.X, pady=(2, 8))
        ttk.Label(info_body, text="当前坐标", style="MetaTitle.TLabel").pack(anchor="w")
        ttk.Label(info_body, textvariable=self.coord_var, style="MetaValue.TLabel", wraplength=280).pack(anchor="w", fill=tk.X, pady=(2, 0))

        help_card, help_body = self._create_card(left_panel, "操作提示")
        help_card.pack(fill=tk.BOTH, expand=True)
        help_text = "1. 加载参考图\n2. 在画布拖拽选区\n3. 批量裁剪 input\n4. 预览 output 或上传数据库"
        ttk.Label(help_body, text=help_text, style="Help.TLabel", justify=tk.LEFT).pack(anchor="w")

        canvas_card, canvas_body = self._create_card(right_panel, "裁剪画布")
        canvas_card.pack(fill=tk.BOTH, expand=True)
        canvas_wrapper = tk.Frame(canvas_body, bg=CARD_BG)
        canvas_wrapper.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_wrapper, bg="#e2e8f0", width=1200, height=720, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        status_bar = ttk.Frame(canvas_body, style="Card.TFrame")
        status_bar.pack(fill=tk.X, pady=(10, 0))
        self.task_progress = ttk.Progressbar(status_bar, mode="indeterminate", length=120, style="Accent.Horizontal.TProgressbar")
        self.task_progress.pack(side=tk.LEFT)
        ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

    def load_image(self):
        self.load_request_id += 1
        current_request_id = self.load_request_id
        path = filedialog.askopenfilename(
            title="选择参考图片",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
                ("All Files", "*.*"),
            ],
            initialdir=str(self.input_dir if self.input_dir.exists() else self.project_dir),
        )
        if not path:
            return

        self.status_var.set("正在加载参考图片...")
        worker = threading.Thread(
            target=self._load_image_worker,
            args=(path, current_request_id),
            daemon=True,
        )
        worker.start()

    def _load_image_worker(self, path: str, request_id: int):
        try:
            image = Image.open(path)
            image.load()
            self.master.after(0, self._on_load_image_done, Path(path), image, request_id)
        except Exception as exc:
            self.master.after(0, self._on_load_image_failed, str(exc), request_id)

    def _on_load_image_done(self, image_path: Path, image: Image.Image, request_id: int):
        if request_id != self.load_request_id:
            return
        self.current_image_path = image_path
        self.original_image = image
        self.crop_rect_original = None
        self.file_var.set(f"参考图片：{self.current_image_path}")
        self.status_var.set("图片已加载，请在预览区域拖拽选择裁剪范围。")
        self.coord_var.set("当前坐标：未选择")
        self.render_image()

    def _on_load_image_failed(self, error_text: str, request_id: int):
        if request_id != self.load_request_id:
            return
        self.status_var.set("加载失败，请重试。")
        messagebox.showerror("加载失败", f"无法打开图片：{error_text}")

    def render_image(self):
        if self.original_image is None:
            return

        self.canvas.delete("all")
        canvas_width = max(self.canvas.winfo_width(), 200)
        canvas_height = max(self.canvas.winfo_height(), 200)

        image = self.original_image.copy()
        image.thumbnail((canvas_width - 20, canvas_height - 20))
        self.preview_image = image
        self.scale = self.original_image.width / image.width

        self.tk_preview_image = ImageTk.PhotoImage(image)
        self.offset_x = (canvas_width - image.width) // 2
        self.offset_y = (canvas_height - image.height) // 2
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_preview_image)

        if self.crop_rect_original:
            x1, y1, x2, y2 = self.crop_rect_original
            px1 = self.offset_x + x1 / self.scale
            py1 = self.offset_y + y1 / self.scale
            px2 = self.offset_x + x2 / self.scale
            py2 = self.offset_y + y2 / self.scale
            self.selection_rect_id = self.canvas.create_rectangle(px1, py1, px2, py2, outline="red", width=2)

    def on_mouse_down(self, event):
        if self.preview_image is None:
            return
        if not self._point_in_preview(event.x, event.y):
            return
        self.drag_start_canvas = (event.x, event.y)
        if self.selection_rect_id:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None

    def on_mouse_drag(self, event):
        if self.preview_image is None or self.drag_start_canvas is None:
            return

        x1, y1 = self.drag_start_canvas
        x2 = min(max(event.x, self.offset_x), self.offset_x + self.preview_image.width)
        y2 = min(max(event.y, self.offset_y), self.offset_y + self.preview_image.height)

        if self.selection_rect_id:
            self.canvas.delete(self.selection_rect_id)
        self.selection_rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)

    def on_mouse_up(self, event):
        if self.preview_image is None or self.drag_start_canvas is None:
            return

        start_x, start_y = self.drag_start_canvas
        end_x = min(max(event.x, self.offset_x), self.offset_x + self.preview_image.width)
        end_y = min(max(event.y, self.offset_y), self.offset_y + self.preview_image.height)
        self.drag_start_canvas = None

        x1, x2 = sorted([start_x, end_x])
        y1, y2 = sorted([start_y, end_y])

        if abs(x2 - x1) < 2 or abs(y2 - y1) < 2:
            self.clear_selection(update_status=False)
            self.status_var.set("选区过小，请重新框选。")
            return

        ox1 = int(round((x1 - self.offset_x) * self.scale))
        oy1 = int(round((y1 - self.offset_y) * self.scale))
        ox2 = int(round((x2 - self.offset_x) * self.scale))
        oy2 = int(round((y2 - self.offset_y) * self.scale))

        ox1 = max(0, min(ox1, self.original_image.width))
        oy1 = max(0, min(oy1, self.original_image.height))
        ox2 = max(0, min(ox2, self.original_image.width))
        oy2 = max(0, min(oy2, self.original_image.height))

        self.crop_rect_original = (ox1, oy1, ox2, oy2)
        self.coord_var.set(f"当前坐标：({ox1}, {oy1}) - ({ox2}, {oy2})，宽 {ox2 - ox1}，高 {oy2 - oy1}")
        self.status_var.set("裁剪区域已记录，可开始批量处理。")
        self.render_image()

    def clear_selection(self, update_status=True):
        self.crop_rect_original = None
        self.drag_start_canvas = None
        if self.selection_rect_id:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None
        self.coord_var.set("当前坐标：未选择")
        if self.preview_image is not None:
            self.render_image()
        if update_status:
            self.status_var.set("已清除选区。")

    def _point_in_preview(self, x, y):
        if self.preview_image is None:
            return False
        return (
            self.offset_x <= x <= self.offset_x + self.preview_image.width
            and self.offset_y <= y <= self.offset_y + self.preview_image.height
        )

    def _list_images(self, directory: Path):
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在：{directory}")
        if not directory.is_dir():
            raise NotADirectoryError(f"路径不是目录：{directory}")
        return sorted([
            p for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ])

    def get_input_images(self):
        return self._list_images(self.input_dir)

    def get_output_images(self):
        return self._list_images(self.output_dir)

    def schedule_render_image(self):
        if self.original_image is None:
            return
        if self.render_after_id is not None:
            self.master.after_cancel(self.render_after_id)
        self.render_after_id = self.master.after(120, self._render_image_after_resize)

    def _on_canvas_resize(self, _event):
        if self.original_image is not None:
            self.schedule_render_image()

    def _render_image_after_resize(self):
        self.render_after_id = None
        self.render_image()

    def _set_task_running(self, running: bool, status_text: str | None = None):
        self.task_running = running
        for button in self.busy_buttons:
            button.configure(state=(tk.DISABLED if running else tk.NORMAL))
        if self.task_progress is not None:
            if running:
                self.task_progress.start(10)
            else:
                self.task_progress.stop()
        self.canvas.configure(cursor=("watch" if running else "cross"))
        if status_text is not None:
            self.status_var.set(status_text)

    def select_upload_dir(self):
        if self.task_running:
            return
        dir_path = filedialog.askdirectory(
            title="选择上传目录",
            initialdir=str(self.upload_dir),
        )
        if dir_path:
            self.upload_dir = Path(dir_path)
            self.upload_dir_var.set(f"上传目录：{self.upload_dir}")

    def batch_crop(self):
        if self.task_running:
            self.status_var.set("已有任务在执行中，请等待完成。")
            return
        if self.crop_rect_original is None:
            messagebox.showwarning("未选择区域", "请先加载参考图片并框选裁剪区域。")
            return

        try:
            images = self.get_input_images()
        except (FileNotFoundError, NotADirectoryError) as exc:
            messagebox.showerror("输入目录不可用", str(exc))
            return
        if not images:
            messagebox.showwarning(
                "没有输入文件", f"请先将图片放入目录：\n{self.input_dir}"
            )
            return

        self.output_dir.mkdir(exist_ok=True)
        self._set_task_running(True, f"批量裁剪执行中，共 {len(images)} 张，请稍候...")
        crop_rect = self.crop_rect_original
        worker = threading.Thread(
            target=self._batch_crop_worker,
            args=(images, crop_rect),
            daemon=True,
        )
        worker.start()

    def _batch_crop_worker(self, images, crop_rect):
        try:
            x1, y1, x2, y2 = crop_rect
            success_count = 0
            failures = []
            for image_path in images:
                try:
                    with Image.open(image_path) as img:
                        width, height = img.size
                        crop_box = (
                            max(0, min(x1, width)),
                            max(0, min(y1, height)),
                            max(0, min(x2, width)),
                            max(0, min(y2, height)),
                        )
                        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                            raise ValueError("裁剪区域超出当前图片范围，无法生成有效结果")
                        cropped = img.crop(crop_box)
                        output_path = self.output_dir / ("cropped_" + image_path.name)
                        cropped.save(output_path)
                        success_count += 1
                except Exception as exc:
                    failures.append(f"{image_path.name}: {exc}")
            self.master.after(0, self._on_batch_crop_done, success_count, failures)
        except Exception as exc:
            self.master.after(0, self._on_batch_crop_failed, str(exc))

    def _on_batch_crop_done(self, success_count: int, failures):
        fail_count = len(failures)
        summary = f"处理完成：成功 {success_count} 张，失败 {fail_count} 张。输出目录：{self.output_dir}"
        self._set_task_running(False, summary)
        if failures:
            detail = "\n".join(failures[:10])
            messagebox.showwarning("部分文件处理失败", f"{summary}\n\n{detail}")
        else:
            messagebox.showinfo("处理完成", summary)

    def _on_batch_crop_failed(self, error_text: str):
        self._set_task_running(False, "批量裁剪失败。")
        messagebox.showerror("批量裁剪失败", f"错误：{error_text}")

    # -------- output 预览 --------
    def open_output_preview(self):
        try:
            images = self.get_output_images()
        except (FileNotFoundError, NotADirectoryError) as exc:
            messagebox.showerror("输出目录不可用", str(exc))
            return
        if not images:
            messagebox.showinfo("没有输出文件", f"output 目录为空：\n{self.output_dir}")
            return

        if self.output_preview_window and tk.Toplevel.winfo_exists(self.output_preview_window):
            self.output_preview_window.lift()
        else:
            self.output_preview_window = tk.Toplevel(self.master)
            self.output_preview_window.title("Output 预览（每页10张）")
            self.output_preview_window.geometry("1100x700")
            self.output_preview_window.configure(bg=APP_BG)
            self.output_preview_window.protocol(
                "WM_DELETE_WINDOW", self.close_output_preview
            )

            self.preview_container = ttk.Frame(self.output_preview_window, style="Card.TFrame", padding=10)
            self.preview_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            self.output_nav_frame = ttk.Frame(self.output_preview_window, style="Card.TFrame", padding=10)
            self.output_nav_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Button(self.output_nav_frame, text="上一页", command=self.prev_output_page, style="Secondary.TButton").pack(side=tk.LEFT, padx=5)
            ttk.Button(self.output_nav_frame, text="下一页", command=self.next_output_page, style="Secondary.TButton").pack(side=tk.LEFT, padx=5)
            ttk.Label(self.output_nav_frame, textvariable=self.page_info_var, style="MetaValue.TLabel").pack(side=tk.LEFT, padx=15)

        self.output_images = images
        self.output_page = 0
        self.render_output_page()

    def close_output_preview(self):
        if self.output_preview_window:
            self.output_preview_window.destroy()
            self.output_preview_window = None
            self.preview_container = None
            self.output_nav_frame = None

    def render_output_page(self):
        if not (self.output_preview_window and tk.Toplevel.winfo_exists(self.output_preview_window)):
            return

        for widget in self.preview_container.winfo_children():
            widget.destroy()
        self.output_thumbs.clear()

        page_size = 10
        total = len(self.output_images)
        start = self.output_page * page_size
        end = min(start + page_size, total)
        current = self.output_images[start:end]

        # 网格 5 列，2 行
        cols = 5
        thumb_size = (200, 200)
        for idx, img_path in enumerate(current):
            row = idx // cols
            col = idx % cols
            frame = tk.Frame(self.preview_container, bd=0, relief=tk.FLAT, bg=CARD_BG, padx=6, pady=6)
            frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            try:
                with Image.open(img_path) as im:
                    im.thumbnail(thumb_size)
                    thumb = ImageTk.PhotoImage(im)
            except Exception as exc:
                thumb = None
                err_label = tk.Label(frame, text=f"无法加载\n{img_path.name}\n{exc}", fg="#b91c1c", bg=CARD_BG, justify=tk.LEFT)
                err_label.pack()
                continue

            self.output_thumbs.append(thumb)
            tk.Label(frame, image=thumb, bg=CARD_BG).pack()
            tk.Label(frame, text=img_path.name, wraplength=190, justify=tk.LEFT, bg=CARD_BG, fg=TEXT_PRIMARY).pack()

        for i in range(2):
            self.preview_container.rowconfigure(i, weight=1)
        for j in range(cols):
            self.preview_container.columnconfigure(j, weight=1)

        total_pages = (total + page_size - 1) // page_size
        self.page_info_var.set(f"第 {self.output_page + 1} / {max(total_pages,1)} 页，共 {total} 张")

    def prev_output_page(self):
        if self.output_page > 0:
            self.output_page -= 1
            self.render_output_page()

    def next_output_page(self):
        page_size = 10
        total_pages = (len(self.output_images) + page_size - 1) // page_size
        if self.output_page + 1 < total_pages:
            self.output_page += 1
            self.render_output_page()

    def upload_to_db(self):
        if self.task_running:
            self.status_var.set("已有任务在执行中，请等待完成。")
            return
        try:
            images = self._list_images(self.upload_dir)
        except (FileNotFoundError, NotADirectoryError) as exc:
            messagebox.showerror("上传目录不可用", str(exc))
            return
        if not images:
            messagebox.showwarning("没有文件", f"选择的上传目录为空：\n{self.upload_dir}")
            return

        config_path = self.project_dir / "db_config.json"
        if not config_path.exists():
            messagebox.showerror("配置缺失", f"请创建 db_config.json 文件：\n{config_path}")
            return

        self._set_task_running(True, f"数据库上传执行中，共 {len(images)} 张，请稍候...")
        worker = threading.Thread(
            target=self._upload_to_db_worker,
            args=(images, config_path),
            daemon=True,
        )
        worker.start()

    def _upload_to_db_worker(self, images, config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            with oracledb.connect(user=config["user"], password=config["password"], dsn=config["dsn"]) as conn:
                cursor = conn.cursor()
                uploaded_count = 0
                failed = []
                for img_path in images:
                    try:
                        with open(img_path, "rb") as f:
                            blob_data = f.read()
                        created = datetime.datetime.now()
                        cursor.execute(
                            """
                            INSERT INTO SM_POSTS (FILE_BLOB, FILE_NAME, CREATED)
                            VALUES (:1, :2, :3)
                            """,
                            [blob_data, img_path.name, created],
                        )
                        uploaded_count += 1
                    except OSError as exc:
                        failed.append(f"{img_path.name}: {exc}")
                conn.commit()
                self.master.after(0, self._on_upload_done, uploaded_count, failed)
        except Exception as exc:
            self.master.after(0, self._on_upload_failed, str(exc))

    def _on_upload_done(self, uploaded_count: int, failed):
        summary = f"上传完成：成功 {uploaded_count} 张，失败 {len(failed)} 张。"
        self._set_task_running(False, summary)
        if failed:
            detail = "\n".join(failed[:10])
            messagebox.showwarning("部分文件上传失败", f"{summary}\n\n{detail}")
        else:
            messagebox.showinfo("上传完成", f"{summary}\n已写入 SM_POSTS 表。")

    def _on_upload_failed(self, error_text: str):
        self._set_task_running(False, "上传失败。")
        messagebox.showerror("上传失败", f"错误：{error_text}")


def main():
    root = tk.Tk()
    app = ImageCropApp(root)
    root.update_idletasks()
    app.render_image()
    root.mainloop()


if __name__ == "__main__":
    main()
