#!/bin/bash
# ====================================================================
# 修复 PyTorch: 从 CUDA 版切换到 ROCm 版
# 针对 AMD AI Max 395+ / WSL2
#
# 问题: PyTorch 2.9.1+cu128 (CUDA) -> 需要 ROCm 版
# 原因: AMD 官方 ROCm wheels 只有 cp310/cp312, 没有 cp311
#
# 方案: 检测 Python 版本, 选择最佳安装方式
# ====================================================================

set -e

CONDA_ENV="trading_ai_py311"

echo "========================================================================"
echo " PyTorch ROCm 修复脚本 - AMD AI Max 395+"
echo "========================================================================"

# 初始化 conda
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source "/opt/conda/etc/profile.d/conda.sh"
else
    eval "$(conda shell.bash hook)"
fi

conda activate "$CONDA_ENV"

echo ""
echo "[CHECK] 当前环境信息:"
echo "  Conda env: $CONDA_ENV"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_FULL=$(python3 --version)
echo "  Python: $PYTHON_FULL"
echo "  当前 PyTorch: $(python3 -c 'import torch; print(torch.__version__)' 2>/dev/null || echo '未安装')"
echo ""

# ====================================================================
# 检查 Python 版本, 决定安装策略
# ====================================================================

if [ "$PYTHON_VERSION" = "3.10" ]; then
    echo "[INFO] Python 3.10 → 使用 AMD 官方 ROCm wheels (最佳)"
    INSTALL_METHOD="amd_official"
    CP_TAG="cp310"

elif [ "$PYTHON_VERSION" = "3.12" ]; then
    echo "[INFO] Python 3.12 → 使用 AMD 官方 ROCm wheels (最佳)"
    INSTALL_METHOD="amd_official"
    CP_TAG="cp312"

elif [ "$PYTHON_VERSION" = "3.11" ]; then
    echo "[WARNING] Python 3.11 → AMD 官方没有 cp311 wheels"
    echo ""
    echo "  你有两个选择:"
    echo ""
    echo "  [1] 创建新的 conda env (Python 3.12) 使用 AMD 官方 wheels (推荐)"
    echo "      - 最稳定，AMD 官方测试过"
    echo "      - 需要重新安装 LlamaFactory 等依赖"
    echo ""
    echo "  [2] 尝试 PyTorch.org 的 ROCm wheels (py311)"
    echo "      - 保留现有 conda env"
    echo "      - AMD 声明这些 wheels 未经其全面测试"
    echo "      - 可能可以工作"
    echo ""
    read -p "请选择 [1/2]: " CHOICE

    if [ "$CHOICE" = "1" ]; then
        INSTALL_METHOD="new_env"
    else
        INSTALL_METHOD="pytorch_org"
    fi
else
    echo "[ERROR] 不支持的 Python 版本: $PYTHON_VERSION"
    echo "        需要 Python 3.10 或 3.12"
    exit 1
fi

# ====================================================================
# 方案 1: AMD 官方 wheels (Python 3.10/3.12)
# ====================================================================
if [ "$INSTALL_METHOD" = "amd_official" ]; then
    echo ""
    echo "[STEP 1] 下载 AMD 官方 ROCm 7.2 wheels..."
    
    WHEEL_DIR="/tmp/rocm_wheels"
    mkdir -p "$WHEEL_DIR"
    cd "$WHEEL_DIR"
    
    BASE_URL="https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2"
    
    echo "  下载 torch (~2GB, 请耐心等待)..."
    wget --progress=bar:force "${BASE_URL}/torch-2.9.1%2Brocm7.2.0.lw.git7e1940d4-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torch.whl
    echo "  下载 torchvision..."
    wget --progress=bar:force "${BASE_URL}/torchvision-0.24.0%2Brocm7.2.0.gitb919bd0c-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torchvision.whl
    echo "  下载 torchaudio..."
    wget --progress=bar:force "${BASE_URL}/torchaudio-2.9.0%2Brocm7.2.0.gite3c6ee2b-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torchaudio.whl
    echo "  下载 triton..."
    wget --progress=bar:force "${BASE_URL}/triton-3.5.1%2Brocm7.2.0.gita272dfa8-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O triton.whl
    
    echo ""
    echo "[STEP 2] 卸载旧版 PyTorch..."
    pip3 uninstall -y torch torchvision triton torchaudio 2>/dev/null || true
    
    echo ""
    echo "[STEP 3] 安装 ROCm 版 PyTorch..."
    pip3 install torch.whl torchvision.whl torchaudio.whl triton.whl
    
    echo ""
    echo "[STEP 4] 修复 numpy 兼容性..."
    pip3 install "numpy==1.26.4"
    
    echo ""
    echo "[STEP 5] 更新 WSL2 兼容运行时库..."
    TORCH_LIB=$(python3 -c "import torch; import os; print(os.path.join(os.path.dirname(torch.__file__), 'lib'))")
    echo "  torch lib: $TORCH_LIB"
    if [ -d "$TORCH_LIB" ]; then
        cd "$TORCH_LIB"
        rm -f libhsa-runtime64.so*
        echo "  ✓ 已移除 bundled libhsa-runtime64.so (使用系统 ROCm 版)"
    fi
    
    # 清理下载的 wheels
    rm -rf "$WHEEL_DIR"

