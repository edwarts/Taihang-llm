# WSL2 + vLLM 部署清单

## 📋 部署前检查

- [ ] 已安装WSL2 (`wsl --version` 能输出版本号)
- [ ] AMD AI Max 395+ 驱动正常工作
- [ ] Windows PowerShell 或 cmd 可用
- [ ] 有100+ GB 磁盘空间（用于模型下载）
- [ ] 网络连接良好

## 🚀 快速部署（选择一个）

### 方案A：一键启动（推荐）
```powershell
# Windows PowerShell，进入项目目录
cd C:\code-base\Taihang-llm

# 第一次运行（安装依赖）
wsl bash -c "cd /mnt/c/code-base/Taihang-llm && python3 -m venv venv_vllm && source venv_vllm/bin/activate && pip install -q vllm[rocm]"

# 启动vLLM
.\start_vllm.bat
```

### 方案B：手动配置
```bash
# WSL2内逐步执行
wsl
cd /mnt/c/code-base/Taihang-llm
python3 -m venv venv_vllm
source venv_vllm/bin/activate
pip install vllm[rocm]
bash vllm_startup.sh
```

## ⚙️ 配置步骤

### 1️⃣ 启动vLLM
```powershell
# 新建一个PowerShell窗口
cd C:\code-base\Taihang-llm
wsl bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh
```

**等待输出：** `[START] Launching vLLM...`

### 2️⃣ 获取WSL2 IP
```bash
# vLLM启动后，会显示 WSL2 IP，形如:
# [INFO] WSL2 IP: 172.31.194.125
```

或手动获取：
```bash
# 在WSL2终端中运行
hostname -I
```

### 3️⃣ 更新配置文件
编辑 `src/local_data_pipeline_inference.py`，找到第19行：
```python
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 改成你的IP！
USE_VLLM = True  # 启用vLLM
```

### 4️⃣ 测试连接
```powershell
# Windows PowerShell 中测试
python -c "
import requests
try:
    r = requests.get('http://172.31.194.125:8000/v1/models', timeout=5)
    print('[OK] vLLM connected:', r.json())
except Exception as e:
    print('[ERROR]', e)
"
```

### 5️⃣ 运行推理
```powershell
# Windows PowerShell
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

## 📊 验证成功标志

✅ **vLLM启动时**
```
[INFO] Ollama is running. Available models: ...
[INFO] Configured connection pool with 25 max connections
```

✅ **推理开始时**
```
[START] Local DeepSeek-R1 Inference Pipeline
[CONFIG] Backend: vLLM
[CONFIG] API URL: http://172.31.xxx.xxx:8000
```

✅ **推理过程中**
```
[INFO] Processing 28389 prompts for AAPL...
Inferencing AAPL: 15%|███       | 4000/28389 [5:20<30:00, 13.3/s]
```

**预期速度：** 10-15个prompts/秒（相比Ollama的0.007个prompts/秒快2000倍！）

## 🆘 故障排查

| 问题 | 症状 | 解决方案 |
|------|------|---------|
| WSL2无GPU | `rocm-smi` 找不到 | 重装AMD驱动或WSL2 |
| 无法连接vLLM | `Connection refused` | 检查WSL2 IP和端口8000 |
| 显存不足 | CUDA OOM错误 | 降低 `--gpu-memory-utilization` 到0.8 |
| 模型下载失败 | 网络超时 | 检查网络或使用代理 |
| vLLM启动很慢 | 首次启动卡很久 | 正常，第一次要编译kernels |

## 🎯 性能目标

| 指标 | 目标 | 实际 |
|------|------|------|
| 单个prompt耗时 | 20-40s | ? |
| 吞吐量 | 10-15/s | ? |
| 28k prompts总时间 | 8小时 | ? |
| GPU利用率 | >90% | ? |

## 📁 关键文件位置

| 文件 | 位置 | 说明 |
|------|------|------|
| 推理代码 | `src/local_data_pipeline_inference.py` | 改这里的`VLLM_BASE_URL` |
| 配置文件 | `src/inference_config.py` | 高级配置选项 |
| 启动脚本 | `start_vllm.bat` / `vllm_startup.sh` | 一键启动 |
| 输入数据 | `data/deepseek_r1_input_prompts_*.jsonl` | CTA生成的prompts |
| 输出数据 | `data/deepseek_r1_reasoning_*.jsonl` | 推理结果 |

## 💡 常用命令

```powershell
# 启动vLLM
.\start_vllm.bat

# 测试推理（3个symbols）
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA

# 全量运行（30个symbols）
python src/local_data_pipeline_inference.py

# 切换回Ollama
# 编辑 src/local_data_pipeline_inference.py，改 USE_VLLM = False

# 查看GPU使用（WSL2终端）
watch -n 1 rocm-smi
```

## 📚 详细文档

- **快速开始**: `VLLM_QUICKSTART.md` (推荐先读)
- **完整部署**: `WSL2_VLLM_SETUP.md` (详细步骤)
- **配置参考**: `INFERENCE_BACKEND_CONFIG.md` (高级选项)

## ✨ 预期改进

```
Windows Ollama:     150s/prompt × 28389 = 110 小时 ⭐⭐
WSL2 vLLM:          30s/prompt × 28389 = 8 小时   ⭐⭐⭐⭐⭐

性能提升: 13.75倍 🚀
```

---

**准备好了？** → 开始第1步：启动vLLM！
