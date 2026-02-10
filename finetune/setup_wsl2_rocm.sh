#!/bin/bash
# ====================================================================
# WSL2 + ROCm 环境安装脚本
# 硬件: AMD AI Max 395+ 128GB
# ====================================================================

set -e

# ====================================================================
# WSL2 路径映射
# ====================================================================
# Windows: C:\code-base\Taihang-llm\
# WSL2:    /mnt/c/code-base/Taihang-llm/
PROJECT_ROOT="/mnt/c/code-base/Taihang-llm"
FINETUNE_DIR="${PROJECT_ROOT}/finetune"
DATA_DIR="${PROJECT_ROOT}/data"

echo "========================================================================"
echo " WSL2 + ROCm 环境配置 - AMD AI Max 395+ "
echo "========================================================================"
echo ""
echo "[PATH] PROJECT_ROOT = $PROJECT_ROOT"
echo "[PATH] FINETUNE_DIR = $FINETUNE_DIR"

# ====================================================================
# 第0步: 前提条件检查
# ====================================================================
echo ""
echo "[STEP 0] 检查前提条件..."

# 检查是否在 WSL2 中
if ! grep -qi microsoft /proc/version; then
    echo "[ERROR] 请在 WSL2 中运行此脚本！"
    exit 1
fi
echo "  ✓ WSL2 环境确认"

# 检查项目目录是否可访问
if [ -d "$PROJECT_ROOT" ]; then
    echo "  ✓ 项目目录可访问: $PROJECT_ROOT"
else
    echo "  ✗ 项目目录不可访问: $PROJECT_ROOT"
    echo "    请确认 Windows 盘已挂载到 /mnt/c/"
    exit 1
fi

# 检查 GPU 是否可见
if ls /dev/dri/renderD* 1> /dev/null 2>&1; then
    echo "  ✓ GPU 设备可见: $(ls /dev/dri/renderD*)"
else
    echo "  ✗ 未检测到 GPU 设备"
    echo "    请确保 Windows 已安装 AMD Software: Adrenalin Edition 26.1.1+"
    echo "    文档: https://rocm.docs.amd.com/projects/radeon/en/latest/docs/install/wsl/howto_wsl.html"
fi

# ====================================================================
# 第1步: 安装 ROCm (如果尚未安装)
# ====================================================================
echo ""
echo "[STEP 1] 检查/安装 ROCm..."

if command -v rocminfo &> /dev/null; then
    echo "  ✓ ROCm 已安装: $(rocminfo | grep 'ROCk module version' | head -1 || echo 'version check skipped')"
else
    echo "  安装 ROCm 7.2..."

    # 添加 ROCm 仓库
    sudo apt-get update
    sudo apt-get install -y wget gnupg2

    # ROCm 7.2 for Ubuntu 22.04
    wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
    echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/latest/ ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list

    sudo apt-get update
    sudo apt-get install -y rocm-dev rocm-libs

    echo "  ✓ ROCm 安装完成"
fi

# ====================================================================
# 第2步: Python 虚拟环境
# ====================================================================
echo ""
echo "[STEP 2] 创建 Python 虚拟环境..."

VENV_DIR="$HOME/venv_finetune"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  ✓ 虚拟环境创建于: $VENV_DIR"
else
    echo "  ✓ 虚拟环境已存在: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "  ✓ 虚拟环境已激活"

# ====================================================================
# 第3步: 安装 PyTorch ROCm 版
# ====================================================================
echo ""
echo "[STEP 3] 安装 PyTorch (ROCm 版)..."

pip install --upgrade pip

# PyTorch ROCm 版 - 使用最新稳定版
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.3

echo "  验证 PyTorch ROCm..."
python3 -c "
import torch
print(f'  PyTorch: {torch.__version__}')
print(f'  ROCm available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  Device: {torch.cuda.get_device_name(0)}')
    mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f'  Memory: {mem_gb:.1f} GB')
else:
    print('  [WARNING] ROCm 未检测到 GPU！请检查驱动和 ROCm 安装')
"

# ====================================================================
# 第4步: 安装 LlamaFactory
# ====================================================================
echo ""
echo "[STEP 4] 安装 LlamaFactory..."

pip install llamafactory[torch,metrics]

echo "  ✓ LlamaFactory 安装完成"
llamafactory-cli version 2>/dev/null || echo "  (版本检查跳过)"

# ====================================================================
# 第5步: 安装额外依赖
# ====================================================================
echo ""
echo "[STEP 5] 安装额外依赖..."

# wandb - 训练日志
pip install wandb

# bitsandbytes - QLoRA 量化 (ROCm 版)
pip install bitsandbytes

# transformers >= 4.51.0 (Qwen3 requirement)
pip install "transformers>=4.51.0"

# accelerate - 训练加速
pip install accelerate

