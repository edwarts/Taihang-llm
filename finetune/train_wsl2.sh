#!/bin/bash
# ====================================================================
# LlamaFactory 训练脚本 - Qwen3-32B Trading Reasoning 微调
# 硬件: AMD AI Max 395+ 128GB / WSL2 + ROCm
#
# 用法:
#   bash train_wsl2.sh [lora|qlora] [--samples N] [--tag TAG]
#
# 示例:
#   bash train_wsl2.sh lora                    # 全量 LoRA
#   bash train_wsl2.sh lora --samples 50       # 只用 50 条数据快速测试
#   bash train_wsl2.sh qlora --samples 100 --tag exp_lr3e5
#   bash train_wsl2.sh lora --tag baseline_v2
# ====================================================================

set -e

# ====================================================================
# WSL2 路径映射
# ====================================================================
PROJECT_ROOT="/mnt/c/code-base/Taihang-llm"
FINETUNE_DIR="${PROJECT_ROOT}/finetune"
DATA_DIR="${PROJECT_ROOT}/data"
FINETUNE_DATA_DIR="${DATA_DIR}/finetune"
OUTPUTS_DIR="${PROJECT_ROOT}/outputs"

# ====================================================================
# 解析命令行参数
# ====================================================================
TRAINING_MODE="${1:-lora}"
shift 2>/dev/null || true

MAX_SAMPLES=""
CUSTOM_TAG=""

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

# 构造 RUN_ID: 模式_样本数_标签_时间戳
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

# 输出目录带唯一标识
OUTPUT_DIR="${OUTPUTS_DIR}/qwen3_32b_${RUN_ID}"

VENV_DIR="${VENV_DIR:-$HOME/venv_finetune}"

# 进入 finetune 工作目录
cd "$FINETUNE_DIR"

echo "========================================================================"
echo " Qwen3-32B Trading Reasoning 微调"
echo " 硬件: AMD AI Max 395+ 128GB | WSL2 + ROCm"
echo "========================================================================"
echo ""
echo "  模式:       ${TRAINING_MODE^^}"
echo "  RUN_ID:     ${RUN_ID}"
echo "  样本限制:   ${MAX_SAMPLES:-全量 (不限制)}"
echo "  自定义标签: ${CUSTOM_TAG:-无}"
echo "  输出目录:   ${OUTPUT_DIR}"
echo ""
echo "[PATH] PROJECT_ROOT = $PROJECT_ROOT"
echo "[PATH] DATA_DIR     = $DATA_DIR"
echo "[PATH] OUTPUT_DIR   = $OUTPUT_DIR"

# ====================================================================
# 环境准备
# ====================================================================
echo ""
echo "[ENV] 激活虚拟环境..."

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "[ERROR] 虚拟环境不存在: $VENV_DIR"
    echo "        请先运行: bash ${FINETUNE_DIR}/setup_wsl2_rocm.sh"
    exit 1
fi

# 加载 ROCm 环境变量
if [ -f "$VENV_DIR/env_vars.sh" ]; then
    source "$VENV_DIR/env_vars.sh"
    echo "[ENV] ROCm 环境变量已加载"
fi

# AMD AI Max 395+ 特定设置
export HSA_OVERRIDE_GFX_VERSION=11.5.0
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
export GPU_MAX_HEAP_SIZE=100
export GPU_MAX_ALLOC_PERCENT=100
export HIP_VISIBLE_DEVICES=0

# Wandb 配置
export WANDB_PROJECT="${WANDB_PROJECT:-trading-reasoning-qwen3}"
export WANDB_RUN_NAME="${RUN_ID}"

echo "[ENV] HIP_VISIBLE_DEVICES=$HIP_VISIBLE_DEVICES"

# ====================================================================
# GPU 检查
# ====================================================================
echo ""
echo "[GPU] 检查 GPU 状态..."
python3 -c "
import torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f'  Device: {name}')
    print(f'  Memory: {mem:.1f} GB')
    print(f'  ROCm: OK')
else:
    print('  [WARNING] GPU not detected!')
    print('  Training will be very slow on CPU.')
"

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
# 动态生成训练配置文件 (基于参数)
# ====================================================================
echo ""
echo "========================================================================"
echo "[STEP 2] 生成训练配置"
echo "========================================================================"

