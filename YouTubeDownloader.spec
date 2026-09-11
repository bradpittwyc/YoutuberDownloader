# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

root = Path(SPECPATH)
datas = [(str(root / 'youtube_red.json'), '.')]
binaries = []
for name, destination in [('ffmpeg.exe', 'tools/ffmpeg/bin'), ('deno.exe', 'tools/deno')]:
    matches = list((root / 'tools').rglob(name))
    if not matches:
        raise SystemExit(f'Missing {name}: place the official executable under tools/ before building')
    binaries.append((str(matches[0]), destination))
for probe in (root / 'tools').rglob('ffprobe.exe'):
    binaries.append((str(probe), 'tools/ffmpeg/bin'))
    break
hiddenimports = ['yt_dlp']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(root / 'yt_downloader_gui.py')],
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
    icon=[str(root / 'icon.ico')],
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
