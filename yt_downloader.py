#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube 高清视频下载器
=====================

功能：输入一个 YouTube 视频链接，自动下载该视频的【最高清晰度】版本
（最佳视频流 + 最佳音频流自动合并，优先输出 mp4，不行则 mkv）。

用法：
    python yt_downloader.py <视频链接> [输出目录]
    python yt_downloader.py <视频链接> --info      # 只预览将选择的清晰度，不下载

示例：
    python yt_downloader.py https://www.youtube.com/watch?v=jNQXAC9IVRw
    python yt_downloader.py https://www.youtube.com/watch?v=xxx D:\我的视频

依赖：
    pip install yt-dlp
    合并高清晰度视频需要 ffmpeg（脚本会自动在本项目 tools 目录或系统 PATH 中查找）
"""

import glob
import importlib.util
import os
import subprocess
import sys

# 让输出统一用 UTF-8 编码，避免在部分终端或重定向下中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ============ 配置区 ============

def _is_frozen():
    """判断是否运行在 PyInstaller 打包后的独立程序里。"""
    return getattr(sys, "frozen", False)


def _resource_dir():
    """
    资源目录：ffmpeg / deno / 主题文件所在位置。
    - 打包后：PyInstaller 会把资源解压到临时目录 sys._MEIPASS
    - 源码运行：就是本文件所在目录
    """
    if _is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


# 资源目录（内置 ffmpeg / deno / 主题）
RESOURCE_DIR = _resource_dir()

# 默认输出目录：
# - 打包后的程序装在 Program Files（只读），所以下载到用户的「下载」文件夹
# - 源码运行时仍下载到项目同级的 downloads 文件夹
if _is_frozen():
    DEFAULT_OUTPUT = os.path.join(os.path.expanduser("~"), "Downloads")
else:
    DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

# 兼容旧代码里对 SCRIPT_DIR 的引用
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg_bin_dir():
    """在资源目录中查找 ffmpeg 的 bin 文件夹；找不到返回 None。"""
    candidates = glob.glob(os.path.join(RESOURCE_DIR, "tools", "ffmpeg-*", "bin")) \
        + glob.glob(os.path.join(RESOURCE_DIR, "tools", "ffmpeg", "bin"))
    return candidates[0] if candidates else None


def find_deno_exe():
    """在资源目录中查找 deno（yt-dlp 的 JS 运行时，用于完整解析清晰度）。
    Windows 上是 deno.exe，macOS/Linux 上是 deno（无扩展名）。"""
    for name in ("deno.exe", "deno"):
        for base in (os.path.join(RESOURCE_DIR, "tools", "deno"),
                     os.path.join(RESOURCE_DIR, "deno")):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
    return None


def build_command(url, output_dir, info_only=False):
    """构造 yt-dlp 命令（返回命令行参数列表）。"""
    # 用当前 Python 解释器运行 yt_dlp 模块，保证用的是同一个环境
    cmd = [sys.executable, "-m", "yt_dlp"]

    # 防止误把整个播放列表下载下来
    cmd += ["--no-playlist"]

    # 断点续传 + 网络重试（--continue 让中断的下载从断点继续）
    cmd += ["--continue", "--retries", "10", "--fragment-retries", "10"]

    if info_only:
        # 模拟下载：只解析链接、打印将选择的格式，不真正下载
        cmd += ["--simulate"]
        cmd += ["--print", "标题: %(title)s"]
        cmd += ["--print", "将选择格式: %(format_id)s  (分辨率 %(resolution)s)"]
    else:
        # 最高清晰度：最佳视频流 + 最佳音频流（如 1080p+ 通常要合并）
        # 合并时优先 mp4 容器，若编码不兼容则自动退回 mkv
        cmd += ["-f", "bestvideo*+bestaudio/best"]
        cmd += ["--merge-output-format", "mp4/mkv"]
        # 输出文件名：视频标题.mp4（yt-dlp 会自动清理非法字符）
        cmd += ["-o", os.path.join(output_dir, "%(title)s.%(ext)s")]

    # 若项目内自带 ffmpeg（绿色版），明确告诉 yt-dlp 用哪个
    ffmpeg_bin = find_ffmpeg_bin_dir()
    if ffmpeg_bin:
        cmd += ["--ffmpeg-location", ffmpeg_bin]

    # 若项目内自带 deno（JS 运行时），交给 yt-dlp 用于完整解析最高清晰度格式
    deno_exe = find_deno_exe()
    if deno_exe:
        cmd += ["--js-runtimes", f"deno:{deno_exe}"]
        # 启用远程"挑战求解"组件（配合 deno 破解 YouTube 的格式签名限制，
        # 否则可能拿不到部分最高清晰度格式；脚本会自动下载并缓存）
        cmd += ["--remote-components", "ejs:github"]

    cmd += [url]
    return cmd


def main():
    # 1) 检查 yt-dlp 是否已安装
    if importlib.util.find_spec("yt_dlp") is None:
        print("[错误] 未安装 yt-dlp，请先运行：")
        print("    python -m pip install yt-dlp")
        return 1

    # 2) 解析命令行参数
    args = [a for a in sys.argv[1:] if a]
    info_only = "--info" in args
    args = [a for a in args if a != "--info"]

    if not args:
        url = input("请输入 YouTube 视频链接: ").strip()
        if not url:
            print("没有输入链接，退出。")
            return 1
    else:
        url = args[0]

    # 输出目录：命令行第二个参数，缺省用默认目录
    output_dir = args[1] if len(args) > 1 else DEFAULT_OUTPUT
    if not info_only:
        os.makedirs(output_dir, exist_ok=True)

    print(f"链接: {url}")
    print(f"输出: {output_dir if not info_only else '(仅预览，不下载)'}")
    print("-" * 60)

    # 3) 调用 yt-dlp 下载（进度条会实时显示）
    cmd = build_command(url, output_dir, info_only)
    # 强制子进程输出 UTF-8，避免在重定向/管道环境下中文乱码
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        result = subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n已取消下载。")
        return 130

    if result.returncode != 0:
        print(f"\n[失败] 下载出错（错误码 {result.returncode}）。")
        print("常见原因：链接无效 / 网络不通 / 该视频不允许下载 / 需要登录。")
        return result.returncode

    if not info_only:
        print(f"\n✅ 下载完成！文件保存在: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
