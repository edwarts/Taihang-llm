#!/bin/bash
# ====================================================================
# LlamaFactory 训练脚本 - Qwen3-32B Trading Reasoning 微调
# 环境: WSL2 + Conda (trading_ai_py311)
# 硬件: AMD AI Max 395+ 128GB / ROCm
#
# 用法:
#   bash train_conda.sh [lora|qlora] [--samples N] [--tag TAG] [--epochs N]
#                                     [--lr RATE] [--rank N] [--data DATASET]
#
# 示例:
#   bash train_conda.sh lora                          # 全量 LoRA
#   bash train_conda.sh lora --samples 50             # 50 条快速测试
#   bash train_conda.sh lora --samples 50 --tag smoke # 50 条 + 自定义标签
#   bash train_conda.sh qlora --samples 200 --tag exp_lr3e5 --lr 3e-5
#   bash train_conda.sh lora --epochs 5 --rank 128 --tag high_rank
#   bash train_conda.sh lora --data trading_reasoning_merged  # 用合并数据集
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
FINETUNE_DATA_DIR="${DATA_DIR}/finetune"
OUTPUTS_DIR="${PROJECT_ROOT}/outputs"

# Conda 环境名 (可通过环境变量覆盖)
CONDA_ENV="${CONDA_ENV:-trading_ai_py311}"

# ====================================================================
# 解析命令行参数
# ====================================================================
TRAINING_MODE="${1:-lora}"
shift 2>/dev/null || true

MAX_SAMPLES=""
CUSTOM_TAG=""
CUSTOM_LR=""
CUSTOM_EPOCHS=""
CUSTOM_RANK=""
DATASET_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --samples)
            MAX_SAMPLES="$2"
            shift 2
            ;;
        --tag)
            CUSTOM_TAG="$2"
            shift 2
            ;;
        --lr)
            CUSTOM_LR="$2"
            shift 2
            ;;
        --epochs)
            CUSTOM_EPOCHS="$2"
            shift 2
            ;;
        --rank)
            CUSTOM_RANK="$2"
            shift 2
            ;;
        --data)
            DATASET_NAME="$2"
            shift 2
            ;;
        *)
            echo "[WARNING] 未知参数: $1"
            shift
            ;;
    esac
done

# ====================================================================
# 生成唯一运行标识 (RUN_ID)
# ====================================================================
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

RUN_ID="${TRAINING_MODE}"
if [ -n "$MAX_SAMPLES" ]; then
    RUN_ID="${RUN_ID}_n${MAX_SAMPLES}"
else
    RUN_ID="${RUN_ID}_full"
fi
if [ -n "$CUSTOM_TAG" ]; then
    RUN_ID="${RUN_ID}_${CUSTOM_TAG}"
fi
RUN_ID="${RUN_ID}_${TIMESTAMP}"

OUTPUT_DIR="${OUTPUTS_DIR}/qwen3_32b_${RUN_ID}"

# 进入 finetune 工作目录
cd "$FINETUNE_DIR"

echo "========================================================================"
echo " Qwen3-32B Trading Reasoning 微调"
echo " 环境: Conda (${CONDA_ENV}) | WSL2 + ROCm"
echo " 硬件: AMD AI Max 395+ 128GB"
echo "========================================================================"
echo ""
echo "  模式:       ${TRAINING_MODE^^}"
echo "  RUN_ID:     ${RUN_ID}"
echo "  样本限制:   ${MAX_SAMPLES:-全量 (不限制)}"
echo "  自定义标签: ${CUSTOM_TAG:-无}"
echo "  学习率:     ${CUSTOM_LR:-默认 (1e-5)}"
echo "  Epochs:     ${CUSTOM_EPOCHS:-默认 (3)}"
echo "  LoRA Rank:  ${CUSTOM_RANK:-默认 (64)}"
echo "  数据集:     ${DATASET_NAME:-trading_reasoning (默认)}"
echo "  输出目录:   ${OUTPUT_DIR}"
echo ""
echo "[PATH] PROJECT_ROOT = $PROJECT_ROOT"
echo "[PATH] DATA_DIR     = $DATA_DIR"
echo "[PATH] OUTPUT_DIR   = $OUTPUT_DIR"

# ====================================================================
# 激活 Conda 环境
# ====================================================================
echo ""
echo "[ENV] 激活 Conda 环境: ${CONDA_ENV}..."

# 初始化 conda (兼容不同安装方式)
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source "/opt/conda/etc/profile.d/conda.sh"
elif command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
else
    echo "[ERROR] 找不到 conda！请确认 conda 已安装"
    exit 1
fi

