# vLLM 启动脚本 - PowerShell 版本（Windows -> WSL2）
# 简化版：直接调用WSL2内的bash脚本
# 使用：.\vllm_startup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "vLLM Server Startup (DeepSeek-R1:70b)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查WSL2是否安装
Write-Host "[INFO] Checking WSL2 installation..." -ForegroundColor Yellow
$result = wsl --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] WSL2 not found!" -ForegroundColor Red
    Write-Host "[HINT] Run: wsl --install Ubuntu-22.04" -ForegroundColor Yellow
    exit 1
}
Write-Host "[SUCCESS] WSL2 is installed" -ForegroundColor Green
Write-Host ""

# 在WSL2内执行启动脚本
Write-Host "[INFO] Starting vLLM in WSL2..." -ForegroundColor Yellow
Write-Host "[HINT] Look for 'WSL2 IP:' in the output below" -ForegroundColor Yellow
Write-Host ""

# 直接调用WSL2内的bash脚本
wsl bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh

Write-Host ""
Write-Host "[INFO] vLLM server stopped" -ForegroundColor Yellow
