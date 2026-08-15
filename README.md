# YouTube 高清视频下载器

一个简单易用的 Python 程序：输入 YouTube 视频链接，自动下载**最高清晰度**版本
（视频流 + 音频流自动合并，优先输出 mp4）。

**两种使用方式：**

| 方式 | 入口 | 适合场景 |
|------|------|----------|
| 🖥️ 图形界面 | 双击 **`启动图形界面.vbs`**（无黑窗口） | 日常使用，有进度条、选目录、日志 |
| ⌨️ 命令行 | 双击 **`run.bat`** 或 `python yt_downloader.py` | 快速下载、脚本调用 |

## 图形界面用法

1. 双击 `启动图形界面.vbs` —— 用 `pythonw` 静默启动，**不会弹出黑色命令行窗口**
   （`启动图形界面.bat` 为备用启动方式）
2. 粘贴视频链接，可点「选择目录」改保存位置
3. 点「⬇ 开始下载」，进度条实时显示进度，支持**断点续传**
4. 完成后点「打开下载目录」查看文件

> 如果界面异常退出，错误详情会保存在用户主目录下的 `yt_downloader_error.log` 文件中。

## 安装到 Windows（独立 exe，免 Python 环境）

打包后的独立程序安装在：
`%LOCALAPPDATA%\Programs\YouTubeDownloader`

- **开始菜单** → 搜索「YouTube」即可启动
- 桌面也会创建快捷方式
- 卸载：开始菜单或桌面 → 双击「卸载」，或在 Windows「设置 → 应用」里卸载

重新打包（换机器后）：

```bat
python -m pip install pyinstaller pillow yt-dlp
python make_icon.py
python -m PyInstaller --noconfirm --windowed --onedir ^
  --name YouTubeDownloader --icon icon.ico ^
  --add-data "youtube_red.json;." ^
  --add-binary "tools\ffmpeg-*\bin\ffmpeg.exe;tools\ffmpeg\bin" ^
  --add-binary "tools\ffmpeg-*\bin\ffprobe.exe;tools\ffmpeg\bin" ^
  --add-binary "tools\deno\deno.exe;tools\deno" ^
  --collect-all customtkinter --hidden-import yt_dlp yt_downloader_gui.py
```

## 命令行用法

```bat
python yt_downloader.py https://www.youtube.com/watch?v=jNQXAC9IVRw
python yt_downloader.py https://www.youtube.com/watch?v=xxx D:\我的视频
python yt_downloader.py https://www.youtube.com/watch?v=xxx --info
```

- 第二个参数：自定义输出目录（可选）
- `--info`：只预览将选择的清晰度，不实际下载

## 原理（学习要点）

| 组件 | 作用 |
|------|------|
| **yt-dlp** | 从 YouTube 提取视频/音频流地址并下载 |
| **ffmpeg** | 把分离的视频流和音频流合并成一个文件 |
| **deno** | JS 运行时，帮助 yt-dlp 完整解析最高清晰度格式 |
| `-f bestvideo*+bestaudio` | 选择最高质量的视频流+音频流（1080p 以上通常分开发布） |

`ffmpeg` 和 `deno` 都放在本项目 `tools` 目录里（绿色版，程序启动时自动查找并调用），
无需手动安装到系统。

为什么需要 ffmpeg？YouTube 的高清视频（1080p+）把**画面**和**声音**分成两个独立
文件发布，下载后必须用 ffmpeg 合并，否则只有画面没有声音。

## 依赖安装（如换电脑需要重新安装）

```bat
python -m pip install yt-dlp
```

ffmpeg 放在本项目 `tools` 目录里（绿色版，脚本自动查找），或安装到系统 PATH 中均可。

## macOS（Intel x86_64）安装版

**为什么不能直接在 Windows 上构建？** PyInstaller 不支持跨平台交叉编译，
macOS 程序必须在 macOS 上构建。本项目的 macOS 构建已做成**一条龙自动流水线**
（GitHub Actions），Intel 版通过「arm64 构建机 + Rosetta 模拟 x86_64」实现。

**使用方法：**

1. 把本项目推到你的 GitHub 仓库
2. 仓库页面 → **Actions** → 选 **Build macOS Intel** → **Run workflow**
3. 几分钟后构建完成，在 Actions 运行页下载 `YouTubeDownloader-macOS-Intel.dmg`
4. 双击 .dmg 把 App 拖入「应用程序」即可（首次打开如提示未验证，右键 → 打开）

相关文件：`build_macos.sh`（构建脚本）、`.github/workflows/build-macos.yml`（工作流）、
`make_icns.py`（macOS 图标生成）。

> 说明：GitHub 已于 2025-2026 年停用 Intel 构建机（macos-13），
> 因此 Intel 版使用 Rosetta 方案在 arm64 构建机上交叉构建；
> 如果不需要兼容老款 Intel Mac，也可以把 `runs-on` 改成 `macos-14` 直接构建 Apple Silicon 版。

**首次打开被 Gatekeeper 拦截（"Apple 无法验证此 App 不含恶意软件"）怎么办？**

这是无 Apple 开发者签名的正常现象。任选其一：

```bash
# 方法一：解除隔离标记（最推荐）
xattr -d com.apple.quarantine /Applications/YouTubeDownloader.app
open /Applications/YouTubeDownloader.app

# 方法二：如果提示"已损坏/无法打开"，先重新签名再打开
codesign --force --deep --sign - /Applications/YouTubeDownloader.app
```

或：系统设置 → 隐私与安全性 → 底部「仍要打开」。构建流水线已内置 ad-hoc 签名，
可减少此类拦截；要彻底消除需 Apple 开发者账号 + 公证（Notarization）。

## 常见问题

- **下载报错 / 网络错误**：YouTube 在某些地区无法直接访问，需要科学上网后重试。
- **提示"视频不可用"**：该视频可能被删除、设为私密，或禁止下载。
- **下载的是 mkv 而不是 mp4**：某些视频编码（如 VP9/Opus）与 mp4 容器不兼容，
  程序会自动改用 mkv，属正常现象。