conda activate "$CONDA_ENV"
echo "[ENV] ✓ Conda 环境已激活: $(python3 --version)"
echo "[ENV]   Python 路径: $(which python3)"

# ====================================================================
# AMD AI Max 395+ ROCm 环境变量
# ====================================================================
export HSA_OVERRIDE_GFX_VERSION=11.5.0
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
export GPU_MAX_HEAP_SIZE=100
export GPU_MAX_ALLOC_PERCENT=100
export HIP_VISIBLE_DEVICES=0

# Wandb 配置
export WANDB_PROJECT="${WANDB_PROJECT:-trading-reasoning-qwen3}"
export WANDB_RUN_NAME="${RUN_ID}"

echo "[ENV] ROCm 环境变量已设置"
echo "[ENV] HIP_VISIBLE_DEVICES=$HIP_VISIBLE_DEVICES"

# ====================================================================
# GPU 检查
# ====================================================================
echo ""
echo "[GPU] 检查 GPU 状态..."
python3 -c "
import torch
print(f'  PyTorch: {torch.__version__}')
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f'  Device: {name}')
    print(f'  Memory: {mem:.1f} GB')
    print(f'  ROCm: OK')
else:
    print('  [WARNING] GPU not detected! Training will be CPU-only.')
"

# 快速检查 LlamaFactory
python3 -c "import llamafactory; print('[ENV] ✓ LlamaFactory ready')" 2>/dev/null || {
    echo "[ERROR] LlamaFactory 未安装在 ${CONDA_ENV} 中"
    exit 1
}

# ====================================================================
# 数据准备
# ====================================================================
echo ""
echo "========================================================================"
echo "[STEP 1] 准备训练数据"
echo "========================================================================"

mkdir -p "$FINETUNE_DATA_DIR"

if [ ! -f "${FINETUNE_DATA_DIR}/trading_reasoning_aapl.json" ]; then
    echo "[DATA] 转换 reasoning 数据..."
    python3 "${FINETUNE_DIR}/data_converter.py"
else
    SAMPLE_COUNT=$(python3 -c "import json; print(len(json.load(open('${FINETUNE_DATA_DIR}/trading_reasoning_aapl.json'))))")
    echo "[DATA] 数据已就绪: $SAMPLE_COUNT 条样本"
fi

# ====================================================================
# 动态生成训练配置文件
# ====================================================================
echo ""
echo "========================================================================"
echo "[STEP 2] 生成训练配置"
echo "========================================================================"

if [ "$TRAINING_MODE" = "qlora" ]; then
    BASE_CONFIG="${FINETUNE_DIR}/train_config_qwen3_32b_qlora.yaml"
    echo "[CONFIG] 基础模板: QLoRA 4-bit"
else
    BASE_CONFIG="${FINETUNE_DIR}/train_config_qwen3_32b_lora.yaml"
    echo "[CONFIG] 基础模板: LoRA BF16"
fi

RUNTIME_CONFIG="${FINETUNE_DIR}/runtime_config_${RUN_ID}.yaml"

cp "$BASE_CONFIG" "$RUNTIME_CONFIG"

# 用 Python 动态修改 YAML 配置
python3 << PYSCRIPT
import re

config = open('${RUNTIME_CONFIG}', 'r').read()

# 必改: output_dir
config = re.sub(r'^output_dir:.*$', 'output_dir: ${OUTPUT_DIR}', config, flags=re.MULTILINE)

# 必改: run_name
config = re.sub(r'^run_name:.*$', 'run_name: ${RUN_ID}', config, flags=re.MULTILINE)

# 可选: max_samples
max_samples = '${MAX_SAMPLES}'
if max_samples:
    config = re.sub(r'^max_samples:.*$', f'max_samples: {max_samples}', config, flags=re.MULTILINE)

# 可选: learning_rate
lr = '${CUSTOM_LR}'
if lr:
    config = re.sub(r'^learning_rate:.*$', f'learning_rate: {lr}', config, flags=re.MULTILINE)

# 可选: num_train_epochs
epochs = '${CUSTOM_EPOCHS}'
if epochs:
    config = re.sub(r'^num_train_epochs:.*$', f'num_train_epochs: {epochs}', config, flags=re.MULTILINE)

# 可选: lora_rank (同时调整 lora_alpha = 2x rank)
rank = '${CUSTOM_RANK}'
if rank:
    config = re.sub(r'^lora_rank:.*$', f'lora_rank: {rank}', config, flags=re.MULTILINE)
    alpha = int(rank) * 2
    config = re.sub(r'^lora_alpha:.*$', f'lora_alpha: {alpha}', config, flags=re.MULTILINE)