# ====================================================================
# 方案 2: 创建新 conda env (Python 3.12)
# ====================================================================
elif [ "$INSTALL_METHOD" = "new_env" ]; then
    NEW_ENV="trading_ai_py312"
    echo ""
    echo "[INFO] 创建新 conda 环境: $NEW_ENV (Python 3.12)"
    
    conda create -n "$NEW_ENV" python=3.12 -y
    conda activate "$NEW_ENV"
    
    echo ""
    echo "[STEP 1] 下载 AMD 官方 ROCm wheels..."
    
    WHEEL_DIR="/tmp/rocm_wheels"
    mkdir -p "$WHEEL_DIR"
    cd "$WHEEL_DIR"
    
    BASE_URL="https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2"
    CP_TAG="cp312"
    
    echo "  下载 torch (~2GB)..."
    wget --progress=bar:force "${BASE_URL}/torch-2.9.1%2Brocm7.2.0.lw.git7e1940d4-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torch.whl
    echo "  下载 torchvision..."
    wget --progress=bar:force "${BASE_URL}/torchvision-0.24.0%2Brocm7.2.0.gitb919bd0c-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torchvision.whl
    echo "  下载 torchaudio..."
    wget --progress=bar:force "${BASE_URL}/torchaudio-2.9.0%2Brocm7.2.0.gite3c6ee2b-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O torchaudio.whl
    echo "  下载 triton..."
    wget --progress=bar:force "${BASE_URL}/triton-3.5.1%2Brocm7.2.0.gita272dfa8-${CP_TAG}-${CP_TAG}-linux_x86_64.whl" -O triton.whl
    
    pip3 install torch.whl torchvision.whl torchaudio.whl triton.whl
    pip3 install "numpy==1.26.4"
    
    echo ""
    echo "[STEP 2] 更新 WSL2 兼容运行时库..."
    TORCH_LIB=$(python3 -c "import torch; import os; print(os.path.join(os.path.dirname(torch.__file__), 'lib'))")
    cd "$TORCH_LIB"
    rm -f libhsa-runtime64.so*
    
    echo ""
    echo "[STEP 3] 安装 LlamaFactory 及依赖..."
    pip3 install "llamafactory[torch,metrics]"
    pip3 install wandb accelerate peft bitsandbytes
    pip3 install "transformers>=4.51.0"
    
    # GCC 12.1+ for conda (避免 GLIBCXX 错误)
    conda install -c conda-forge gcc=12.1.0 -y
    
    rm -rf "$WHEEL_DIR"
    
    echo ""
    echo "========================================================================"
    echo "[INFO] 新环境 $NEW_ENV 已创建！"
    echo "       后续使用请改为: conda activate $NEW_ENV"
    echo "       训练脚本中的 CONDA_ENV 也需要改为 $NEW_ENV"
    echo "========================================================================"

# ====================================================================
# 方案 3: PyTorch.org ROCm wheels (Python 3.11)
# ====================================================================
elif [ "$INSTALL_METHOD" = "pytorch_org" ]; then
    echo ""
    echo "[WARNING] 使用 PyTorch.org wheels (AMD 未全面测试)"
    echo ""
    
    echo "[STEP 1] 卸载 CUDA 版 PyTorch..."
    pip3 uninstall -y torch torchvision torchaudio 2>/dev/null || true
    
    echo ""
    echo "[STEP 2] 安装 ROCm 版 PyTorch (from pytorch.org)..."
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.3
    
    echo ""
    echo "[STEP 3] 更新 WSL2 兼容运行时库..."
    TORCH_LIB=$(python3 -c "import torch; import os; print(os.path.join(os.path.dirname(torch.__file__), 'lib'))" 2>/dev/null)
    if [ -n "$TORCH_LIB" ] && [ -d "$TORCH_LIB" ]; then
        cd "$TORCH_LIB"
        rm -f libhsa-runtime64.so*
        echo "  ✓ 已移除 bundled libhsa-runtime64.so"
    fi
fi

# ====================================================================
# 设置 ROCm 环境变量
# ====================================================================
echo ""
echo "[ENV] 设置 AMD AI Max 395+ ROCm 环境变量..."
export HSA_OVERRIDE_GFX_VERSION=11.5.0
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
export GPU_MAX_HEAP_SIZE=100
export GPU_MAX_ALLOC_PERCENT=100
export HIP_VISIBLE_DEVICES=0

# ====================================================================
# 验证
# ====================================================================
echo ""
echo "========================================================================"
echo "[VERIFY] 验证 PyTorch ROCm 安装"
echo "========================================================================"

python3 << 'PYEOF'
import torch
print(f"PyTorch version: {torch.__version__}")

if "rocm" in torch.__version__.lower() or "hip" in str(getattr(torch, '_C', '')):
    print("✓ ROCm 版本确认")
elif "cu" in torch.__version__:
    print("✗ 仍然是 CUDA 版本！安装失败")
else:
    print(f"? 版本标识: {torch.__version__}")

print(f"CUDA/ROCm available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"Memory: {mem:.1f} GB")
    print("\n✓ GPU 检测成功！可以开始训练了")
else:
    print("\n✗ GPU 未检测到")
    print("  可能原因:")
    print("  1. Windows 驱动未安装: 需要 AMD Adrenalin Edition 26.1.1+")
    print("  2. ROCm 未安装在 WSL2 中")
    print("  3. HSA_OVERRIDE_GFX_VERSION 设置不正确")
    print("  4. /dev/dri/renderD128 设备不存在")
    print()
    import os
    print(f"  HSA_OVERRIDE_GFX_VERSION = {os.environ.get('HSA_OVERRIDE_GFX_VERSION', '未设置')}")
    
    import subprocess
    result = subprocess.run(["ls", "/dev/dri/"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  /dev/dri/ 内容: {result.stdout.strip()}")
    else:
        print("  /dev/dri/ 目录不存在！GPU 设备未暴露给 WSL2")
PYEOF

echo ""
echo "========================================================================"
