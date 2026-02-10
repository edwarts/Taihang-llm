# ⚠️ vLLM GPU驱动问题 - 解决方案

## 错误信息

```
RuntimeError: Failed to infer device type
Triton is installed but 0 active driver(s) found (expected 1)
```

## 原因

vLLM无法识别GPU驱动。可能是：
1. ROCm驱动未安装或版本不兼容
2. AMD GPU在WSL2中无法识别
3. 环境变量未设置正确

---

## 解决方案（按顺序尝试）

### 方案 1：检查GPU状态（推荐先做）

在WSL2内运行诊断脚本：
```bash
wsl
cd /mnt/c/code-base/Taihang-llm
bash check_gpu.sh
```

输出应该显示：
```
✓ Running in WSL2
✓ rocm-smi found
✓ GPU devices found
✓ HIP found
✓ vLLM installed
```

如果有❌，按下面的方案修复。

---

### 方案 2：重新安装ROCm（最常见）

如果 `rocm-smi` 找不到：

```bash
wsl
sudo apt update
sudo apt install -y rocm-dkms hip-runtime-amd rocm-libs

# 验证
rocm-smi
```

应该输出GPU信息，类似：
```
ROCm version: 5.x.x
GPU 0: AMD Radeon (VRAM 128GB)
```

---

### 方案 3：重新安装vLLM（版本问题）

ROCm安装后，重新安装vLLM：

```bash
wsl
cd /mnt/c/code-base/Taihang-llm
source venv_vllm/bin/activate

# 完全卸载并重装
pip uninstall -y vllm
pip install --upgrade pip
pip install vllm[rocm]
```

---

### 方案 4：启用详细日志

运行vLLM时启用DEBUG日志：

```bash
source venv_vllm/bin/activate
export VLLM_LOGGING_LEVEL=DEBUG

python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-r1-distill-qwen-70b \
  --host 0.0.0.0 \
  --port 8000
```

查看详细错误信息。

---

### 方案 5：尝试CPU模式（备选）

如果GPU一直无法识别，可以临时用CPU：

```bash
# 编辑 vllm_startup.sh，改这一行：
python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-r1-distill-qwen-70b \
  --host 0.0.0.0 \
  --port 8000 \
  --device cpu  # 改为CPU
```

⚠️ CPU会慢10-100倍，仅用于调试。

---

## 完整修复步骤

如果以上都不行，按以下步骤完全重新设置：

### 1. 清理旧的虚拟环境
```bash
wsl
cd /mnt/c/code-base/Taihang-llm
rm -rf venv_vllm
```

### 2. 更新系统和安装ROCm
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y rocm-dkms hip-runtime-amd rocm-libs

# 验证ROCm
rocm-smi
```

### 3. 创建新虚拟环境
```bash
python3 -m venv venv_vllm
source venv_vllm/bin/activate
pip install --upgrade pip
```

### 4. 重新安装vLLM
```bash
pip install vllm[rocm]
```

### 5. 测试GPU检测
```bash
python -c "
import torch
import vllm
print('PyTorch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('Device count:', torch.cuda.device_count())
"
```

### 6. 启动vLLM
```bash
cd /mnt/c/code-base/Taihang-llm
bash vllm_startup.sh
```

---

## 快速诊断清单

| 检查项 | 命令 | 应该看到 |
|--------|------|---------|
| ROCm | `rocm-smi` | GPU信息 |
| HIP | `hipconfig --version` | 版本号 |
| PyTorch GPU | `python -c "import torch; print(torch.cuda.is_available())"` | True |
| vLLM | `python -c "import vllm; print('OK')"` | OK |

---

## 常见问题

### Q: rocm-smi 显示0个GPU
**A:** 
1. 检查AMD GPU驱动是否在Windows中正常（设备管理器）
2. 尝试在Windows中安装AMD GPU驱动
3. 重启WSL2：`wsl --shutdown` 然后重启

### Q: Permission denied 错误
**A:**
```bash
sudo usermod -a -G render $USER
sudo usermod -a -G video $USER
# 重新登录或运行: newgrp render
```

### Q: vLLM still says "no GPU found"
**A:**
1. 确认 `rocm-smi` 输出GPU列表
2. 检查环境变量：
```bash
echo $HSA_OVERRIDE_GFX_VERSION
echo $GPU_DEVICE_ORDINAL
```
3. 如果是自定义硬件，可能需要设置：
```bash
export HSA_OVERRIDE_GFX_VERSION=gfx90a  # 改成你的GPU型号
```

### Q: 模型下载失败
**A:**
```bash
# 检查网络和磁盘空间
df -h  # 应该有100+GB
ping huggingface.co
```

---

## 如果都不行...

1. 运行诊断：`bash check_gpu.sh`
2. 保存完整输出
3. 检查WSL2 version: `wsl --version`
4. 检查Windows GPU驱动版本
5. 考虑在Windows中尝试native vLLM（不用WSL2）

---

## 备选方案

### 使用Ollama（不需要配置）
```powershell
# Windows内，假设Ollama已安装
ollama serve
```

然后改配置：
```python
USE_VLLM = False  # 用Ollama
```

### 使用HuggingFace推理API
```python
from transformers import AutoTokenizer, TextIteratorStreamer
from threading import Thread
# 改用transformers库本地推理
```

---

## 下一步

1. ✅ 运行 `bash check_gpu.sh` 诊断
2. ✅ 按方案修复
3. ✅ 重新启动vLLM
4. ✅ 运行 `python test_inference_backends.py` 验证

祝顺利！ 🚀
