# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:/Projects/DS Harness/yt-downloader/youtube_red.json', '.')]
binaries = [('D:/Projects/DS Harness/yt-downloader/tools/ffmpeg-9.0.1-essentials_build/bin/ffmpeg.exe', 'tools/ffmpeg/bin'), ('D:/Projects/DS Harness/yt-downloader/tools/ffmpeg-9.0.1-essentials_build/bin/ffprobe.exe', 'tools/ffmpeg/bin'), ('D:/Projects/DS Harness/yt-downloader/tools/deno/deno.exe', 'tools/deno')]
hiddenimports = ['yt_dlp']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/Projects/DS Harness/yt-downloader/yt_downloader_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/Projects/DS Harness/yt-downloader/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeDownloader',
)
