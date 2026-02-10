# Qwen3-32B Trading Reasoning 微调指南

基于 LlamaFactory 的交易推理模型微调方案，针对 **AMD AI Max 395+ 128GB** + **WSL2 ROCm** 优化。

## 🖥️ 硬件配置

| 组件 | 规格 |
|------|------|
| **APU** | AMD AI Max 395+ |
| **统一内存** | 128GB |
| **计算后端** | ROCm 7.2 (WSL2) |
| **模型** | Qwen/Qwen3-32B (32.8B 参数) |

## 📋 文件结构

```
finetune/
├── setup_wsl2_rocm.sh             # WSL2 ROCm 环境一键安装
├── data_converter.py              # 数据转换 (支持 Qwen3 think 模式)
├── dataset_info.json              # LlamaFactory 数据集配置
├── train_config_qwen3_32b_lora.yaml    # LoRA 配置 (~80GB 显存)
├── train_config_qwen3_32b_qlora.yaml   # QLoRA 配置 (~25GB 显存)
├── train_wsl2.sh                  # WSL2 训练启动脚本
└── README.md
```

## 🚀 快速开始

### 第 1 步：WSL2 环境配置

**Windows 端前置条件：**
- AMD Software: Adrenalin Edition **26.1.1+** 驱动
- WSL2 已启用

```bash
# 在 WSL2 终端中运行
cd /mnt/c/code-base/Taihang-llm/finetune
bash setup_wsl2_rocm.sh
```

这个脚本会自动：
1. 检查 WSL2 和 GPU 设备
2. 安装 ROCm 7.2
3. 创建 Python 虚拟环境
4. 安装 PyTorch ROCm 版
5. 安装 LlamaFactory + wandb + 所有依赖
6. 配置 AMD AI Max 395+ 特定环境变量
7. 验证整个环境

### 第 2 步：登录 Wandb

```bash
wandb login
# 输入你的 API key (从 https://wandb.ai/settings 获取)
```

### 第 3 步：准备数据

```bash
cd /mnt/c/code-base/Taihang-llm/finetune

# 转换 AAPL reasoning 数据 (自动启用 Qwen3 think 模式)
python data_converter.py

# 或合并多个 symbol 的数据
python data_converter.py --merge \
    ../data/deepseek_r1_reasoning_AAPL_*.jsonl \
    ../data/deepseek_r1_reasoning_AMD_*.jsonl \
    -o ../data/finetune/trading_reasoning_merged.json

# 预览转换效果
python data_converter.py --preview ../data/deepseek_r1_reasoning_AAPL_5m_15y_y2008_2017_2020_2021_2022.jsonl
```

### 第 4 步：启动训练

```bash
# LoRA 训练 (推荐 - 充分利用 128GB)
bash train_wsl2.sh lora

# 或 QLoRA 训练 (保守内存使用)
bash train_wsl2.sh qlora
```

### 第 5 步：监控训练

```bash
# Wandb 在线监控
# 浏览器访问: https://wandb.ai/<your_username>/trading-reasoning-qwen3

# TensorBoard 本地监控
tensorboard --logdir=../outputs/qwen3_32b_trading_lora
```

## ⚙️ 训练模式对比

### LoRA vs QLoRA (针对 128GB 统一内存)

| 特性 | LoRA (推荐) | QLoRA |
|------|-------------|-------|
| **模型精度** | BF16 (全精度) | 4-bit 量化 |
| **内存占用** | ~80GB | ~25GB |
| **Batch Size** | 1 | 2 |
| **梯度累积** | 16 | 8 |
| **有效 Batch** | 16 | 16 |
| **训练速度** | 较快 | 较慢 (量化开销) |
| **模型质量** | 最优 | 略低 (几乎无损) |
| **适合场景** | 128GB 可以跑 | 内存紧张时 |

**推荐方案**：你的 128GB 统一内存完全可以跑 **LoRA BF16**，无需量化。

### 关键训练超参数

```yaml
# Qwen3-32B 推荐参数
model_name_or_path: Qwen/Qwen3-32B
template: qwen3                    # Qwen3 专用 template

lora_rank: 64                      # LoRA 秩
lora_alpha: 128                    # LoRA 缩放 (通常 = 2x rank)
lora_dropout: 0.05                 # 低 dropout

learning_rate: 1.0e-5              # 32B 模型用较低学习率
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1

gradient_checkpointing: true       # 必须开启，节省内存
cutoff_len: 8192                   # 序列长度

# 优化器 (Qwen3 官方推荐)
optim: adamw_torch
adam_beta2: 0.95                   # Qwen3 推荐 0.95
weight_decay: 0.1
```

