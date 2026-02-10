# Google Colab A100 部署指南: DeepSeek R1 70B 推理

## 概述

在 Google Colab A100 (80GB) 上运行 DeepSeek R1 Distill 70B Q4 (AWQ量化) 推理，
生成完整思维链 (CoT) 用于 finetune Qwen3 7B。

**预估性能**:
- 单条 prompt: ~15-20 秒 (vLLM batch=32)
- AAPL 28K 条: ~3-4 天
- 全量 880K 条: 逐个 symbol 跑，约 90-120 天

## 前提条件

1. **Google Colab Pro/Pro+** 订阅 (才能使用 A100 GPU)
   - Colab Pro: $9.99/月, 可能分配到 A100 但不保证
   - Colab Pro+: $49.99/月, 优先获得 A100
   
2. **Google Drive** 存储空间 (存放数据和结果)
   - Prompt 数据: ~2.5 GB (所有 symbol)
   - 输出结果: ~5-10 GB (含完整思维链)
   - 建议预留: 20 GB

## 步骤

### Step 1: 上传数据到 Google Drive

```
Google Drive/
└── Taihang-llm/
    └── data/
        ├── deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
        ├── deepseek_r1_input_prompts_MSFT_5m_15y.jsonl
        ├── deepseek_r1_input_prompts_NVDA_5m_15y.jsonl
        └── ... (其他 symbol 的文件)
```

### Step 2: 打开 Notebook

1. 上传 `notebooks/colab_deepseek_r1_inference.ipynb` 到 Colab
2. 或者直接在 Colab 中 "File → Open notebook → Upload"

### Step 3: 设置运行时

1. 菜单: **Runtime → Change runtime type**
2. 选择:
   - **Hardware accelerator**: GPU
   - **GPU type**: **A100** (需要 Pro/Pro+)
   - **High-RAM**: 启用
3. 点击 Save

### Step 4: 运行 Notebook

按顺序运行每个 Cell:

1. **Cell 0**: 检查 GPU 是否为 A100 80GB
2. **Cell 1**: 安装 vLLM
3. **Cell 2**: 配置模型 (AWQ 量化版自动下载)
4. **Cell 3**: 挂载 Google Drive
5. **Cell 4**: 设置参数 (修改 SYMBOL, 年份筛选等)
6. **Cell 5**: 启动 vLLM 引擎 (首次约 10 分钟)
7. **Cell 6**: 加载数据 + 年份筛选
8. **Cell 7**: **运行推理** (核心步骤, 耗时最长)

### Step 5: 断点续传

Colab 会话可能在 ~12 小时后断开。不用担心:

1. 重新连接并运行相同 Notebook
2. 从 **Cell 5** 开始重新运行 (重新加载模型)
3. Cell 7 会自动加载 checkpoint，跳过已完成的 prompt
4. 进度保存在 Google Drive 中，不会丢失

## 模型选择

### 推荐: AWQ 量化 (38GB)

```python
MODEL_ID = "casperhansen/deepseek-r1-distill-qwen-70b-awq"
```

- 大小: ~38 GB
- 精度: 4-bit AWQ
- A100 80GB 剩余 ~42GB 给 KV cache
- 支持 batch=32 的 continuous batching
- 思维链质量接近 FP16

### 备选: GPTQ 量化

```python
MODEL_ID = "TheBloke/deepseek-r1-distill-qwen-70b-GPTQ"
```

### 备选: FP16 原始权重 (140GB, 不推荐)

A100 80GB 放不下，需要 2 张 A100 + tensor parallelism。

## 年份筛选

### 黄金切片法 (自动)

```python
GOLDEN_SLICE = 5  # 从15年中自动选5个代表性年份
```

将数据量减少到 ~1/3，本地推理时间从 140 天 → ~47 天。

### 手动选择

```python
YEARS_SELECT = [2020, 2021, 2022, 2023, 2024]  # 最近 5 年
```

## 常见问题

### Q: 分配不到 A100 怎么办?

Colab 免费版通常只有 T4 (16GB), 完全无法跑 70B。
- 升级到 Pro+ 获得 A100 优先权
- 或者用 L4 (24GB) 跑 14B 模型

### Q: 会话超时断开了?

正常现象。Colab Pro+ 最长 ~24 小时，Pro ~12 小时。
- 断点续传会保存进度
- 重新连接后从 Cell 5 开始运行即可

### Q: vLLM 安装失败?

```python
# 尝试指定版本
!pip install vllm==0.6.0
```

### Q: GPU OOM (显存不足)?

```python
# 降低显存使用率
GPU_MEMORY_UTIL = 0.85
# 降低最大上下文长度
MAX_MODEL_LEN = 4096
# 降低 batch size (在 Cell 7 中修改)
BATCH_SIZE = 16
```

### Q: 如何估算费用?

- Colab Pro+: $49.99/月 (无限 A100 使用)
- 单个 AAPL (28K 条): ~3-4 天
- 一个月可以跑 ~7-8 个 symbol
- 全部 29 个 symbol: ~4 个月 ≈ $200

## 本地推理命令参考

如果你选择在本地用黄金切片法处理:

```powershell
# 黄金切片 5 年, 单个 symbol
python src/local_data_pipeline_inference.py -s AAPL --golden-slice 5

# 指定年份
python src/local_data_pipeline_inference.py -s AAPL --years-select 2020 2021 2022 2023 2024

# 黄金切片 5 年, 所有 symbols
python src/local_data_pipeline_inference.py --golden-slice 5

# 测试: 黄金切片 3 年, 每年限制 10 条
python src/local_data_pipeline_inference.py -s AAPL --golden-slice 3 --limit 10
```
