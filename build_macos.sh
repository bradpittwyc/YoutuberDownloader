#!/bin/bash
# ============================================================
# macOS Intel (x86_64) 构建脚本
# 在 GitHub Actions 的 arm64 macOS 构建机上，用 Rosetta 模拟 x86_64
# 构建出能在 Intel Mac 上运行的 .app 和 .dmg。
#
# 用法：在 GitHub Actions 里执行  bash build_macos.sh
# ============================================================
set -e

APP_NAME="YouTubeDownloader"
PY_VERSION="3.12.10"

# 版本号：从 Git 标签取（如 v1.0.2 -> 1.0.2），手动触发时默认 1.0.0
APP_VERSION="${GITHUB_REF_NAME#v}"
APP_VERSION="${APP_VERSION:-1.0.0}"

# ---------- 1) 安装 x86_64 Python（python.org 官方安装包为 universal2，
#             经 arch -x86_64 运行时走 x86_64 分支） ----------
echo "=== [1/6] 安装 x86_64 Python ${PY_VERSION} ==="
curl -fSL -o /tmp/python.pkg "https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-macos11.pkg"
sudo installer -pkg /tmp/python.pkg -target /
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

echo "=== 验证架构（应为 x86_64） ==="
arch -x86_64 "$PYTHON" -c "import platform; print('架构:', platform.machine())"

# ---------- 2) 安装依赖 ----------
echo "=== [2/6] 安装 Python 依赖 ==="
arch -x86_64 "$PYTHON" -m pip install --upgrade pip -q
arch -x86_64 "$PYTHON" -m pip install -q pyinstaller customtkinter yt-dlp pillow

# ---------- 3) 下载 Intel (x86_64) 版 ffmpeg 和 deno ----------
echo "=== [3/6] 下载 ffmpeg (Intel macOS) ==="
mkdir -p tools/ffmpeg/bin
curl -fSL -o /tmp/ffmpeg.zip "https://evermeet.cx/ffmpeg/getrelease/zip"
unzip -o /tmp/ffmpeg.zip -d tools/ffmpeg/bin
curl -fSL -o /tmp/ffprobe.zip "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
unzip -o /tmp/ffprobe.zip -d tools/ffmpeg/bin
chmod +x tools/ffmpeg/bin/ffmpeg tools/ffmpeg/bin/ffprobe

echo "=== 下载 deno (x86_64-apple-darwin) ==="
mkdir -p tools/deno
curl -fSL -o /tmp/deno.zip "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-apple-darwin.zip"
unzip -o /tmp/deno.zip -d tools/deno
chmod +x tools/deno/deno

# ---------- 4) 生成 macOS 图标 ----------
echo "=== [4/6] 生成 icon.icns ==="
arch -x86_64 "$PYTHON" make_icns.py

# ---------- 5) PyInstaller 打包（macOS 上 --add-binary 分隔符是冒号） ----------
echo "=== [5/6] PyInstaller 打包 ==="
arch -x86_64 "$PYTHON" -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name "$APP_NAME" \
  --icon icon.icns \
  --add-data "youtube_red.json:." \
  --add-binary "tools/ffmpeg/bin/ffmpeg:tools/ffmpeg/bin" \
  --add-binary "tools/ffmpeg/bin/ffprobe:tools/ffmpeg/bin" \
  --add-binary "tools/deno/deno:tools/deno" \
  --collect-all customtkinter \
  --hidden-import yt_dlp \
  yt_downloader_gui.py

# ---------- 6) ad-hoc 签名（没有 Apple 开发者证书时的最佳实践：
#             可减少 Gatekeeper 的"无法验证开发者"硬拦截） ----------
echo "=== [6/7] ad-hoc 签名 ==="
codesign --force --deep --sign - "dist/$APP_NAME.app"

# ---------- 7) 打包成 .dmg ----------
echo "=== [7/8] 生成 DMG ==="
mkdir -p dist/dmg
cp -R "dist/$APP_NAME.app" dist/dmg/
hdiutil create -volname "$APP_NAME" -srcfolder dist/dmg -ov -format UDZO "dist/${APP_NAME}-macOS-Intel.dmg"

# ---------- 8) 生成 .pkg 安装包（原生安装器：双击 → 输管理员密码 →
#              自动安装到 /Applications，Launchpad 自动可见） ----------
echo "=== [8/8] 生成 PKG ==="
pkgbuild --component "dist/$APP_NAME.app" \
  --install-location /Applications \
  --identifier "com.bradpittwyc.youtubedownloader" \
  --version "$APP_VERSION" \
  "dist/${APP_NAME}-macOS-Intel.pkg"

echo ""
echo "✅ 构建完成！产物："
echo "   dist/${APP_NAME}-macOS-Intel.dmg"
echo "   dist/${APP_NAME}-macOS-Intel.pkg"
