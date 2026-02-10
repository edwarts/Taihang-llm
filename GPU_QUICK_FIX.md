# 🚀 vLLM GPU问题 - 快速参考卡

## 错误信息
```
RuntimeError: Failed to infer device type
Triton not found: 0 active drivers
```

## 一行命令诊断
```bash
bash check_gpu.sh
```

## 3步快速修复

### 1️⃣ 安装ROCm驱动（如果缺失）
```bash
wsl
sudo apt update
sudo apt install -y rocm-dkms hip-runtime-amd
rocm-smi  # 验证GPU
```

### 2️⃣ 重装vLLM
```bash
pip uninstall -y vllm
pip install vllm[rocm]
```

### 3️⃣ 重启服务
```bash
bash vllm_startup.sh
```

## 常用检查命令

| 检查项 | 命令 | 预期 |
|--------|------|------|
| GPU驱动 | `rocm-smi` | 显示GPU列表 |
| HIP | `hipconfig --version` | 显示版本号 |
| PyTorch | `python -c "import torch; print(torch.cuda.is_available())"` | True |
| vLLM | `python -c "import vllm"` | 无错误 |

## 如果还是不行

**选项A: 用Ollama (推荐)**
```powershell
# Windows中运行
ollama serve

# 改代码
USE_VLLM = False
```

**选项B: CPU模式 (调试用)**
```bash
# 编辑 vllm_startup.sh
# 改成: --device cpu
```

## 常见原因及解决

| 症状 | 原因 | 修复 |
|------|------|------|
| `rocm-smi: command not found` | ROCm未装 | `apt install rocm-dkms` |
| `No AMD GPUs detected` | GPU无权限 | 重启WSL2 / 更新驱动 |
| `Failed to infer device` | vLLM版本不兼容 | 重装vLLM |
| `模型下载失败` | 网络/磁盘 | 检查空间/网络 |

## 防止问题再发生

✅ **定期检查**:
```bash
# 每次启动前
bash check_gpu.sh
```

✅ **保持更新**:
```bash
sudo apt upgrade rocm-dkms
pip install --upgrade vllm
```

✅ **监测GPU**:
```bash
# 另开终端
watch -n 1 rocm-smi
```

---

**记住**: 99%的问题是ROCm版本不兼容。按诊断流程修复！ 🎯
