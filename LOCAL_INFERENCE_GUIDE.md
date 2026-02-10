# Local DeepSeek-R1 Inference Pipeline (Ollama)

## Overview

基于Windows本地Ollama的DeepSeek-R1:70b推理管道，用于处理交易提示词生成推理输出。

## 核心特性

✅ **本地推理** - 使用Ollama运行DeepSeek-R1:70b，无需API调用
✅ **多symbol支持** - 自动遍历config.py中的TARGET_SYMBOLS
✅ **智能文件加载** - 支持prompt文件自动降级fallback
✅ **个别+合并输出** - 每个symbol的单独推理结果+合并文件
✅ **批处理** - 内存管理和进度显示

## 安装前置条件

### 1. 安装Ollama (Windows)
```
https://ollama.ai/download
# 或 Windows Package Manager:
winget install ollama
```

### 2. 拉取DeepSeek-R1模型
```powershell
ollama pull deepseek-r1:70b
```

### 3. 启动Ollama服务
```powershell
ollama serve
# 默认运行在 http://localhost:11434
```

### 4. 安装Python依赖
```powershell
pip install requests tqdm pandas numpy
```

## 快速开始

### 处理所有symbols（默认5m窗口，15年数据）
```powershell
python src/local_data_pipeline_inference.py
```

**输出:**
- 每个symbol: `deepseek_r1_reasoning_AAPL_5m_15y.jsonl`
- 合并文件: `deepseek_r1_reasoning_CONSOLIDATED_33symbols_5m_15y.jsonl`

### 处理特定symbols
```powershell
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

### 使用不同窗口和年份
```powershell
python src/local_data_pipeline_inference.py -w 1m -y 10
```

### 查看帮助
```powershell
python src/local_data_pipeline_inference.py --help
```

## 文件格式

### 输入文件（Prompt Files）
```
data/deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
```

每行是JSON对象：
```json
{
  "custom_id": "AAPL_2024-01-15T09:30:00",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "deepseek-reasoner",
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "Market analysis prompt..."}
    ]
  }
}
```

### 输出文件（Reasoning Results）
```
data/deepseek_r1_reasoning_AAPL_5m_15y.jsonl
```

每行是推理结果：
```json
{
  "symbol": "AAPL",
  "custom_id": "AAPL_2024-01-15T09:30:00",
  "prompt": "Market analysis prompt...",
  "reasoning": "DeepSeek R1的推理输出...",
  "window": "5m",
  "years": 15
}
```

## 配置说明

在脚本中修改以下常量：

```python
# Ollama配置
OLLAMA_BASE_URL = "http://localhost:11434"     # Ollama服务地址
OLLAMA_MODEL = "deepseek-r1:70b"               # 模型名称
OLLAMA_TIMEOUT = 300                           # 超时时间（秒）

# 路径配置
PROMPT_DIR = "data"                            # Prompt文件目录
OUTPUT_DIR = "data"                            # 输出目录

# 默认参数
DEFAULT_WINDOW = "5m"                          # 默认窗口
DEFAULT_YEARS = 15                             # 默认年份
BATCH_SIZE = 5                                 # 批处理大小
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --symbols` | 要处理的symbols (空格分隔) | 所有symbols |
| `-w, --window` | 时间框架 | 5m |
| `-y, --years` | 历史年份 | 15 |
| `--prompt-dir` | Prompt文件目录 | data |
| `--ollama-url` | Ollama服务地址 | http://localhost:11434 |

## 工作流程

```
1. 连接Ollama服务
   ↓
2. 获取要处理的symbols列表
   ↓
3. 对于每个symbol:
   a) 加载prompt文件 (with fallback)
   b) 遍历每个prompt
   c) 调用DeepSeek-R1进行推理
   d) 保存单个symbol结果
   ↓
4. 合并所有结果到consolidated文件
   ↓
5. 输出汇总报告
```

## 输出示例

```
======================================================================
[START] Local DeepSeek-R1 Inference Pipeline
======================================================================
[CONFIG] Symbols: 3
[CONFIG] Window: 5m
[CONFIG] Years: 15
[CONFIG] Prompt Directory: data
[CONFIG] Ollama Model: deepseek-r1:70b
======================================================================

[INFO] Ollama is running. Available models: ['deepseek-r1:70b']

