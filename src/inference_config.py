# -*- coding: utf-8 -*-
"""
Inference Backend Configuration
支持在Ollama和vLLM之间快速切换
"""

import os

# ==================== 后端选择 ====================
# 设置为 "vllm" 或 "ollama"
INFERENCE_BACKEND = os.getenv("INFERENCE_BACKEND", "vllm").lower()

# ==================== vLLM配置 ====================
# WSL2内vLLM服务地址
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://172.31.194.125:8000")
VLLM_MODEL = "deepseek-ai/deepseek-r1-distill-qwen-70b"
VLLM_TIMEOUT = 300

# ==================== Ollama配置 ====================
# Windows本地Ollama服务地址
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = "deepseek-r1:70b"
OLLAMA_TIMEOUT = 300

# ==================== 推理配置 ====================
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "25"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("TOP_P", "0.9"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# ==================== 输出配置 ====================
PROMPT_DIR = os.getenv("PROMPT_DIR", "data")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data")
DEFAULT_WINDOW = os.getenv("DEFAULT_WINDOW", "5m")
DEFAULT_YEARS = int(os.getenv("DEFAULT_YEARS", "15"))

# ==================== 验证配置 ====================
def get_backend_config():
    """获取当前后端配置"""
    if INFERENCE_BACKEND == "vllm":
        return {
            "backend": "vLLM",
            "api_url": VLLM_API_URL,
            "model": VLLM_MODEL,
            "timeout": VLLM_TIMEOUT
        }
    else:
        return {
            "backend": "Ollama",
            "api_url": OLLAMA_API_URL,
            "model": OLLAMA_MODEL,
            "timeout": OLLAMA_TIMEOUT
        }

def print_config():
    """打印配置信息"""
    config = get_backend_config()
    print(f"[CONFIG] Backend: {config['backend']}")
    print(f"[CONFIG] API URL: {config['api_url']}")
    print(f"[CONFIG] Model: {config['model']}")
    print(f"[CONFIG] Timeout: {config['timeout']}s")
    print(f"[CONFIG] Concurrent Requests: {CONCURRENT_REQUESTS}")
    print(f"[CONFIG] Temperature: {TEMPERATURE}")

if __name__ == "__main__":
    print_config()
