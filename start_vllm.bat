@echo off
REM vLLM启动脚本 - Windows批处理版本（推荐）
REM 用法: .\start_vllm.bat 或双击运行

setlocal enabledelayedexpansion

cls
echo.
echo ========================================
echo vLLM Server Launcher (DeepSeek-R1:70b)
echo ========================================
echo.

REM 检查WSL2
echo [INFO] Checking WSL2...
wsl --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] WSL2 not found!
    echo [HINT] Install WSL2: wsl --install Ubuntu-22.04
    pause
    exit /b 1
)
echo [OK] WSL2 is ready
echo.

REM 启动vLLM（简单直接）
echo [INFO] Starting vLLM in WSL2...
echo [HINT] Look for "WSL2 IP:" in output below to find your IP address
echo.

REM 直接调用WSL2内的bash脚本
wsl bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh

echo.
echo [INFO] vLLM has stopped
echo.
pause

