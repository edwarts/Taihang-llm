#!/bin/bash
# vLLM 启动脚本（WSL2内运行）
# 使用：cd /mnt/c/code-base/Taihang-llm && bash vllm_startup.sh

set -e

echo "========================================"
echo "vLLM Server Startup (DeepSeek-R1:70b)"
echo "========================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv_vllm" ]; then
    echo "[ERROR] venv_vllm not found!"
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv_vllm
fi

# 激活虚拟环境
source venv_vllm/bin/activate

# 检查vLLM安装
if ! python -c "import vllm" 2>/dev/null; then
    echo "[INFO] Installing vLLM..."
    pip install --upgrade pip
    pip install vllm[rocm]
fi

# 检查ROCm
echo ""
echo "[INFO] Checking ROCm installation..."
if ! rocm-smi >/dev/null 2>&1; then
    echo "[WARNING] ROCm not found or not working properly."
    echo "[WARNING] vLLM will try to use CPU instead."
fi

# 获取本机IP
WSL_IP=$(hostname -I | cut -d' ' -f1)
echo ""
echo "[INFO] WSL2 IP Address: $WSL_IP"
echo "[INFO] vLLM will be available at: http://$WSL_IP:8000"
echo ""

# 设置环境变量以支持AMD GPU
export VLLM_DEVICE="auto"  # 自动检测设备
export VLLM_LOGGING_LEVEL="INFO"  # 日志级别

# 启动vLLM
echo "[START] Starting vLLM server..."
echo "========================================"
echo ""

python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-r1-distill-qwen-70b \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.95 \
  --enable-prefix-caching \
  --tensor-parallel-size 1 \
  --dtype float16 \
  --seed 42 \
  --max-model-len 4096 \
  --device auto

echo ""
echo "[INFO] To stop vLLM, press Ctrl+C"