# peft - LoRA 支持
pip install peft

echo "  ✓ 所有依赖安装完成"

# ====================================================================
# 第6步: 环境变量配置
# ====================================================================
echo ""
echo "[STEP 6] 配置环境变量..."

# AMD AI Max 395+ 特定优化 + 项目路径
cat > "$VENV_DIR/env_vars.sh" << ENVEOF
# ====================================================================
# Taihang-LLM 训练环境变量
# ====================================================================

# WSL2 路径映射
export TAIHANG_PROJECT_ROOT="${PROJECT_ROOT}"
export TAIHANG_DATA_DIR="${DATA_DIR}"
export TAIHANG_FINETUNE_DIR="${FINETUNE_DIR}"

# ROCm 环境变量
export HSA_OVERRIDE_GFX_VERSION=11.5.0
export ROCM_PATH=/opt/rocm
export HIP_VISIBLE_DEVICES=0

# 内存优化 (128GB 统一内存)
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
export GPU_MAX_HEAP_SIZE=100
export GPU_MAX_ALLOC_PERCENT=100

# Wandb
export WANDB_PROJECT=trading-reasoning-qwen3
ENVEOF

echo "  ✓ 环境变量保存到: $VENV_DIR/env_vars.sh"
echo "  每次训练前执行: source $VENV_DIR/env_vars.sh"

# ====================================================================
# 第7步: 创建输出目录
# ====================================================================
echo ""
echo "[STEP 7] 创建输出目录..."

mkdir -p "${PROJECT_ROOT}/outputs"
mkdir -p "${DATA_DIR}/finetune"

echo "  ✓ ${PROJECT_ROOT}/outputs/"
echo "  ✓ ${DATA_DIR}/finetune/"

# ====================================================================
# 第8步: 验证
# ====================================================================
echo ""
echo "========================================================================"
echo "[STEP 8] 环境验证"
echo "========================================================================"

python3 << 'PYEOF'
import sys
print(f"Python: {sys.version}")

try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    print(f"ROCm/CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name(0)}")
        mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU Memory: {mem:.1f} GB")
except ImportError:
    print("PyTorch: NOT INSTALLED")

try:
    import transformers
    print(f"Transformers: {transformers.__version__}")
except ImportError:
    print("Transformers: NOT INSTALLED")

try:
    import peft
    print(f"PEFT: {peft.__version__}")
except ImportError:
    print("PEFT: NOT INSTALLED")

try:
    import wandb
    print(f"Wandb: {wandb.__version__}")
except ImportError:
    print("Wandb: NOT INSTALLED")

try:
    import llamafactory
    print(f"LlamaFactory: OK")
except ImportError:
    print("LlamaFactory: NOT INSTALLED")

print("\n✓ 环境验证完成！")
PYEOF

# ====================================================================
# 第9步: 验证项目路径可访问性
# ====================================================================
echo ""
echo "[STEP 9] 验证 WSL2 路径映射..."

echo "  检查数据文件:"
REASONING_FILES=$(find "${DATA_DIR}" -name "deepseek_r1_reasoning_*.jsonl" 2>/dev/null | wc -l)
FILTERED_FILES=$(find "${DATA_DIR}/filtered_q" -name "*.jsonl" 2>/dev/null | wc -l)
echo "    Reasoning 文件: ${REASONING_FILES} 个"
echo "    Filtered 文件: ${FILTERED_FILES} 个"

echo "  检查 finetune 配置:"
if [ -f "${FINETUNE_DIR}/train_config_qwen3_32b_lora.yaml" ]; then
    echo "    ✓ LoRA 配置"
fi
if [ -f "${FINETUNE_DIR}/train_config_qwen3_32b_qlora.yaml" ]; then
    echo "    ✓ QLoRA 配置"
fi
if [ -f "${FINETUNE_DIR}/dataset_info.json" ]; then
    echo "    ✓ Dataset 配置"
fi
if [ -f "${FINETUNE_DIR}/data_converter.py" ]; then
    echo "    ✓ 数据转换脚本"
fi

echo ""
echo "========================================================================"
echo " 安装完成！"
echo "========================================================================"
echo ""
echo "  WSL2 路径映射:"
echo "    Windows: C:\\code-base\\Taihang-llm\\"
echo "    WSL2:    ${PROJECT_ROOT}/"
echo ""
echo "  下一步:"
echo ""
echo "  1. 登录 wandb："
echo "     wandb login"
echo ""
echo "  2. 准备训练数据："
echo "     cd ${FINETUNE_DIR}"
echo "     python3 data_converter.py"
echo ""
echo "  3. 启动训练："
echo "     source $VENV_DIR/env_vars.sh"
echo "     bash ${FINETUNE_DIR}/train_wsl2.sh lora"
echo "========================================================================"
