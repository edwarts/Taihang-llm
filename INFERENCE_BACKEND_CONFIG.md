# 推理后端配置指南

## 支持的后端

| 后端 | 位置 | 性能 | 配置复杂度 |
|------|------|------|----------|
| **Ollama** | Windows本地 | ⭐⭐ (150s/prompt) | ⭐ 简单 |
| **vLLM** | WSL2 Linux | ⭐⭐⭐⭐⭐ (20-40s/prompt) | ⭐⭐⭐ 中等 |

---

## 方法A：使用Ollama（Windows）- 最简单

### 前置条件
- Windows上已安装Ollama
- `ollama serve` 运行中

### 配置
编辑 `src/local_data_pipeline_inference.py`：
```python
USE_VLLM = False  # 使用Ollama
```

或者环境变量：
```powershell
$env:INFERENCE_BACKEND = "ollama"
```

### 启动
```powershell
python src/local_data_pipeline_inference.py -s AAPL
```

**性能:** ~150秒/prompt = 110小时 (28k prompts)

---

## 方法B：使用vLLM（WSL2）- 最快

### 前置条件
- Windows上已安装WSL2 (Ubuntu 22.04)
- AMD GPU驱动正常

### 一句话启动

**第一次部署（5分钟）：**
```powershell
# Windows PowerShell
.\start_vllm.bat
```

**日常使用（启动vLLM）：**
```powershell
# Windows PowerShell
wsl bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh
```

### 手动配置步骤

#### 1. WSL2内安装vLLM（15分钟）
```bash
wsl
cd /mnt/c/code-base/Taihang-llm

# 创建虚拟环境
python3 -m venv venv_vllm
source venv_vllm/bin/activate

# 安装vLLM
pip install --upgrade pip
pip install vllm[rocm]
```

#### 2. WSL2内启动vLLM服务
```bash
source venv_vllm/bin/activate
bash vllm_startup.sh
```

**保存输出的IP地址！** (形如 `172.31.xxx.xxx`)

#### 3. Windows内更新配置
编辑 `src/local_data_pipeline_inference.py`，第19行：
```python
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 改成你的WSL2 IP!
USE_VLLM = True
```

#### 4. Windows内运行推理
```powershell
python src/local_data_pipeline_inference.py -s AAPL MSFT
```

**性能:** ~30秒/prompt = 8小时 (28k prompts)

---

## 方法C：环境变量配置（推荐用于脚本化）

### 设置环境变量
```powershell
# Windows PowerShell
$env:INFERENCE_BACKEND = "vllm"
$env:VLLM_API_URL = "http://172.31.194.125:8000"
$env:CONCURRENT_REQUESTS = "25"
```

或创建 `.env` 文件：
```bash
INFERENCE_BACKEND=vllm
VLLM_API_URL=http://172.31.194.125:8000
CONCURRENT_REQUESTS=25
TEMPERATURE=0.7
```

然后在Python中：
```python
from src.inference_config import get_backend_config, print_config
config = get_backend_config()
print_config()
```

---

## 常见问题

### Q: 如何知道WSL2的IP地址？
```bash
# WSL2终端内运行
hostname -I
```
输出第一个数字就是IP，形如 `172.31.194.125`

### Q: 如何在Ollama和vLLM间快速切换？
编辑代码改一行：
```python
USE_VLLM = True   # vLLM
USE_VLLM = False  # Ollama
```

或用环境变量：
```powershell
$env:INFERENCE_BACKEND = "vllm"   # 或 "ollama"
```

### Q: vLLM和Ollama能同时运行吗？
可以，但会占用GPU显存。建议选择一个。

### Q: 如果WSL2 IP经常变化怎么办？
在 `vllm_startup.sh` 中有自动打印IP的功能。或固定WSL2 IP（见WSL2_VLLM_SETUP.md）。

### Q: 推理效果是否有区别？
模型和参数一样时，推理结果完全相同。只是速度不同。

---

## 性能调优

### 对于Ollama
```powershell
# 增加并发数
python src/local_data_pipeline_inference.py -s AAPL MSFT &
python src/local_data_pipeline_inference.py -s NVDA TSLA &
```

### 对于vLLM
```bash
# 编辑 vllm_startup.sh，调整以下参数：

# 增加显存利用
--gpu-memory-utilization 0.95  # 改为 0.98

# 增加max_model_len用于更长的输入
--max-model-len 8192  # 改为更大值

# 启用自适应分桶（batch操作）
--enable-lora  # 可选，需要LoRA支持

# 减少输出显存消耗
--dtype bfloat16  # 从float16改为bfloat16
```

---

## 完整工作流

### 场景1：快速测试（3个symbols）
```powershell
# 启动vLLM（新终端）
wsl bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh

# 等待提示"启动成功"，然后在主终端运行：
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

### 场景2：大规模运行（30个symbols）
```powershell
# vLLM已在后台运行
python src/local_data_pipeline_inference.py
# 默认处理所有30个symbols
```

### 场景3：持续运行（所有symbols，多次）
```bash
# WSL2内，venv_vllm激活状态
while true; do
  python /mnt/c/code-base/Taihang-llm/src/local_data_pipeline_inference.py
  sleep 3600  # 每小时运行一次
done
```

---

## 文件结构

```
Taihang-llm/
├── src/
│   ├── local_data_pipeline_inference.py  # 推理pipeline（支持两个后端）
│   └── inference_config.py               # 后端配置管理
├── WSL2_VLLM_SETUP.md                   # WSL2+vLLM详细部署指南
├── VLLM_QUICKSTART.md                   # vLLM快速开始
├── vllm_startup.sh                      # WSL2内启动vLLM脚本
├── start_vllm.bat                       # Windows启动脚本
└── data/
    ├── deepseek_r1_input_prompts_*.jsonl  # 输入prompts
    └── deepseek_r1_reasoning_*.jsonl      # 输出推理结果
```

---

## 快速参考表

| 任务 | Ollama | vLLM |
|------|--------|------|
| 启动方式 | `ollama serve` | `bash vllm_startup.sh` (WSL2) |
| 配置代码行 | `USE_VLLM = False` | `USE_VLLM = True` |
| 单个prompt时间 | ~150s | ~30s |
| 全量28k prompts | 110小时 | 8小时 |
| GPU需求 | 24GB+ | 128GB (充分利用) |
| 推荐用于 | 快速测试 | 生产推理 |

---

## 选择指南

**选择Ollama如果：**
- ✅ 只做测试
- ✅ 不想配置WSL2
- ✅ 只有少量prompts (<1000)

**选择vLLM如果：**
- ✅ 需要快速推理
- ✅ 处理大量prompts (>5000)
- ✅ 已有AMD GPU
- ✅ 不怕配置复杂度

---

## 支持

遇到问题？检查：
1. `WSL2_VLLM_SETUP.md` - 详细部署指南
2. `VLLM_QUICKSTART.md` - 快速开始
3. 本文档 - 配置参考
