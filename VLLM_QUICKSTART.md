# WSL2 + vLLM 快速开始指南

## 30分钟快速部署

### 步骤1：启动WSL2（5分钟）
```powershell
# Windows PowerShell (管理员)
wsl
```

如果还没安装WSL2：
```powershell
wsl --install Ubuntu-22.04
# 然后重启
```

### 步骤2：WSL2内安装vLLM（15分钟）
```bash
# WSL2内运行
cd /mnt/c/code-base/Taihang-llm

# 创建虚拟环境
python3 -m venv venv_vllm
source venv_vllm/bin/activate

# 安装vLLM和依赖
pip install --upgrade pip
pip install vllm[rocm]  # AMD GPU支持

# 验证
python -c "import vllm; print('✓ vLLM安装成功')"
```

### 步骤3：启动vLLM服务（5分钟）

在WSL2内运行：
```bash
cd /mnt/c/code-base/Taihang-llm
source venv_vllm/bin/activate

bash vllm_startup.sh
```

**重要！记下输出的WSL2 IP地址，形如 `172.31.xxx.xxx`**

### 步骤4：更新Python代码

编辑 `src/local_data_pipeline_inference.py`，修改：
```python
# 第19行左右
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 改成你的WSL2 IP！
USE_VLLM = True
```

### 步骤5：运行推理（Windows内）

```powershell
cd C:\code-base\Taihang-llm
python src/local_data_pipeline_inference.py -s AAPL MSFT NVDA
```

---

## 性能对比

| 配置 | 单个prompt耗时 | 28k prompts总耗时 |
|------|-----------|------------|
| Windows Ollama | ~150s | 110小时 |
| **WSL2 vLLM** | **~20-40s** | **6-13小时** |

**期望性能提升：8-15倍**

---

## 故障排查

### 问题1：WSL2无法连接GPU
```bash
# WSL2内检查
rocm-smi
```
如果报错，需要重新安装ROCm驱动。

### 问题2：Python无法连接vLLM
```python
# 在Windows Python中测试
import requests
response = requests.get("http://172.31.194.125:8000/v1/models")
print(response.json())
```

### 问题3：vLLM启动超慢
第一次启动会编译CUDA/HIP kernels，可能10-15分钟。之后会快速启动。

### 问题4：显存不足
编辑 `vllm_startup.sh` 的这一行：
```bash
# 改 0.95 为 0.8 或 0.7
--gpu-memory-utilization 0.95 \
```

---

## 环境变量配置（可选）

在 `.bashrc` 中添加（WSL2内）：
```bash
export VLLM_API_KEY=""  # 如果需要
export HF_HOME="/mnt/c/code-base/models"  # Hugging Face缓存
export VLLM_GPU_MEMORY_UTILIZATION=0.95
```

---

## 监测GPU使用（实时）

另开一个WSL2终端，运行：
```bash
watch -n 1 rocm-smi
```

应该看到GPU占用率>90%。

---

## 常用命令速查表

| 任务 | 命令 |
|------|------|
| 进入WSL2 | `wsl` |
| 启动vLLM | `bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh` |
| 获取WSL2 IP | `hostname -I` |
| 测试连接 | `curl http://172.31.194.125:8000/v1/models` |
| 停止vLLM | `Ctrl+C` |
| 查看vLLM日志 | vLLM启动的终端中 |

---

## 文件位置

| 文件 | 位置 | 说明 |
|------|------|------|
| 推理代码 | `src/local_data_pipeline_inference.py` | 已添加vLLM支持 |
| 启动脚本 | `vllm_startup.sh` | WSL2内执行 |
| 部署指南 | `WSL2_VLLM_SETUP.md` | 完整文档 |

---

## 下一步

1. ✅ 检查WSL2是否已安装 (`wsl --version`)
2. ✅ 在WSL2内安装vLLM
3. ✅ 启动vLLM服务
4. ✅ 更新`VLLM_BASE_URL`为你的WSL2 IP
5. ✅ 运行 `python src/local_data_pipeline_inference.py -s AAPL`

预期首次运行会下载模型（~40GB），然后推理速度应该显著提升！
