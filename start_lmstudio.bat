@echo off
REM LM Studio Server Launcher
REM This script provides instructions for starting LM Studio and the inference pipeline

setlocal enabledelayedexpansion

REM Colors for output
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║                                                                ║
echo ║         🚀 LM Studio Inference Pipeline Launcher              ║
echo ║                                                                ║
echo ║     Complete ROCm + LLAMA.cpp Support for AMD GPU             ║
echo ║                                                                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo ┌─ STEP 1: Verify LM Studio is Running ─────────────────────────┐
echo │                                                                │
echo │  1. Open LM Studio application                                │
echo │  2. Go to "Local Server" tab                                  │
echo │  3. Select: deepseek-r1-distill-qwen-70b-q4 (or full)        │
echo │  4. Click "Start Server"                                      │
echo │  5. Verify: "Server running on http://localhost:1234"        │
echo │                                                                │
echo └────────────────────────────────────────────────────────────────┘
echo.

echo ┌─ Testing Connection to LM Studio ─────────────────────────────┐
timeout /t 2 /nobreak
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:1234/v1/models' -TimeoutSec 2; Write-Host '  ✓ LM Studio is running' -ForegroundColor Green } catch { Write-Host '  ✗ Cannot connect to LM Studio' -ForegroundColor Red; Write-Host '    Please start LM Studio and ensure Local Server is running' -ForegroundColor Yellow }" 2>nul
echo │                                                                │
echo └────────────────────────────────────────────────────────────────┘
echo.

echo ┌─ STEP 2: Run Inference Pipeline ──────────────────────────────┐
echo │                                                                │
echo │  Quick test (1 symbol, 1 prompt):                            │
echo │    python src/local_data_pipeline_inference.py -s AAPL       │
echo │                                                                │
echo │  Full batch (30 symbols):                                     │
echo │    python src/local_data_pipeline_inference.py               │
echo │                                                                │
echo │  Custom selection:                                            │
echo │    python src/local_data_pipeline_inference.py -s AAPL JPM   │
echo │                                                                │
echo └────────────────────────────────────────────────────────────────┘
echo.

REM Try to activate venv
echo Activating Python environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo. & echo ✓ Python environment activated
) else (
    echo ⚠ Virtual environment not found at venv\
)

echo.
echo Configuration:
echo   Backend: LM Studio
echo   URL: http://localhost:1234
echo   Expected speed: 15-25 seconds per prompt
echo   Memory: 24GB (Q4) or 140GB (Full)
echo.

echo Ready to run inference! Type the command above or press Enter for demo test.
echo.
pause

REM Run demo test
echo.
echo Launching inference pipeline...
python src/local_data_pipeline_inference.py -s AAPL --max-prompts 1

echo.
echo ✓ Inference test complete!
echo.
pause
