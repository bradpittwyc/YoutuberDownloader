#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包后的验证入口（控制台版）：复用 GUI 的下载参数，实际解析一个视频，
用来验证 PyInstaller 打包后 yt-dlp / ffmpeg / deno 都能正常工作。

用法：YouTubeDownloader_verify.exe <视频链接>
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from yt_downloader_gui import build_ydl_opts  # noqa: E402
import yt_dlp  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("用法: verify.exe <视频链接>")
        return 1
    url = sys.argv[1]
    opts = build_ydl_opts(lambda d: None)
    opts["quiet"] = False
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    print(f"OK|标题: {info.get('title')}|分辨率: {info.get('resolution')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
