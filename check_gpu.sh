#!/bin/bash
# GPU 和 ROCm 诊断脚本
# 用法: bash check_gpu.sh

echo "========================================"
echo "GPU & ROCm Diagnostic Tool"
echo "========================================"
echo ""

# 检查WSL2
echo "[1] Checking WSL2..."
if [ -f "/proc/version" ]; then
    grep -i microsoft /proc/version >/dev/null 2>&1 && echo "✓ Running in WSL2" || echo "✗ Not WSL2"
else
    echo "✗ Not WSL2"
fi
echo ""

# 检查ROCm安装
echo "[2] Checking ROCm Installation..."
if command -v rocm-smi &> /dev/null; then
    echo "✓ rocm-smi found"
    rocm-smi
    echo ""
else
    echo "✗ rocm-smi not found"
    echo "  Run: apt install rocm-dkms"
fi
echo ""

# 检查GPU驱动
echo "[3] Checking GPU Drivers..."
if [ -d "/dev/dri" ]; then
    echo "✓ GPU devices found:"
    ls -la /dev/dri/
else
    echo "✗ No GPU devices found in /dev/dri"
fi
echo ""

# 检查HIP
echo "[4] Checking HIP (GPU API)..."
if command -v hipconfig &> /dev/null; then
    echo "✓ HIP found"
    hipconfig --version
    hipconfig --gpu-detect
else
    echo "✗ HIP not found"
    echo "  Run: apt install hip-runtime-amd"
fi
echo ""

# 检查vLLM
echo "[5] Checking vLLM Installation..."
if python -c "import vllm" 2>/dev/null; then
    echo "✓ vLLM installed"
    python -c "import vllm; print('  Version:', vllm.__version__)"
else
    echo "✗ vLLM not installed"
    echo "  Run: pip install vllm[rocm]"
fi
echo ""

# 检查Python版本
echo "[6] Checking Python..."
python3 --version
echo ""

# 检查环境变量
echo "[7] Environment Variables..."
echo "  HSA_OVERRIDE_GFX_VERSION: $HSA_OVERRIDE_GFX_VERSION"
echo "  GPU_DEVICE_ORDINAL: $GPU_DEVICE_ORDINAL"
echo "  VLLM_DEVICE: $VLLM_DEVICE"
echo ""

# 总结
echo "========================================"
echo "Diagnostic Summary:"
echo "========================================"
echo ""

HAS_ISSUE=0

if ! command -v rocm-smi &> /dev/null; then
    echo "⚠️  ROCm not installed"
    HAS_ISSUE=1
fi

if ! python -c "import vllm" 2>/dev/null; then
    echo "⚠️  vLLM not installed"
    HAS_ISSUE=1
fi

if [ $HAS_ISSUE -eq 0 ]; then
    echo "✓ All checks passed! vLLM should work."
else
    echo "✗ Issues found. See above."
fi
echo ""
