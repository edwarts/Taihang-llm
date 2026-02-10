# Local Inference Pipeline - Updated Features

## 📋 更新内容

已更新 `src/local_data_pipeline_inference.py` 以支持CTA风格的自动配置和时间戳：

### ✅ 新增功能

**1. 默认无参数运行**
- 默认处理所有 TARGET_SYMBOLS（来自config.py）
- 默认窗口：5m
- 默认年份：15y
- 无需任何命令行参数即可运行

```powershell
# 直接运行，处理全部symbols，默认5m, 15y
python src/local_data_pipeline_inference.py
```

**2. 智能合并策略**
- 单个symbol：仅生成individual文件，不合并
- 多个symbols（≥2）：自动生成consolidated文件
- 合并文件仅在有意义时创建

**3. 时间戳支持**
- Individual文件格式：`deepseek_r1_reasoning_SYMBOL_5m_15y_YYYYMMDD_HHMMSS.jsonl`
- Consolidated文件格式：`deepseek_r1_reasoning_CONSOLIDATED_Nsymbols_5m_15y_YYYYMMDD_HHMMSS.jsonl`
- 时间戳精确到秒，方便追溯和版本管理

## 🚀 使用方式

### 场景1：处理所有symbols（推荐）
```powershell
python src/local_data_pipeline_inference.py
```
**输出：**
- 30个individual文件：`deepseek_r1_reasoning_AAPL_5m_15y_20260205_143022.jsonl` 等
- 1个consolidated文件：`deepseek_r1_reasoning_CONSOLIDATED_30symbols_5m_15y_20260205_143022.jsonl`

### 场景2：处理单个symbol
```powershell
python src/local_data_pipeline_inference.py -s AAPL
```
**输出：**
- 仅1个individual文件：`deepseek_r1_reasoning_AAPL_5m_15y_20260205_143022.jsonl`
- ❌ 无consolidated文件（因为只有1个symbol）

### 场景3：处理多个symbols
```powershell
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA GOOGL AMZN
```
**输出：**
- 5个individual文件
- 1个consolidated文件：`deepseek_r1_reasoning_CONSOLIDATED_5symbols_5m_15y_20260205_143022.jsonl`

### 场景4：自定义参数
```powershell
python src/local_data_pipeline_inference.py -w 1m -y 10
```
**输出：**
- 30个individual文件：`deepseek_r1_reasoning_SYMBOL_1m_10y_TIMESTAMP.jsonl`
- 1个consolidated文件：`deepseek_r1_reasoning_CONSOLIDATED_30symbols_1m_10y_TIMESTAMP.jsonl`

## 📁 输出文件示例

```
data/
├── deepseek_r1_reasoning_AAPL_5m_15y_20260205_143022.jsonl        (5,200 records)
├── deepseek_r1_reasoning_MSFT_5m_15y_20260205_143025.jsonl        (4,800 records)
├── deepseek_r1_reasoning_NVDA_5m_15y_20260205_143028.jsonl        (5,100 records)
└── deepseek_r1_reasoning_CONSOLIDATED_30symbols_5m_15y_20260205_143030.jsonl  (150,100 records)
```

## 🔧 命令行参数

所有参数都是可选的，默认值为：

| 参数 | 默认 | 说明 |
|------|------|------|
| `-s, --symbols` | 所有symbols | 特定symbols列表 |
| `-w, --window` | 5m | 时间窗口 |
| `-y, --years` | 15 | 历史年份 |
| `--prompt-dir` | data | Prompt文件目录 |
| `--ollama-url` | http://localhost:11434 | Ollama服务地址 |

## 📊 关键改变

### 时间戳格式
- 格式：YYYYMMDD_HHMMSS (UTC)
- 示例：20260205_143022 (2026年2月5日 14:30:22)
- 用途：防止文件覆盖，便于版本控制

### 合并条件
```python
# 伪代码
if len(successful) > 1 and all_consolidated_results:
    save_consolidated_file()
```

- ✅ 2个symbols → 合并
- ✅ 30个symbols → 合并
- ❌ 1个symbol → 不合并

## 📝 典型执行日志

```
======================================================================
[START] Local DeepSeek-R1 Inference Pipeline
======================================================================
[CONFIG] Symbols: 30
[CONFIG] Window: 5m
[CONFIG] Years: 15
[CONFIG] Prompt Directory: data
[CONFIG] Ollama Model: deepseek-r1:70b
======================================================================

[1/30] Processing AAPL...
[SUCCESS] Loaded 5200 prompts from deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
[INFO] Processing 5200 prompts for AAPL...
Inferencing AAPL: 100%|████| 5200/5200 [45:30<00:00, 1.90it/s]
[RESULT] AAPL: 5200/5200 prompts processed successfully
[SUCCESS] Saved 5200 results to deepseek_r1_reasoning_AAPL_5m_15y_20260205_143022.jsonl

[2/30] Processing MSFT...
...

[INFO] Saving consolidated reasoning results...
[SUCCESS] Consolidated file created: deepseek_r1_reasoning_CONSOLIDATED_30symbols_5m_15y_20260205_143030.jsonl
[INFO] Total records in consolidated file: 150100

======================================================================
[SUMMARY] DeepSeek-R1 Inference Report
======================================================================
[RESULT] Successful: 30/30
[RESULT] Failed: 0/30
[SUCCESS] Processed symbols: AAPL, MSFT, NVDA, GOOGL, ...
======================================================================
[COMPLETE] Inference pipeline finished!
[OUTPUT] Results saved to: data/
```

## 💡 最佳实践

### 1. 首次运行测试
```powershell
# 小规模测试
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

### 2. 完整处理
```powershell
# 处理所有symbols，使用默认配置
python src/local_data_pipeline_inference.py
```

### 3. 批量处理不同参数
```powershell
# 不同窗口
python src/local_data_pipeline_inference.py -w 1m
python src/local_data_pipeline_inference.py -w 15m

# 不同历史长度
python src/local_data_pipeline_inference.py -y 5
python src/local_data_pipeline_inference.py -y 20
```

### 4. 追踪结果版本
由于有时间戳，可以轻松管理多个运行的结果：
```powershell
# 查看所有版本
Get-ChildItem data/deepseek_r1_reasoning_CONSOLIDATED*.jsonl | Sort-Object LastWriteTime -Descending
```

## 🔄 与CTA Pipeline对齐

✅ **Default Configuration**
- CTA: 默认5m, 10y → 已改为15y
- Inference: 默认5m, 15y ✓

✅ **Default Behavior**
- CTA: 无参数运行处理所有symbols
- Inference: 无参数运行处理所有symbols ✓

✅ **Output Files**
- CTA: Individual + Consolidated（多symbols时）
- Inference: Individual + Consolidated（多symbols时）✓

✅ **Timestamp Support**
- CTA: 可选时间戳
- Inference: 文件尾部时间戳 ✓

## ✅ 验证清单

- ✅ 语法检查通过
- ✅ 默认参数正确（5m, 15y）
- ✅ 无参数运行支持所有symbols
- ✅ 合并逻辑正确（>1 symbol时）
- ✅ 时间戳格式正确
- ✅ 文件命名规范
- ✅ 错误处理完善

---

**状态: ✅ 完成**

推理管道已更新，现在完全对齐CTA pipeline的模式和默认配置。