# 选择基础配置模板
if [ "$TRAINING_MODE" = "qlora" ]; then
    BASE_CONFIG="${FINETUNE_DIR}/train_config_qwen3_32b_qlora.yaml"
    BATCH_SIZE=2
    GRAD_ACCUM=8
    echo "[CONFIG] 基础模板: QLoRA 4-bit"
else
    BASE_CONFIG="${FINETUNE_DIR}/train_config_qwen3_32b_lora.yaml"
    BATCH_SIZE=1
    GRAD_ACCUM=16
    echo "[CONFIG] 基础模板: LoRA BF16"
fi

# 生成运行时配置 (覆盖 output_dir, max_samples, run_name)
RUNTIME_CONFIG="${FINETUNE_DIR}/runtime_config_${RUN_ID}.yaml"

# 复制基础配置并覆盖动态参数
cp "$BASE_CONFIG" "$RUNTIME_CONFIG"

# 替换 output_dir 为带唯一标识的路径
python3 -c "
import re
config = open('${RUNTIME_CONFIG}', 'r').read()

# 替换 output_dir
config = re.sub(
    r'^output_dir:.*$',
    'output_dir: ${OUTPUT_DIR}',
    config, flags=re.MULTILINE
)

# 替换 run_name
config = re.sub(
    r'^run_name:.*$',
    'run_name: ${RUN_ID}',
    config, flags=re.MULTILINE
)

# 替换 max_samples (如果指定了 --samples)
max_samples = '${MAX_SAMPLES}'
if max_samples:
    config = re.sub(
        r'^max_samples:.*$',
        f'max_samples: {max_samples}',
        config, flags=re.MULTILINE
    )

open('${RUNTIME_CONFIG}', 'w').write(config)
print('[CONFIG] 运行时配置已生成')
"

echo ""
echo "  配置文件:   $RUNTIME_CONFIG"
echo "  输出目录:   $OUTPUT_DIR"
echo "  样本限制:   ${MAX_SAMPLES:-不限制 (使用配置文件默认值)}"
echo "  Wandb Run:  $RUN_ID"
echo ""

# 显示关键配置差异
echo "[CONFIG] 关键参数:"
grep -E "^(output_dir|max_samples|run_name|per_device_train|gradient_accum|learning_rate|num_train_epochs|lora_rank):" "$RUNTIME_CONFIG" | while read line; do
    echo "  $line"
done

echo ""

# 确认训练
read -p "按 Enter 开始训练 (Ctrl+C 取消)..." _

# ====================================================================
# 创建输出目录
# ====================================================================
mkdir -p "$OUTPUT_DIR"

# 保存本次运行的元信息
cat > "${OUTPUT_DIR}/run_info.json" << INFOEOF
{
    "run_id": "${RUN_ID}",
    "timestamp": "${TIMESTAMP}",
    "training_mode": "${TRAINING_MODE}",
    "max_samples": ${MAX_SAMPLES:-null},
    "custom_tag": "${CUSTOM_TAG:-null}",
    "base_config": "$(basename $BASE_CONFIG)",
    "runtime_config": "$(basename $RUNTIME_CONFIG)",
    "output_dir": "${OUTPUT_DIR}",
    "output_dir_windows": "C:\\\\code-base\\\\Taihang-llm\\\\outputs\\\\qwen3_32b_${RUN_ID}",
    "model": "Qwen/Qwen3-32B",
    "hardware": "AMD AI Max 395+ 128GB"
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

# 记录开始时间
START_TIME=$(date +%s)

llamafactory-cli train \
    "$RUNTIME_CONFIG"

# 计算训练时长
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

# 清理运行时配置
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
echo "  查看训练日志:"
echo "    Wandb: https://wandb.ai/\$WANDB_ENTITY/$WANDB_PROJECT/runs/$RUN_ID"
echo ""
echo "  合并 LoRA 适配器:"
echo "    llamafactory-cli export \\"
echo "        --model_name_or_path Qwen/Qwen3-32B \\"
echo "        --adapter_name_or_path $OUTPUT_DIR \\"
echo "        --template qwen3 \\"
echo "        --finetuning_type lora \\"
echo "        --trust_remote_code true \\"
echo "        --export_dir ${OUTPUTS_DIR}/qwen3_32b_merged_${RUN_ID}"
echo "========================================================================"
