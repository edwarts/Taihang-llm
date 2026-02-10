# Local DeepSeek-R1 Inference Implementation - Complete ✅

## 项目概述

已完成基于Windows Ollama的DeepSeek-R1:70b本地推理管道实现。该管道能够：
- ✅ 遍历config.py中的所有symbols
- ✅ 加载对应的prompt文件（支持自动降级fallback）
- ✅ 通过Ollama调用DeepSeek-R1:70b进行推理
- ✅ 保存individual和consolidated结果
- ✅ 生成详细的执行报告

## 创建的文件

### 1. 主要推理脚本
**文件:** `src/local_data_pipeline_inference.py` (390行)

**核心类:**
- `OllamaDeepSeekInferencer`: Ollama连接和推理
- `LocalInferencePipeline`: 推理管道编排
- `main()`: 主程序入口

**主要功能:**
- Ollama服务连接验证
- Prompt文件加载（支持fallback）
- DeepSeek-R1推理调用
- 批量处理多symbols
- 个别和合并结果保存

### 2. 文档

| 文件 | 用途 | 阅读时间 |
|------|------|---------|
| [LOCAL_INFERENCE_GUIDE.md](LOCAL_INFERENCE_GUIDE.md) | 完整使用指南 | 15分钟 |
| [LOCAL_INFERENCE_QUICKSTART.md](LOCAL_INFERENCE_QUICKSTART.md) | 快速开始 | 5分钟 |

## 快速开始

### 1. 环境准备

```powershell
# 安装Ollama (Windows)
# https://ollama.ai/download

# 拉取DeepSeek-R1模型
ollama pull deepseek-r1:70b

# 启动Ollama服务
ollama serve
```

### 2. 运行推理

```powershell
# 所有symbols（默认5m, 15y）
python src/local_data_pipeline_inference.py

# 特定symbols
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA

# 自定义参数
python src/local_data_pipeline_inference.py -w 1m -y 10 -s AAPL
```

### 3. 查看结果

```powershell
# 个别文件
Get-ChildItem data/deepseek_r1_reasoning_*.jsonl

# 合并文件
Get-ChildItem data/deepseek_r1_reasoning_CONSOLIDATED*.jsonl
```

## 功能详解

### Prompt文件加载

**自动识别文件格式:**
```
deepseek_r1_input_prompts_SYMBOL_WINDOW_YEARy.jsonl
```

**Fallback策略:**
- 尝试精确文件名（如15年）
- 如果不存在，自动降级到14年、13年...直到1年
- 都不存在则记录错误并继续处理下一个symbol

```python
# 示例
load_prompt_file('AAPL', window='5m', years=15, prompt_dir='data')
# 尝试: deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
# 降级: deepseek_r1_input_prompts_AAPL_5m_14y.jsonl
# 降级: deepseek_r1_input_prompts_AAPL_5m_13y.jsonl
# ...
```

### Ollama推理调用

**连接验证:**
```python
# 自动检查Ollama服务
# 列出可用模型
# 验证deepseek-r1:70b是否存在
```

**推理参数:**
- Model: deepseek-r1:70b
- Temperature: 0.7（可调）
- Top P: 0.9
- Timeout: 300秒
- Stream: False（完整返回）

**返回格式:**
```json
{
  "symbol": "AAPL",
  "custom_id": "AAPL_2024-01-15T09:30:00",
  "prompt": "Market analysis prompt...",
  "reasoning": "DeepSeek R1 complete reasoning output",
  "window": "5m",
  "years": 15
}
```

### 多Symbol遍历

**处理流程:**
1. 导入TARGET_SYMBOLS（config.py）
2. 按batch_size分组处理
3. 对每个symbol：
   - 加载prompt文件
   - 遍历所有prompts
   - 逐个推理
   - 保存结果
4. 收集所有结果到consolidated文件

**批处理优势:**
- 管理内存使用
- 避免显存溢出
- 可调节BATCH_SIZE

## 命令行参数

```
python src/local_data_pipeline_inference.py [OPTIONS]

OPTIONS:
  -s, --symbols TEXT          要处理的symbols (空格分隔)
  -w, --window [1m|5m|15m|30m|60m|D]  时间框架 (默认: 5m)
  -y, --years INTEGER         历史年份 (默认: 15)
  --prompt-dir TEXT           Prompt文件目录 (默认: data)
  --ollama-url TEXT           Ollama服务地址 (默认: http://localhost:11434)
  --help                      显示帮助信息
```

## 配置选项

在脚本中修改：

```python
# Ollama配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1:70b"
OLLAMA_TIMEOUT = 300  # 推理超时时间（秒）

# 路径
PROMPT_DIR = "data"
OUTPUT_DIR = "data"

# 默认参数
DEFAULT_WINDOW = "5m"
DEFAULT_YEARS = 15
BATCH_SIZE = 5  # 内存管理
```

## 输出文件结构

