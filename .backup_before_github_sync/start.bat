@echo off
title TTS 音频库
cd /d "%~dp0"

echo ====================================
echo   TTS 音频库 正在启动...
echo   启动后浏览器将自动打开
echo   关闭本窗口即停止服务
echo ====================================
echo.

start "" "http://127.0.0.1:5000"
python app.py

if errorlevel 1 (
    echo.
    echo [错误] 启动失败。请确认已安装 Python 3 并已执行: pip install flask
    pause
)