[1/3] Processing AAPL...
[SUCCESS] Loaded 5200 prompts from deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
[INFO] Processing 5200 prompts for AAPL...
Inferencing AAPL: 100%|████| 5200/5200 [45:30<00:00, 1.90it/s]
[RESULT] AAPL: 5200/5200 prompts processed successfully
[SUCCESS] Saved 5200 results to deepseek_r1_reasoning_AAPL_5m_15y.jsonl

[2/3] Processing MSFT...
[SUCCESS] Loaded 4800 prompts from deepseek_r1_input_prompts_MSFT_5m_15y.jsonl
...

[INFO] Saving consolidated reasoning results...
[SUCCESS] Consolidated file created: deepseek_r1_reasoning_CONSOLIDATED_3symbols_5m_15y.jsonl
[INFO] Total records in consolidated file: 15200

======================================================================
[SUMMARY] DeepSeek-R1 Inference Report
======================================================================
[RESULT] Successful: 3/3
[RESULT] Failed: 0/3

[SUCCESS] Processed symbols:
  - AAPL: 5200 reasoning outputs
  - MSFT: 4800 reasoning outputs
  - NVDA: 5200 reasoning outputs

======================================================================
[COMPLETE] Inference pipeline finished!
[OUTPUT] Results saved to: data/
```

## 常见问题

### Q: Ollama连接失败
**A:** 确保Ollama正在运行：
```powershell
ollama serve
```

### Q: 模型未找到
**A:** 拉取模型：
```powershell
ollama pull deepseek-r1:70b
```

### Q: 推理很慢
**A:** 这是正常的。DeepSeek-R1:70b的推理时间取决于：
- 硬件性能（GPU内存）
- Prompt长度
- 温度参数（temperature）

估计时间：每个prompt 30-120秒

### Q: Prompt文件找不到
**A:** 检查：
1. Prompt文件是否存在于`data/`目录
2. 文件命名是否正确：`deepseek_r1_input_prompts_SYMBOL_WINDOW_YEARy.jsonl`
3. 是否已运行pipeline_main_cta_structure.py生成prompt文件

## 故障排除

### 连接Ollama失败
```powershell
# 检查Ollama服务状态
curl http://localhost:11434/api/tags
```

### 内存不足 (OOM)
减小BATCH_SIZE：
```python
BATCH_SIZE = 1  # 一次处理1个symbol
```

### 模型加载失败
```powershell
# 重新启动Ollama
Stop-Process -Name ollama
ollama serve
```

## 性能优化

### 1. 降低温度以加快推理
```python
# 在OllamaDeepSeekInferencer.generate_reasoning()
reasoning_output = self.inferencer.generate_reasoning(
    prompt_text, 
    temperature=0.3  # 默认0.7，降低为更确定的输出
)
```

### 2. 减小超时时间
```python
OLLAMA_TIMEOUT = 120  # 从300秒改为120秒
```

### 3. 批量处理
当处理大量symbols时，分批处理以管理内存：
```powershell
# 第一批
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA GOOGL AMZN

# 第二批
python src/local_data_pipeline_inference.py -s TSLA AMD NFLX ...
```

## 输出文件说明

### 个别结果文件
- 文件名：`deepseek_r1_reasoning_{SYMBOL}_{WINDOW}_{YEARS}y.jsonl`
- 用途：详细分析特定symbol的推理过程
- 大小：取决于symbol的prompt数量

### 合并结果文件
- 文件名：`deepseek_r1_reasoning_CONSOLIDATED_{N}symbols_{WINDOW}_{YEARS}y.jsonl`
- 用途：批量训练或统一分析
- 大小：所有symbol的总和

## 下一步

1. 完成推理：`python src/local_data_pipeline_inference.py`
2. 分析结果：审查`data/deepseek_r1_reasoning_*.jsonl`文件
3. 数据清洗：提取reasoning输出，格式化为训练数据
4. 模型微调：使用结果数据微调下游交易模型

## 技术细节

### Ollama API调用
```python
POST http://localhost:11434/api/generate
{
  "model": "deepseek-r1:70b",
  "prompt": "...",
  "temperature": 0.7,
  "stream": false
}
```

### 错误处理
- 连接失败：自动重试
- Prompt处理失败：记录错误，继续处理下一个
- 文件保存失败：输出警告但继续

## 许可证

遵循原项目许可证

---

**状态: ✅ 完成，可以生产使用**

本推理管道已准备好使用Windows Ollama处理所有33个TARGET_SYMBOLS的推理任务。