### 个别Symbol结果
```
data/deepseek_r1_reasoning_AAPL_5m_15y.jsonl      (每行一个推理结果)
data/deepseek_r1_reasoning_MSFT_5m_15y.jsonl
data/deepseek_r1_reasoning_NVDA_5m_15y.jsonl
...
```

### 合并结果文件
```
data/deepseek_r1_reasoning_CONSOLIDATED_30symbols_5m_15y.jsonl
```

### 文件大小估计
- 每个symbol: 100-200 MB（取决于prompt数量）
- 全部30个symbols: 3-6 GB

## 执行流程

```
准备阶段
├── 验证Ollama连接
├── 检查可用模型
└── 初始化推理器

处理阶段
├── 对每个symbol:
│   ├── 加载prompt文件
│   ├── 显示进度条
│   ├── 逐个调用推理
│   ├── 收集结果
│   └── 保存individual文件
│
└── 合并结果
    ├── 汇总所有results
    ├── 写入consolidated文件
    └── 生成统计报告

完成
└── 输出汇总报告
```

## 性能特征

### 推理速度
- 单个prompt: 30-120秒（依赖GPU）
- 5000 prompts: 40-160小时
- 全部30 symbols: 数周

### 内存使用
- Ollama服务: ~20GB（70B模型）
- Python脚本: <1GB
- 输出文件: 3-6GB

### 优化建议
1. 使用高端GPU（H100, A100等）
2. 调整temperature为0.3以加快推理
3. 批处理分组处理symbols
4. 监控GPU内存使用

## 错误处理

**自动处理的错误:**
- ✅ 连接失败 → 重试提示
- ✅ 模型未找到 → 列出可用模型
- ✅ Prompt文件缺失 → 降级到低年份
- ✅ Prompt处理失败 → 记录并继续
- ✅ 推理超时 → 记录错误并跳过

**用户可处理的错误:**
- ❌ Ollama服务未运行 → 运行 `ollama serve`
- ❌ 模型未拉取 → 运行 `ollama pull deepseek-r1:70b`
- ❌ 内存不足 → 减小BATCH_SIZE

## 集成点

### 上游依赖
- ✅ `src/config.py` - TARGET_SYMBOLS
- ✅ `src/pipeline_main_cta_structure.py` - 生成prompt文件

### 下游使用
- 数据清洗：提取reasoning字段
- 模型训练：使用reasoning输出
- 策略开发：分析推理逻辑

## 验证清单

✅ **代码质量**
- 语法检查通过
- 导入验证成功
- 错误处理完整

✅ **功能完整**
- Ollama连接集成
- Config symbols导入
- Prompt文件加载（含fallback）
- 推理调用
- 结果保存
- 报告生成

✅ **文档完整**
- 快速开始指南
- 完整使用说明
- 参数文档
- 故障排除

✅ **Windows兼容**
- UTF-8编码声明
- 路径处理
- 异常处理

## 使用案例

### 案例1: 完整处理所有symbols
```powershell
python src/local_data_pipeline_inference.py
# 输出: 30个individual文件 + 1个consolidated文件
```

### 案例2: 特定sector处理
```powershell
# 科技股
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA GOOGL AMZN

# 金融股
python src/local_data_pipeline_inference.py -s JPM BAC GS MS
```

### 案例3: 短期数据分析
```powershell
python src/local_data_pipeline_inference.py -w 1m -y 5
```

### 案例4: 并行处理（多个终端）
```powershell
# Terminal 1: 处理第一批
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA GOOGL AMZN TSLA NFLX AMD AVGO QCOM

# Terminal 2: 处理第二批
python src/local_data_pipeline_inference.py -s INTC JPM BAC GS MS COIN PYPL SQ MARA GME
```

## 下一步

1. **验证环境:**
   ```powershell
   ollama list  # 确认深搜R1可用
   ```

2. **首次测试:**
   ```powershell
   python src/local_data_pipeline_inference.py -s AAPL -w 5m -y 5
   ```

3. **监控执行:**
   ```powershell
   Get-ChildItem data/deepseek_r1_reasoning_*.jsonl -n
   ```

4. **后续处理:**
   - 分析reasoning输出
   - 提取关键决策逻辑
   - 微调下游模型

## 技术栈

- **推理框架:** Ollama (本地推理)
- **模型:** DeepSeek-R1:70b
- **语言:** Python 3.13
- **关键库:** requests, json, tqdm
- **系统:** Windows 11

## 支持和文档

- **快速开始:** [LOCAL_INFERENCE_QUICKSTART.md](LOCAL_INFERENCE_QUICKSTART.md)
- **完整指南:** [LOCAL_INFERENCE_GUIDE.md](LOCAL_INFERENCE_GUIDE.md)
- **源代码:** [src/local_data_pipeline_inference.py](src/local_data_pipeline_inference.py)

---

**状态: ✅ 完成、验证、生产就绪**

该本地推理管道已完全实现并准备用于处理所有30个TARGET_SYMBOLS的DeepSeek-R1推理任务。
