import os
import re
import json
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageOps

# Твой базовый URL, где лежит index.html галереи
BASE_GALLERY_URL = "https://ombb1979-abk.github.io/gallery/"

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ә': 'a', 'ғ': 'g', 'қ': 'q', 'ң': 'n', 'ө': 'o', 'ұ': 'u', 'ү': 'u', 'һ': 'h', 'і': 'i'
}

def slugify(text: str) -> str:
    text = text.lower().strip()
    res = ''.join(TRANSLIT_MAP.get(ch, ch) for ch in text)
    res = re.sub(r'[^a-z0-9]+', '-', res).strip('-')
    return res or "class"

class GalleryBuilderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FocusLab — Генератор школьных галерей")
        self.geometry("680x740")
        self.resizable(False, False)

        # Корень проекта — папка, где лежит сам скрипт
        self.repo_dir = os.path.dirname(os.path.abspath(__file__))

        self.src_dir_var = tk.StringVar()
        self.title_var = tk.StringVar(value="Школа №4 — 11 «А» класс")
        self.id_var = tk.StringVar()
        self.subtitle_var = tk.StringVar(
            value="Выберите фотографии для выпускного альбома. После отправки откроется ссылка на скачивание всех фото."
        )
        self.archive_url_var = tk.StringVar(value="https://disk.yandex.kz/")
        self.allow_custom_var = tk.BooleanVar(value=True)
        self.git_push_var = tk.BooleanVar(value=True)

        # Настройки слотов
        self.slot_portraits_on = tk.BooleanVar(value=True)
        self.slot_portraits_min = tk.IntVar(value=2)
        self.slot_portraits_max = tk.IntVar(value=3)

        self.slot_group_on = tk.BooleanVar(value=True)
        self.slot_group_min = tk.IntVar(value=1)
        self.slot_group_max = tk.IntVar(value=1)

        self.slot_free_on = tk.BooleanVar(value=False)
        self.slot_free_min = tk.IntVar(value=0)
        self.slot_free_max = tk.IntVar(value=2)

        self.title_var.trace_add("write", self.update_slug)
        self.build_ui()
        self.update_slug()

    def build_ui(self):
        pad = {"padx": 12, "pady": 5}
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Папка с исходниками
        f_src = ttk.LabelFrame(main, text="1. Исходные фотографии")
        f_src.pack(fill="x", **pad)
        ttk.Entry(f_src, textvariable=self.src_dir_var, width=68).pack(side="left", padx=8, pady=8)
        ttk.Button(f_src, text="Выбрать папку...", command=self.choose_folder).pack(side="left", padx=4)

        # 2. Основные параметры класса
        f_info = ttk.LabelFrame(main, text="2. Данные класса и ссылки")
        f_info.pack(fill="x", **pad)

        grid = ttk.Frame(f_info)
        grid.pack(fill="x", padx=8, pady=6)

        ttk.Label(grid, text="Название класса:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=self.title_var, width=55).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(grid, text="ID папки (URL):").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=self.id_var, width=55).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(grid, text="Подзаголовок:").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=self.subtitle_var, width=55).grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(grid, text="Ссылка на архив:").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(grid, textvariable=self.archive_url_var, width=55).grid(row=3, column=1, sticky="w", padx=6)

        # 3. Конструктор ячеек (слотов)
        f_slots = ttk.LabelFrame(main, text="3. Настройка ячеек выбора (слотов)")
        f_slots.pack(fill="x", **pad)
        s_grid = ttk.Frame(f_slots)
        s_grid.pack(fill="x", padx=8, pady=6)

        self._add_slot_row(s_grid, 0, self.slot_portraits_on, "Портреты в виньетку", self.slot_portraits_min, self.slot_portraits_max)
        self._add_slot_row(s_grid, 1, self.slot_group_on, "Общее фото с классом", self.slot_group_min, self.slot_group_max)
        self._add_slot_row(s_grid, 2, self.slot_free_on, "Свободные / с друзьями", self.slot_free_min, self.slot_free_max)

        # 4. Список учеников
        f_stud = ttk.LabelFrame(main, text="4. Список учеников (каждый с новой строки)")
        f_stud.pack(fill="both", expand=True, **pad)

        self.students_text = tk.Text(f_stud, height=8, font=("Consolas", 10))
        self.students_text.pack(fill="both", expand=True, padx=8, pady=6)
        self.students_text.insert("1.0", "Ахметов Алихан\nИванов Артем\nСерікбай Аружан\nСмирнова Дарья")

        ttk.Checkbutton(
            f_stud, text="Разрешить родителям добавлять ученика вручную (если нет в списке)",
            variable=self.allow_custom_var
        ).pack(anchor="w", padx=8, pady=4)

        # 5. Публикация и запуск
        f_act = ttk.Frame(main)
        f_act.pack(fill="x", padx=12, pady=8)

        ttk.Checkbutton(
            f_act, text="Автоматически сделать git commit и git push в репозиторий",
            variable=self.git_push_var
        ).pack(anchor="w", pady=4)

        self.progress = ttk.Progressbar(f_act, mode="determinate")
        self.progress.pack(fill="x", pady=6)

        self.status_lbl = ttk.Label(f_act, text="Готов к сборке.", foreground="#2563eb")
        self.status_lbl.pack(anchor="w")

        self.run_btn = ttk.Button(f_act, text="СОБРАТЬ ГАЛЕРЕЮ И СКОПИРОВАТЬ ССЫЛКУ", command=self.start_build)
        self.run_btn.pack(fill="x", pady=8, ipady=6)

    def _add_slot_row(self, parent, row, check_var, label, min_var, max_var):
        ttk.Checkbutton(parent, text=label, variable=check_var, width=28).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Label(parent, text="Мин:").grid(row=row, column=1, padx=(10, 2))
        ttk.Spinbox(parent, from_=0, to=20, textvariable=min_var, width=4).grid(row=row, column=2)
        ttk.Label(parent, text="Макс:").grid(row=row, column=3, padx=(12, 2))
        ttk.Spinbox(parent, from_=1, to=20, textvariable=max_var, width=4).grid(row=row, column=4)

    def update_slug(self, *args):
        prefix = datetime.now().strftime("%Y-%m")
        self.id_var.set(f"{prefix}-{slugify(self.title_var.get())}")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с обработанными фото")
        if folder:
            self.src_dir_var.set(folder)

    def start_build(self):
        src = self.src_dir_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("Ошибка", "Укажите существующую папку с фотографиями!")
            return

        gallery_id = self.id_var.get().strip()
        if not gallery_id:
            messagebox.showerror("Ошибка", "Укажите ID папки!")
            return

        self.run_btn.config(state="disabled")
        threading.Thread(target=self.process_gallery, args=(src, gallery_id), daemon=True).start()

    def process_gallery(self, src_dir: str, gallery_id: str):
        try:
            target_dir = os.path.join(self.repo_dir, "galleries", gallery_id)
            photos_out_dir = os.path.join(target_dir, "photos")
            os.makedirs(photos_out_dir, exist_ok=True)

            valid_ext = ('.jpg', '.jpeg', '.png', '.webp')
            files = sorted([f for f in os.listdir(src_dir) if f.lower().endswith(valid_ext)])
            if not files:
                raise RuntimeError("В выбранной папке не найдено изображений (JPG/PNG).")

            self.progress["maximum"] = len(files)
            processed_names = []

            for idx, fname in enumerate(files, start=1):
                self.set_status(f"Сжатие фото {idx} из {len(files)}: {fname}...")
                src_path = os.path.join(src_dir, fname)
                # Сохраняем оригинальное имя (без пробелов) или нумеруем аккуратно
                clean_name = re.sub(r'\s+', '_', os.path.splitext(fname)[0]) + ".jpg"
                out_path = os.path.join(photos_out_dir, clean_name)

                with Image.open(src_path) as img:
                    img = ImageOps.exif_transpose(img)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                    img.save(out_path, "JPEG", quality=82, optimize=True)

                processed_names.append(clean_name)
                self.progress["value"] = idx

            # Формируем слоты
            slots = []
            if self.slot_portraits_on.get():
                slots.append({
                    "id": "portraits",
                    "name": "Портреты в виньетку",
                    "min": self.slot_portraits_min.get(),
                    "max": self.slot_portraits_max.get()
                })
            if self.slot_group_on.get():
                slots.append({
                    "id": "group",
                    "name": "Общее фото с классом",
                    "min": self.slot_group_min.get(),
                    "max": self.slot_group_max.get()
                })
            if self.slot_free_on.get():
                slots.append({
                    "id": "free",
                    "name": "Свободные / с друзьями",
                    "min": self.slot_free_min.get(),
                    "max": self.slot_free_max.get()
                })

            if not slots:
                raise RuntimeError("Включите хотя бы одну ячейку выбора (слот)!")

            raw_students = self.students_text.get("1.0", "end").splitlines()
            students = [s.strip() for s in raw_students if s.strip()]

            config_data = {
                "title": self.title_var.get().strip(),
                "subtitle": self.subtitle_var.get().strip(),
                "archiveUrl": self.archive_url_var.get().strip(),
                "allowCustomName": self.allow_custom_var.get(),
                "students": students,
                "slots": slots,
                "photos": processed_names
            }

            config_path = os.path.join(target_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            if self.git_push_var.get():
                self.set_status("Отправка файлов в репозиторий (git push)...")
                self.run_git_push(gallery_id)

            final_url = f"{BASE_GALLERY_URL}?id={gallery_id}"
            self.after(0, lambda: self.on_success(final_url, len(processed_names)))

        except Exception as e:
            self.after(0, lambda: self.on_error(str(e)))

    def run_git_push(self, gallery_id: str):
        cmds = [
            ["git", "add", f"galleries/{gallery_id}"],
            ["git", "commit", "-m", f"Add gallery {gallery_id}"],
            ["git", "push"]
        ]
        for cmd in cmds:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Ошибка Git ({' '.join(cmd)}):\n{res.stderr}")

    def set_status(self, text: str):
        self.after(0, lambda: self.status_lbl.config(text=text))

    def on_success(self, url: str, count: int):
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()
        self.set_status(f"Готово! Обработано {count} фото. Ссылка в буфере обмена.")
        self.run_btn.config(state="normal")
        messagebox.showinfo(
            "Готово!",
            f"Галерея успешно собрана ({count} фото).\n\nСсылка скопирована в буфер обмена:\n{url}"
        )

    def on_error(self, err_msg: str):
        self.set_status("Ошибка при сборке.")
        self.run_btn.config(state="normal")
        messagebox.showerror("Ошибка", err_msg)

if __name__ == "__main__":
    app = GalleryBuilderApp()
    app.mainloop()