# Quick Start: Local DeepSeek-R1 Inference

## Prerequisites

```powershell
# 1. Install Ollama (Windows)
# Download from https://ollama.ai/download

# 2. Pull DeepSeek-R1 model
ollama pull deepseek-r1:70b

# 3. Start Ollama service
ollama serve
# Keep this terminal running!
```

## Usage

### Default (All Symbols, 5m, 15y)
```powershell
python src/local_data_pipeline_inference.py
```

### Single Symbol
```powershell
python src/local_data_pipeline_inference.py -s AAPL
```

### Multiple Symbols
```powershell
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

### Custom Window & Years
```powershell
python src/local_data_pipeline_inference.py -w 1m -y 10
```

## Output Files

**Individual Results:**
```
data/deepseek_r1_reasoning_AAPL_5m_15y.jsonl
data/deepseek_r1_reasoning_MSFT_5m_15y.jsonl
...
```

**Consolidated:**
```
data/deepseek_r1_reasoning_CONSOLIDATED_33symbols_5m_15y.jsonl
```

## Record Format

```json
{
  "symbol": "AAPL",
  "custom_id": "AAPL_2024-01-15T09:30:00",
  "prompt": "Market analysis...",
  "reasoning": "DeepSeek R1 reasoning output...",
  "window": "5m",
  "years": 15
}
```

## Settings

Edit in `src/local_data_pipeline_inference.py`:

```python
OLLAMA_BASE_URL = "http://localhost:11434"  # Ollama URL
OLLAMA_MODEL = "deepseek-r1:70b"            # Model name
OLLAMA_TIMEOUT = 300                        # Timeout (seconds)

DEFAULT_WINDOW = "5m"                       # Default window
DEFAULT_YEARS = 15                          # Default years
BATCH_SIZE = 5                              # Batch size
```

## Parameters

```
-s, --symbols       Symbols to process (space-separated)
-w, --window        Window: 1m|5m|15m|30m|60m|D (default: 5m)
-y, --years         Years: 1-20 (default: 15)
--prompt-dir        Prompt directory (default: data)
--ollama-url        Ollama URL (default: http://localhost:11434)
```

## Typical Workflow

```
1. Ensure Ollama is running: ollama serve
2. Verify model is available: ollama list
3. Run inference: python src/local_data_pipeline_inference.py
4. Check results in data/ directory
5. Analyze deepseek_r1_reasoning_*.jsonl files
```

## Expected Performance

- Time per prompt: 30-120 seconds
- For 5,000 prompts: 40-160 hours
- For 1 symbol: 1-2 days with GPU

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Ollama not found | Install from https://ollama.ai/download |
| Model not found | Run: `ollama pull deepseek-r1:70b` |
| Connection error | Check: `ollama serve` is running |
| Out of memory | Reduce BATCH_SIZE to 1 |
| Slow inference | This is normal, DeepSeek-R1 takes time |

## Key Files

- **Code:** `src/local_data_pipeline_inference.py`
- **Guide:** `LOCAL_INFERENCE_GUIDE.md`
- **Input:** `data/deepseek_r1_input_prompts_*.jsonl`
- **Output:** `data/deepseek_r1_reasoning_*.jsonl`

---

**Ready to run!** Start with `python src/local_data_pipeline_inference.py`
