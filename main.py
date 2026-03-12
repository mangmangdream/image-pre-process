import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
MAX_PREVIEW_SIZE = (1000, 700)


class ImageCropApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Image Pre Process - Batch Crop")
        self.master.geometry("1280x860")

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
        self.output_images = []
        self.output_page = 0
        self.output_thumbs = []

        self.status_var = tk.StringVar(value="请选择一张参考图片后进行框选。")
        self.coord_var = tk.StringVar(value="当前坐标：未选择")
        self.file_var = tk.StringVar(value="参考图片：未加载")

        self._build_ui()

    def _build_ui(self):
        top_frame = tk.Frame(self.master)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(top_frame, text="加载参考图片", command=self.load_image, width=14).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="清除选区", command=self.clear_selection, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="批量裁剪 input", command=self.batch_crop, width=16).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="预览 output", command=self.open_output_preview, width=14).pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, textvariable=self.coord_var, anchor="w").pack(side=tk.LEFT, padx=20)

        info_frame = tk.Frame(self.master)
        info_frame.pack(fill=tk.X, padx=10)
        tk.Label(info_frame, textvariable=self.file_var, anchor="w").pack(fill=tk.X)
        tk.Label(info_frame, textvariable=self.status_var, anchor="w", fg="blue").pack(fill=tk.X, pady=(4, 8))

        self.canvas = tk.Canvas(self.master, bg="#f0f0f0", width=1200, height=720, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        help_text = (
            "使用说明：1. 点击“加载参考图片” 2. 鼠标拖拽框选裁剪区域 3. 点击“批量裁剪 input”处理 input 目录下所有图片，结果输出到 output 目录。"
        )
        tk.Label(self.master, text=help_text, anchor="w", justify=tk.LEFT, fg="#444").pack(fill=tk.X, padx=10, pady=(0, 10))

    def load_image(self):
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

        try:
            image = Image.open(path)
            image.load()
        except Exception as exc:
            messagebox.showerror("加载失败", f"无法打开图片：{exc}")
            return

        self.current_image_path = Path(path)
        self.original_image = image
        self.crop_rect_original = None
        self.file_var.set(f"参考图片：{self.current_image_path}")
        self.status_var.set("图片已加载，请在预览区域拖拽选择裁剪范围。")
        self.coord_var.set("当前坐标：未选择")
        self.render_image()

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

    def get_input_images(self):
        return sorted([
            p for p in self.input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ])

    def get_output_images(self):
        return sorted([
            p for p in self.output_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ])

    def batch_crop(self):
        if self.crop_rect_original is None:
            messagebox.showwarning("未选择区域", "请先加载参考图片并框选裁剪区域。")
            return

        images = self.get_input_images()
        if not images:
            messagebox.showwarning(
                "没有输入文件", f"请先将图片放入目录：\n{self.input_dir}"
            )
            return

        x1, y1, x2, y2 = self.crop_rect_original
        success_count = 0
        fail_count = 0
        failures = []

        self.output_dir.mkdir(exist_ok=True)

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
                    output_path = self.output_dir / image_path.name
                    cropped.save(output_path)
                    success_count += 1
            except Exception as exc:
                fail_count += 1
                failures.append(f"{image_path.name}: {exc}")

        summary = f"处理完成：成功 {success_count} 张，失败 {fail_count} 张。输出目录：{self.output_dir}"
        self.status_var.set(summary)
        if failures:
            detail = "\n".join(failures[:10])
            messagebox.showwarning(
                "部分文件处理失败", f"{summary}\n\n{detail}"
            )
        else:
            messagebox.showinfo("处理完成", summary)

    # -------- output 预览 --------
    def open_output_preview(self):
        images = self.get_output_images()
        if not images:
            messagebox.showinfo("没有输出文件", f"output 目录为空：\n{self.output_dir}")
            return

        if self.output_preview_window and tk.Toplevel.winfo_exists(self.output_preview_window):
            self.output_preview_window.lift()
        else:
            self.output_preview_window = tk.Toplevel(self.master)
            self.output_preview_window.title("Output 预览（每页10张）")
            self.output_preview_window.geometry("1100x700")
            self.output_preview_window.protocol(
                "WM_DELETE_WINDOW", self.close_output_preview
            )

            self.preview_container = tk.Frame(self.output_preview_window)
            self.preview_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            nav_frame = tk.Frame(self.output_preview_window)
            nav_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            self.page_info_var = tk.StringVar(value="")
            tk.Button(nav_frame, text="上一页", command=self.prev_output_page, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(nav_frame, text="下一页", command=self.next_output_page, width=10).pack(side=tk.LEFT, padx=5)
            tk.Label(nav_frame, textvariable=self.page_info_var).pack(side=tk.LEFT, padx=15)

        self.output_images = images
        self.output_page = 0
        self.render_output_page()

    def close_output_preview(self):
        if self.output_preview_window:
            self.output_preview_window.destroy()
            self.output_preview_window = None

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
            frame = tk.Frame(self.preview_container, bd=1, relief=tk.SOLID, padx=4, pady=4)
            frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            try:
                with Image.open(img_path) as im:
                    im.thumbnail(thumb_size)
                    thumb = ImageTk.PhotoImage(im)
            except Exception as exc:
                thumb = None
                err_label = tk.Label(frame, text=f"无法加载\n{img_path.name}\n{exc}", fg="red", justify=tk.LEFT)
                err_label.pack()
                continue

            self.output_thumbs.append(thumb)
            tk.Label(frame, image=thumb).pack()
            tk.Label(frame, text=img_path.name, wraplength=190, justify=tk.LEFT).pack()

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


def main():
    root = tk.Tk()
    app = ImageCropApp(root)
    root.update_idletasks()
    app.render_image()
    root.bind("<Configure>", lambda event: app.render_image() if app.original_image else None)
    root.mainloop()


if __name__ == "__main__":
    main()
