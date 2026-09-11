"""Chinese desktop UI; all widgets stay on the main thread."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from channel_service import scan, run_queue, Settings, Cancelled
from yt_downloader import DEFAULT_OUTPUT


class ChannelApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("YouTube 频道下载器 · 开发预览版")
        self.geometry("1000x740")
        self.minsize(800, 620)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.entries = {}
        self.selected = set()
        self.busy = False
        self.catalog = False
        self.categories = {"普通视频 Videos": "videos", "短视频 Shorts": "shorts", "频道播放列表": "playlists"}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="YouTube 频道下载器", font=("Microsoft YaHei", 24, "bold")).grid(row=0, column=0, pady=12)
        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", padx=18)
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="频道或视频链接").grid(row=0, column=0, padx=10, pady=8)
        self.url = ctk.CTkEntry(form, placeholder_text="https://www.youtube.com/@hubermanlab")
        self.url.grid(row=0, column=1, columnspan=3, sticky="ew", padx=8)
        self.category = ctk.CTkOptionMenu(form, values=list(self.categories))
        self.category.grid(row=1, column=0, padx=8, pady=8)
        ctk.CTkLabel(form, text="扫描数量（0 = 全部）").grid(row=1, column=1, sticky="e")
        self.limit = ctk.CTkEntry(form, width=70)
        self.limit.insert(0, "0")
        self.limit.grid(row=1, column=2, padx=8)
        self.scan_button = ctk.CTkButton(form, text="扫描列表", command=self.start_scan)
        self.scan_button.grid(row=1, column=3, padx=8)
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        self.all_button = ctk.CTkButton(toolbar, text="全选", width=70, command=lambda: self.select_all(True))
        self.all_button.pack(side="left", padx=5, pady=5)
        self.none_button = ctk.CTkButton(toolbar, text="清空选择", width=90, command=lambda: self.select_all(False))
        self.none_button.pack(side="left", padx=5)
        self.open_button = ctk.CTkButton(toolbar, text="打开选中播放列表", command=self.open_playlist)
        self.open_button.pack(side="left", padx=5)
        self.count = ctk.CTkLabel(toolbar, text="点击列表中的行切换勾选")
        self.count.pack(side="right", padx=10)
        frame = ctk.CTkFrame(self)
        frame.grid(row=3, column=0, sticky="nsew", padx=18)
        self.tree = ttk.Treeview(frame, columns=("check", "title", "result"), show="headings", selectmode="browse")
        for key, title, width in [("check", "选择", 50), ("title", "标题", 480), ("result", "结果", 300)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40, stretch=key != "check")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<ButtonRelease-1>", self.toggle)
        self.tree.bind("<space>", self.toggle)
        options = ctk.CTkFrame(self)
        options.grid(row=4, column=0, sticky="ew", padx=18, pady=8)
        options.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(options, text="保存位置").grid(row=0, column=0, padx=8)
        self.output = ctk.CTkEntry(options)
        self.output.insert(0, DEFAULT_OUTPUT)
        self.output.grid(row=0, column=1, columnspan=3, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(options, text="选择文件夹", command=self.choose_dir).grid(row=0, column=4, padx=8)
        self.quality = ctk.CTkOptionMenu(options, values=["1080p", "720p", "480p", "最高"])
        self.quality.grid(row=1, column=0, padx=8, pady=8)
        self.subs = ctk.CTkCheckBox(options, text="下载字幕")
        self.subs.select()
        self.subs.grid(row=1, column=1, padx=8)
        self.auto = ctk.CTkCheckBox(options, text="包含自动字幕")
        self.auto.select()
        self.auto.grid(row=1, column=2, padx=8)
        self.languages = ctk.CTkOptionMenu(options, values=["英文和中文", "英文", "中文"])
        self.languages.grid(row=1, column=4, padx=8)
        actions = ctk.CTkFrame(self)
        actions.grid(row=5, column=0, sticky="ew", padx=18)
        self.download_button = ctk.CTkButton(actions, text="下载选中项 / 重试", command=self.start_download)
        self.download_button.pack(side="left", padx=8, pady=8)
        self.cancel_button = ctk.CTkButton(actions, text="取消", command=self.request_cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.progress = ctk.CTkProgressBar(actions)
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True, padx=12)
        self.status = ctk.CTkLabel(self, text="先扫描、再勾选下载。字幕保存为 SRT；仅下载可访问内容。", wraplength=900)
        self.status.grid(row=6, column=0, pady=10)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.drain)

    def set_busy(self, value):
        self.busy = value
        for widget in [self.scan_button, self.download_button, self.open_button, self.all_button, self.none_button]:
            widget.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")
        if value:
            self.cancel.clear()
            self.progress.set(0)

    def choose_dir(self):
        if self.busy:
            return
        if folder := filedialog.askdirectory():
            self.output.delete(0, "end")
            self.output.insert(0, folder)

    def start_scan(self):
        if self.busy:
            return
        try:
            limit = int(self.limit.get())
            if limit < 0:
                raise ValueError()
        except ValueError:
            self.status.configure(text="扫描数量请填写 0 或正整数")
            return
        url, category = self.url.get(), self.categories[self.category.get()]
        self.set_busy(True)
        self.status.configure(text="正在扫描，扫描不会下载视频；大型频道可能需要一段时间。")
        def worker():
            try:
                self.events.put(("scanned", scan(url, category, limit, self.cancel)))
            except Cancelled:
                self.events.put(("finished", "已取消扫描"))
            except Exception as exc:
                self.events.put(("finished", f"扫描失败：{exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def toggle(self, event):
        if self.busy:
            return
        item = self.tree.identify_row(event.y) if event.type == tk.EventType.ButtonRelease else self.tree.focus()
        if item not in self.entries:
            return
        if item in self.selected:
            self.selected.remove(item)
        else:
            if self.catalog:
                self.selected.clear()
            self.selected.add(item)
        self.refresh_checks()

    def refresh_checks(self):
        for key in self.entries:
            self.tree.set(key, "check", "✓" if key in self.selected else "")
        self.count.configure(text=f"共 {len(self.entries)} 项 · 已选 {len(self.selected)} 项")

    def select_all(self, value):
        if not self.busy and (not self.catalog or not value):
            self.selected = set(self.entries) if value else set()
            self.refresh_checks()

    def open_playlist(self):
        if not self.catalog or len(self.selected) != 1:
            self.status.configure(text="请先扫描频道播放列表，再选择其中一个列表")
            return
        self.url.delete(0, "end")
        self.url.insert(0, self.entries[next(iter(self.selected))].url)
        self.start_scan()

    def start_download(self):
        if self.busy:
            return
        if self.catalog or not self.selected:
            self.status.configure(text="请先选择视频；播放列表请先点击“打开选中播放列表”")
            return
        output = self.output.get().strip()
        if not output:
            self.status.configure(text="请选择保存位置")
            return
        langs = {"英文和中文": ("en.*", "zh.*"), "英文": ("en.*",), "中文": ("zh.*",)}
        settings = Settings(output, 0 if self.quality.get() == "最高" else int(self.quality.get()[:-1]),
                            bool(self.subs.get()), bool(self.auto.get()), langs[self.languages.get()])
        entries = [e for key, e in self.entries.items() if key in self.selected]
        for e in entries:
            self.tree.set(e.id, "result", "等待")
        self.set_busy(True)
        def worker():
            try:
                run_queue(entries, settings, lambda kind, payload: self.events.put((kind, payload)), self.cancel)
            except Exception as exc:
                self.events.put(("finished", f"任务失败：{exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def request_cancel(self):
        self.cancel.set()
        self.status.configure(text="正在取消；会在当前网络请求或合并步骤结束后停止。")

    def on_close(self):
        if self.busy:
            self.request_cancel()
            messagebox.showinfo("正在取消", "请等当前任务停止后再关闭，以保留下载进度。")
        else:
            self.destroy()

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "scanned":
                    title, rows = value
                    self.tree.delete(*self.tree.get_children())
                    self.entries = {e.id: e for e in rows}
                    self.selected = set()
                    self.catalog = bool(rows and rows[0].kind == "playlist")
                    for e in rows:
                        self.tree.insert("", "end", iid=e.id, values=("", e.title, "待选择"))
                    self.refresh_checks()
                    self.status.configure(text=f"{title}：读取 {len(rows)} 项。" + ("请选择一个播放列表打开。" if self.catalog else "请勾选要下载的视频。"))
                    self.set_busy(False)
                elif kind == "status":
                    key, result = value
                    self.tree.set(key, "result", result)
                    self.status.configure(text=result)
                elif kind == "progress":
                    self.progress.set(value)
                elif kind == "finished":
                    self.status.configure(text=value)
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.after(100, self.drain)


if __name__ == "__main__":
    ChannelApp().mainloop()