## 🧠 Qwen3 思考模式

Qwen3 支持 **thinking mode**（思考模式），使用 `<think>...</think>` 标签包裹推理过程。

数据转换脚本会自动将 DeepSeek R1 的 reasoning 格式转换为 Qwen3 格式：

**转换前** (DeepSeek R1)：
```
Alright, so I'm trying to figure out why the price rallied...
The volume spike at 14:30 is way above average...
</think>

```json
{"reasoning": {"D1_H4_Key_Level": "..."}}
```

**转换后** (Qwen3)：
```
<think>
Alright, so I'm trying to figure out why the price rallied...
The volume spike at 14:30 is way above average...
</think>

```json
{"reasoning": {"D1_H4_Key_Level": "..."}}
```

## 🔧 AMD AI Max 395+ 特定优化

### ROCm 环境变量

```bash
# GFX 版本覆盖 (AI Max 395+)
export HSA_OVERRIDE_GFX_VERSION=11.5.0

# 内存分配优化
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
export GPU_MAX_HEAP_SIZE=100
export GPU_MAX_ALLOC_PERCENT=100
```

### 已知问题

1. **WSL2 "No WDDM adapters found" 错误**
   - 确保 Windows 驱动为 AMD Adrenalin Edition **26.1.1+**
   - 参考：https://rocm.docs.amd.com/projects/radeon/en/latest/docs/install/wsl/howto_wsl.html

2. **ROCm 内存限制**
   - 统一内存架构下，系统和 GPU 共享 128GB
   - 训练时建议关闭浏览器等占内存的应用
   - 如果 OOM，切换到 QLoRA 模式

3. **HSA_OVERRIDE_GFX_VERSION**
   - AI Max 395+ 可能需要此变量来正确识别 GPU 架构
   - 如果训练报错 "unsupported GPU"，尝试调整此值

## 📈 训练后操作

### 1. 合并 LoRA 适配器

```bash
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen3-32B \
    --adapter_name_or_path ../outputs/qwen3_32b_trading_lora \
    --template qwen3 \
    --finetuning_type lora \
    --trust_remote_code true \
    --export_dir ../outputs/qwen3_32b_trading_merged
```

### 2. 推理测试

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# 加载合并后的模型
model = AutoModelForCausalLM.from_pretrained(
    "../outputs/qwen3_32b_trading_merged",
    device_map="auto",
    torch_dtype=torch.bfloat16,
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(
    "../outputs/qwen3_32b_trading_merged",
    trust_remote_code=True
)

# 构造 prompt
messages = [
    {"role": "system", "content": "You are a specialized trading AI."},
    {"role": "user", "content": """### ROLE
You are a master Quant Trader identifying the causality behind market moves.

### MARKET CONTEXT
[1. MACRO D1] Trend: Bullish | Supp: 185.50 | Res: 192.00
...

### YOUR TASK
Analyze and explain WHY this move happened.
"""}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer([text], return_tensors="pt").to(model.device)

# 启用思考模式
outputs = model.generate(
    **inputs,
    max_new_tokens=4096,
    temperature=0.7,
    top_p=0.8,
    do_sample=True
)
response = tokenizer.decode(outputs[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True)
print(response)
```

### 3. GGUF 量化导出 (用于本地部署)

```bash
# 安装 llama.cpp
# 然后将合并后的模型转换为 GGUF
python convert_hf_to_gguf.py ../outputs/qwen3_32b_trading_merged \
    --outfile qwen3_32b_trading_Q6_K.gguf \
    --outtype q6_k
```

## 📊 训练效果基线

| 实验 | 数据量 | Epochs | LR | Rank | Train Loss | Val Loss | 备注 |
|------|--------|--------|----|------|-----------|---------|------|
| baseline | ~1000 | 3 | 1e-5 | 64 | - | - | AAPL 单 symbol |
| exp2 | ~5000 | 3 | 1e-5 | 64 | - | - | 多 symbol 合并 |
| exp3 | ~5000 | 5 | 5e-6 | 128 | - | - | 更高 rank + 更长训练 |

## 📚 参考

- [LlamaFactory](https://github.com/hiyouga/LLaMA-Factory)
- [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B)
- [ROCm on Radeon/Ryzen](https://rocm.docs.amd.com/projects/radeon/en/latest/)
- [AMD AI Max 395+ LLM Guide](https://www.amd.com/en/blogs/2025/amd-ryzen-ai-max-upgraded-run-up-to-128-billion-parameter-llms-lm-studio.html)
- [Wandb](https://docs.wandb.ai/)
