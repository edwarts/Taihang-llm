# vLLM GPU问题 - 完整诊断流程

## 快速修复流程

```
┌─────────────────────────────────────┐
│  vLLM启动失败: GPU驱动问题          │
└────────────┬────────────────────────┘
             │
             ├─→ 第1步: 运行诊断脚本
             │   bash check_gpu.sh
             │
             ├─→ 检查输出...
             │
             ├─? rocm-smi 找不到？
             │   YES → 安装ROCm (方案2)
             │   NO  → 继续
             │
             ├─? GPU设备未找到？
             │   YES → 检查硬件连接
             │   NO  → 继续
             │
             ├─? vLLM找不到？
             │   YES → 重装vLLM (方案3)
             │   NO  → 继续
             │
             ├─→ 第2步: 启用DEBUG日志
             │   export VLLM_LOGGING_LEVEL=DEBUG
             │
             └─→ 第3步: 尝试启动vLLM
                 bash vllm_startup.sh
```

---

## 逐步故障排查

### 阶段1：基础诊断

| 步骤 | 命令 | 预期结果 | 如果失败 |
|------|------|---------|---------|
| 1 | `rocm-smi` | GPU列表 | 安装ROCm |
| 2 | `hipconfig --version` | 版本号 | 安装HIP |
| 3 | `python -c "import vllm"` | 无报错 | 重装vLLM |
| 4 | `ls -la /dev/dri/` | GPU设备 | 硬件或驱动问题 |

### 阶段2：vLLM配置检查

```bash
# 检查vLLM能否加载模型
python -c "
import torch
print('PyTorch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('HIP available:', hasattr(torch, 'hip'))
print('Device count:', torch.cuda.device_count() if torch.cuda.is_available() else 'N/A')
"
```

### 阶段3：vLLM启动测试

```bash
# 启用日志并启动
export VLLM_LOGGING_LEVEL=DEBUG
python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-r1-distill-qwen-70b \
  --host 0.0.0.0 \
  --port 8000 \
  --device auto
```

---

## 常见问题及解决方案

### ❌ "rocm-smi: command not found"

**原因**: ROCm未安装

**解决**:
```bash
sudo apt update
sudo apt install -y rocm-dkms
sudo apt install -y hip-runtime-amd rocm-libs
rocm-smi  # 验证
```

**时间**: ~15分钟

---

### ❌ "rocm-smi: No AMD GPUs detected"

**原因**: 
- GPU驱动在Windows中异常
- WSL2无权限访问GPU
- 硬件连接问题

**解决**:
1. 重启WSL2:
```powershell
# Windows PowerShell
wsl --shutdown
wsl  # 重新启动
```

2. 在Windows中检查GPU:
   - 打开设备管理器
   - 查找AMD Radeon AI Max 395+
   - 确保驱动版本最新

3. 设置权限:
```bash
sudo usermod -a -G render $USER
sudo usermod -a -G video $USER
# 重新登录或运行: newgrp render
```

**时间**: ~5分钟

---

### ❌ "Failed to infer device type"

**原因**: vLLM无法识别任何计算设备

**解决**:
```bash
# 1. 重新安装vLLM
pip uninstall -y vllm
pip install vllm[rocm]

# 2. 清除缓存
rm -rf ~/.cache/huggingface/
rm -rf /tmp/vllm_*

# 3. 尝试启动，启用DEBUG
export VLLM_LOGGING_LEVEL=DEBUG
bash vllm_startup.sh
```

**时间**: ~10分钟

---

### ❌ "No module named vllm"

**原因**: vLLM未安装或虚拟环境错误

**解决**:
```bash
# 1. 确保在正确的虚拟环境
source venv_vllm/bin/activate

# 2. 重新安装
pip install --upgrade pip
pip install vllm[rocm]

# 3. 验证
python -c "import vllm; print(vllm.__version__)"
```

**时间**: ~10分钟

---

### ⚠️ "模型下载卡住"

**原因**: 网络问题或磁盘空间不足

**解决**:
```bash
# 1. 检查磁盘空间 (需要100+GB)
df -h

# 2. 手动下载模型
python -c "
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained('deepseek-ai/deepseek-r1-distill-qwen-70b')
model = AutoModel.from_pretrained('deepseek-ai/deepseek-r1-distill-qwen-70b')
"

# 3. 如果网络慢，使用代理
export HF_ENDPOINT=https://hf-mirror.com
```

**时间**: 根据网络速度

---

## 快速修复清单

### 轻度问题（可能解决）
- [ ] 运行 `bash check_gpu.sh` 诊断
- [ ] 如果ROCm缺失，安装: `sudo apt install rocm-dkms`
- [ ] 重启WSL2: `wsl --shutdown`
- [ ] 重新启动vLLM

### 中度问题（可能需要重装）
- [ ] 完全卸载并重装vLLM
- [ ] 清除缓存: `rm -rf ~/.cache/huggingface/`
- [ ] 更新ROCm: `sudo apt upgrade rocm-dkms`

### 重度问题（可能需要系统级修复）
- [ ] 更新Windows AMD GPU驱动
- [ ] 重新安装WSL2: `wsl --uninstall && wsl --install`
- [ ] 考虑使用Ollama代替vLLM
- [ ] 考虑在Windows中本地运行vLLM

---

## 备选方案

如果vLLM一直无法工作，可以用以下方案：

### 方案A: 使用Ollama（推荐）
- ✅ 易于安装和使用
- ✅ 无需GPU驱动配置复杂
- ✅ 内置量化优化
- ❌ 性能稍慢

```powershell
# Windows中
ollama serve
```

然后改代码:
```python
USE_VLLM = False
```

### 方案B: HuggingFace 推理API
```python
from transformers import pipeline
pipe = pipeline("text-generation", model="deepseek-ai/deepseek-r1-distill-qwen-70b")
```

### 方案C: 云服务推理
- Together AI
- RunPod
- Lambda Cloud

---

## 获得帮助

如果问题还是没解决：

1. **收集诊断信息**:
```bash
bash check_gpu.sh > diagnostic.txt 2>&1
export VLLM_LOGGING_LEVEL=DEBUG
bash vllm_startup.sh > vllm_debug.txt 2>&1
```

2. **查看日志**:
```bash
cat diagnostic.txt
cat vllm_debug.txt
```

3. **常见错误代码**:
   - `Exit code 1`: 脚本执行失败
   - `Exit code 2`: ROCm不可用
   - `RuntimeError`: vLLM初始化失败

4. **获得更多帮助**:
   - vLLM文档: https://docs.vllm.ai
   - DeepSeek Model: https://huggingface.co/deepseek-ai
   - ROCm文档: https://rocmdocs.amd.com

---

## 性能期望

修复成功后，应该看到：

```
INFO 02-05 13:22:14 [model_loader.py:...] Loading model...
INFO 02-05 13:23:45 [llm_engine.py:...] Initialized engine with...
INFO 02-05 13:25:30 [api_server.py:...] Uvicorn running on 0.0.0.0:8000

# GPU应该显示>80%利用率
rocm-smi
GPU load: 85-95%
GPU memory: 120GB/128GB
```

---

**记住**: 99%的问题都是ROCm或vLLM版本问题。按诊断流程逐步修复！ 🚀