# 可选: dataset 名
dataset_name = '${DATASET_NAME}'
if dataset_name:
    config = re.sub(r'^dataset:.*$', f'dataset: {dataset_name}', config, flags=re.MULTILINE)

open('${RUNTIME_CONFIG}', 'w').write(config)
print('[CONFIG] 运行时配置已生成')
PYSCRIPT

echo ""
echo "  配置文件:   $RUNTIME_CONFIG"
echo "  输出目录:   $OUTPUT_DIR"
echo "  样本限制:   ${MAX_SAMPLES:-不限制}"
echo "  Wandb Run:  $RUN_ID"
echo ""

echo "[CONFIG] 关键参数:"
grep -E "^(output_dir|max_samples|run_name|dataset:|per_device_train|gradient_accum|learning_rate|num_train_epochs|lora_rank|lora_alpha):" "$RUNTIME_CONFIG" | while read line; do
    echo "  $line"
done

echo ""
read -p "按 Enter 开始训练 (Ctrl+C 取消)..." _

# ====================================================================
# 保存运行元信息
# ====================================================================
mkdir -p "$OUTPUT_DIR"

cat > "${OUTPUT_DIR}/run_info.json" << INFOEOF
{
    "run_id": "${RUN_ID}",
    "timestamp": "${TIMESTAMP}",
    "training_mode": "${TRAINING_MODE}",
    "max_samples": ${MAX_SAMPLES:-null},
    "custom_tag": "${CUSTOM_TAG:-null}",
    "learning_rate": "${CUSTOM_LR:-1.0e-5}",
    "epochs": "${CUSTOM_EPOCHS:-3.0}",
    "lora_rank": "${CUSTOM_RANK:-64}",
    "dataset": "${DATASET_NAME:-trading_reasoning}",
    "base_config": "$(basename $BASE_CONFIG)",
    "runtime_config": "$(basename $RUNTIME_CONFIG)",
    "output_dir_wsl2": "${OUTPUT_DIR}",
    "output_dir_windows": "C:\\\\code-base\\\\Taihang-llm\\\\outputs\\\\qwen3_32b_${RUN_ID}",
    "model": "Qwen/Qwen3-32B",
    "hardware": "AMD AI Max 395+ 128GB",
    "conda_env": "${CONDA_ENV}",
    "python_version": "$(python3 --version 2>&1)",
    "status": "started"
}
INFOEOF

echo "[INFO] 运行元信息已保存: ${OUTPUT_DIR}/run_info.json"

# ====================================================================
# 开始训练
# ====================================================================
echo ""
echo "[TRAIN] 启动 LlamaFactory 训练..."
echo "[TRAIN] RUN_ID: $RUN_ID"
echo "[TRAIN] 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

START_TIME=$(date +%s)

llamafactory-cli train "$RUNTIME_CONFIG"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(( (DURATION % 3600) / 60 ))
SECONDS_LEFT=$((DURATION % 60))

# ====================================================================
# 训练完成 - 更新元信息
# ====================================================================
python3 -c "
import json
info = json.load(open('${OUTPUT_DIR}/run_info.json'))
info['training_duration_seconds'] = ${DURATION}
info['training_duration_human'] = '${HOURS}h ${MINUTES}m ${SECONDS_LEFT}s'
info['status'] = 'completed'
json.dump(info, open('${OUTPUT_DIR}/run_info.json', 'w'), indent=2, ensure_ascii=False)
"

rm -f "$RUNTIME_CONFIG"

echo ""
echo "========================================================================"
echo "[COMPLETE] 训练完成！"
echo "========================================================================"
echo ""
echo "  RUN_ID:   $RUN_ID"
echo "  训练时长: ${HOURS}h ${MINUTES}m ${SECONDS_LEFT}s"
echo "  样本数:   ${MAX_SAMPLES:-全量}"
echo ""
echo "  模型输出 (WSL2):    $OUTPUT_DIR"
echo "  模型输出 (Windows): C:\\code-base\\Taihang-llm\\outputs\\qwen3_32b_${RUN_ID}"
echo ""
echo "  Wandb: https://wandb.ai/${WANDB_PROJECT}"
echo ""
echo "  合并 LoRA:"
echo "    llamafactory-cli export \\"
echo "        --model_name_or_path Qwen/Qwen3-32B \\"
echo "        --adapter_name_or_path $OUTPUT_DIR \\"
echo "        --template qwen3 \\"
echo "        --finetuning_type lora \\"
echo "        --trust_remote_code true \\"
echo "        --export_dir ${OUTPUTS_DIR}/qwen3_32b_merged_${RUN_ID}"
echo "========================================================================"
