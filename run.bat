@echo off
rem ============================================
rem  YouTube downloader - command line version
rem  Usage:  python yt_downloader.py <URL> [dir]
rem ============================================
chcp 65001 >nul
cd /d "%~dp0"
python yt_downloader.py %*
echo.
pause
