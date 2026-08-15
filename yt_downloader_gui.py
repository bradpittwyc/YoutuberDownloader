#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube 高清视频下载器 - 图形界面版
====================================
基于 CustomTkinter（现代风格深色界面）。
核心下载逻辑复用 yt_downloader.py 里写好的工具函数（ffmpeg / deno 自动查找），
通过 yt-dlp 的 Python API 下载，并把进度实时显示在进度条上。

启动方式：
    双击「启动图形界面.vbs」（无黑窗口），或命令行运行  python yt_downloader_gui.py

自检模式（无界面，用于测试解析是否正常）：
    python yt_downloader_gui.py --selftest <视频链接>
"""

import os
import queue
import subprocess
import sys
import threading
from tkinter import filedialog

# 统一 UTF-8 输出（防止中文乱码）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 复用命令行版里的工具函数（两个文件放在同一目录）
from yt_downloader import (SCRIPT_DIR, RESOURCE_DIR, DEFAULT_OUTPUT,
                           find_ffmpeg_bin_dir, find_deno_exe)

import customtkinter as ctk

# ============ 下载参数构造 ============

def build_ydl_opts(progress_hook):
    """构造 yt-dlp 的 Python API 参数（与命令行版等价）。"""
    opts = {
        # 最高清晰度：最佳视频流 + 最佳音频流
        "format": "bestvideo*+bestaudio/best",
        # 合并时优先 mp4，编码不兼容则自动退回 mkv
        "merge_output_format": "mp4/mkv",
        # 避免误下整个播放列表
        "noplaylist": True,
        # ---- 断点续传 ----
        # continuedl=True：继续下载未完成的部分（断点续传的核心开关）
        "continuedl": True,
        # nopart=False：下载时用 .part 临时文件，中断后下次才能接着下
        "nopart": False,
        # 网络出错自动重试，降低下载中断概率
        "retries": 10,
        "fragment_retries": 10,
        # 由我们自己的进度条展示进度，关掉 yt-dlp 自带的
        "noprogress": True,
        "quiet": True,
        # 进度回调：下载过程中 yt-dlp 会不断调用它
        "progress_hooks": [progress_hook],
    }

    # 项目内自带绿色版 ffmpeg 时，告诉 yt-dlp 用哪个
    ffmpeg_bin = find_ffmpeg_bin_dir()
    if ffmpeg_bin:
        opts["ffmpeg_location"] = ffmpeg_bin

    # 项目内自带 deno（JS 运行时）+ 远程求解组件，保证能拿到最高清晰度格式
    deno_exe = find_deno_exe()
    if deno_exe:
        # 注意：Python API 里 js_runtimes 是 {运行时名: {配置}} 的嵌套字典
        opts["js_runtimes"] = {"deno": {"path": deno_exe}}
        # remote_components 是字符串列表，元素格式为 "组件:来源"
        opts["remote_components"] = ["ejs:github"]

    return opts


# ============ 主窗口 ============

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")          # 深色主题
        # 自定义 YouTube 红黑配色主题
        ctk.set_default_color_theme(os.path.join(RESOURCE_DIR, "youtube_red.json"))

        self.title("YouTube 高清视频下载器")
        self.geometry("680x620")
        self.resizable(False, False)
        self.configure(fg_color="#0F0F0F")       # YouTube 深色背景

        # 线程安全的消息队列：后台线程只能往队列里放消息，
        # 由主线程定时取出刷新界面（tkinter 不允许跨线程操作控件）
        self.msg_queue = queue.Queue()

        self._build_widgets()

        # 窗口高度贴合内容，去掉状态文字下方的大片空白。
        # 高分屏下 Windows 会把窗口整体放大，Tk 的几何值是逻辑像素，
        # 这里按「物理高度 / 逻辑高度」的比值换算，把高度收窄到刚好装下内容。
        self.update()
        try:
            init_h = int(self.geometry().split("x")[1].split("+")[0])
            scale = self.winfo_height() / init_h
            fit_h = int((self.winfo_reqheight() + 24) / scale)
            self.geometry(f"680x{fit_h}")
        except Exception:
            pass

        # 定时器：每 100ms 检查一次队列，刷新界面
        self.after(100, self._drain_queue)

    # ---------- 界面布局 ----------
    def _build_widgets(self):
        self.grid_columnconfigure(0, weight=1)

        # 顶部红色条（YouTube 风格点缀）
        topbar = ctk.CTkFrame(self, height=5, fg_color="#FF0000", corner_radius=0)
        topbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        topbar.grid_propagate(False)

        ctk.CTkLabel(self, text="▶ YouTube 高清视频下载器",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#FFFFFF").grid(row=1, column=0, columnspan=3, pady=(16, 4))
        ctk.CTkLabel(self, text="自动下载最高清晰度（视频+音频合并，支持断点续传）",
                     font=ctk.CTkFont(size=12), text_color="#AAAAAA").grid(
            row=2, column=0, columnspan=3)

        # 表单区：三列布局 [说明文字 | 输入框 | 按钮]
        # 两个输入框都在第 1 列（可伸缩），因此长度完全一致
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=3, column=0, columnspan=3, padx=24, pady=(16, 6), sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        # 链接行
        ctk.CTkLabel(form, text="视频链接", width=64, anchor="w",
                     font=ctk.CTkFont(size=13), text_color="#AAAAAA").grid(
            row=0, column=0, padx=(0, 10), sticky="w")
        self.url_entry = ctk.CTkEntry(
            form, placeholder_text="在此粘贴视频链接，如 https://www.youtube.com/watch?v=xxx",
            height=36, font=ctk.CTkFont(size=13))
        self.url_entry.grid(row=0, column=1, sticky="ew")

        # 目录行
        ctk.CTkLabel(form, text="保存目录", width=64, anchor="w",
                     font=ctk.CTkFont(size=13), text_color="#AAAAAA").grid(
            row=1, column=0, padx=(0, 10), pady=(10, 0), sticky="w")
        self.dir_entry = ctk.CTkEntry(form, height=36, font=ctk.CTkFont(size=13))
        self.dir_entry.insert(0, DEFAULT_OUTPUT)
        self.dir_entry.grid(row=1, column=1, pady=(10, 0), sticky="ew")
        ctk.CTkButton(form, text="选择目录", width=92, command=self.choose_dir,
                      fg_color="#272727", hover_color="#3F3F3F",
                      text_color="#FFFFFF").grid(row=1, column=2, padx=(10, 0), pady=(10, 0))

        # 操作按钮行（已移除「预览清晰度」按钮）
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=4, column=0, columnspan=3, pady=(6, 4))
        self.download_btn = ctk.CTkButton(btn_row, text="⬇ 开始下载", width=220,
                                          height=40, command=self.start_download,
                                          font=ctk.CTkFont(size=15, weight="bold"),
                                          fg_color="#FF0000", hover_color="#CC0000",
                                          text_color="#FFFFFF")
        self.download_btn.grid(row=0, column=0, padx=6)
        ctk.CTkButton(btn_row, text="打开下载目录", width=140,
                      command=self.open_dir,
                      fg_color="#272727", hover_color="#3F3F3F",
                      text_color="#FFFFFF").grid(row=0, column=1, padx=6)

        # 进度条（红色）
        self.progress = ctk.CTkProgressBar(self, width=620, height=16,
                                           progress_color="#FF0000", fg_color="#2A2A2A")
        self.progress.set(0)
        self.progress.grid(row=5, column=0, columnspan=3, padx=24, pady=(6, 2))

        self.status_label = ctk.CTkLabel(self, text="就绪", font=ctk.CTkFont(size=12),
                                         text_color="#AAAAAA")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=(0, 2))

        # 日志区（高度收紧，减少底部空白）
        self.log_box = ctk.CTkTextbox(self, height=120, font=ctk.CTkFont(size=12))
        self.log_box.grid(row=7, column=0, columnspan=3, padx=24, pady=(2, 10), sticky="ew")
        self.log_box.insert("end", "欢迎使用！粘贴链接后点击「开始下载」。\n")

    # ---------- 界面事件 ----------
    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_entry.get() or DEFAULT_OUTPUT)
        if d:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, d)

    def open_dir(self):
        d = self.dir_entry.get().strip() or DEFAULT_OUTPUT
        os.makedirs(d, exist_ok=True)
        # 跨平台打开文件夹：Windows 用 startfile，macOS 用 open
        if sys.platform == "darwin":
            subprocess.run(["open", d])
        elif sys.platform == "win32":
            os.startfile(d)
        else:
            subprocess.run(["xdg-open", d])

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.log("⚠️  请先粘贴视频链接！")
            return
        outdir = self.dir_entry.get().strip() or DEFAULT_OUTPUT
        os.makedirs(outdir, exist_ok=True)

        self.download_btn.configure(state="disabled", text="下载中...")
        self.progress.set(0)
        self.log("=" * 50)
        self.log(f"开始下载：{url}")
        self.log("已启用断点续传：若之前中断过，会自动从断点继续")

        # 下载放到后台线程，避免卡住界面
        threading.Thread(target=self._worker, args=(url, outdir), daemon=True).start()

    # ---------- 后台线程（不能直接操作控件，只能往队列发消息） ----------
    def _worker(self, url, outdir):
        def hook(d):
            # 进度回调：把消息放进队列，主线程会取走并刷新界面
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                got = d.get("downloaded_bytes", 0)
                if total:
                    self.msg_queue.put(("progress", got / total))
                    self.msg_queue.put(("status",
                        f"下载中 {d.get('_percent_str', f'{got/total*100:.1f}%')}  "
                        f"{d.get('_speed_str', '')}  剩余 {d.get('_eta_str', '')}"))
            elif status == "finished":
                self.msg_queue.put(("status", "正在合并音视频（ffmpeg）..."))
                self.msg_queue.put(("log", "片段下载完成，正在合并音视频..."))

        opts = build_ydl_opts(hook)
        opts["outtmpl"] = os.path.join(outdir, "%(title)s.%(ext)s")
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(opts) as ydl:
                self.msg_queue.put(("log", "正在解析视频信息..."))
                info = ydl.extract_info(url, download=True)
            title = info.get("title", url)
            self.msg_queue.put(("progress", 1.0))
            self.msg_queue.put(("done", f"✅ 下载完成：{title}"))
        except Exception as e:
            self.msg_queue.put(("done", f"❌ 下载失败：{e}"))

    # ---------- 主线程：取出队列消息刷新界面 ----------
    def log(self, msg):
        self.msg_queue.put(("log", msg))

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self.log_box.insert("end", payload + "\n")
                    self.log_box.see("end")
                elif kind == "progress":
                    self.progress.set(payload)
                elif kind == "status":
                    self.status_label.configure(text=payload)
                elif kind == "done":
                    self.status_label.configure(text=payload)
                    self.download_btn.configure(state="normal", text="⬇ 开始下载")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)


# ============ 入口 ============

if __name__ == "__main__":
    # 自检模式：不弹窗口，验证 yt-dlp 解析是否正常（供测试用）
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        url = sys.argv[2]
        import yt_dlp
        opts = build_ydl_opts(lambda d: None)
        opts["quiet"] = False
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        print(f"标题: {info.get('title')}")
        print(f"最高分辨率: {info.get('resolution')}")
        heights = sorted({f.get("height") for f in (info.get("formats") or []) if f.get("height")}, reverse=True)
        print("可选分辨率: " + ", ".join(f"{h}p" for h in heights[:6]) if heights else "未知")
        sys.exit(0)

    app = DownloaderApp()
    try:
        app.mainloop()
    except Exception:
        # pythonw/打包后没有控制台，报错信息写到文件里方便排查
        import traceback
        log_path = os.path.join(os.path.expanduser("~"), "yt_downloader_error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        from tkinter import messagebox
        messagebox.showerror("程序出错", f"发生错误，详情已保存到:\n{log_path}")
