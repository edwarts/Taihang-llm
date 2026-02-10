# WSL2 + vLLM 部署指南（AMD AI Max 395+）

## 快速总结
vLLM相比Ollama可以提升性能2-5倍，通过更高效的批处理和GPU利用。

---

## 第1步：检查WSL2状态

### 1.1 检查是否已安装WSL2
```powershell
# Windows PowerShell (管理员)
wsl --version
```

如果看到版本号，说明已安装。如果未安装，运行：
```powershell
wsl --install Ubuntu-22.04
```
然后重启电脑。

### 1.2 检查GPU驱动（AMD AI Max 395+）
```bash
# WSL2内部运行
rocm-smi
```

如果命令不存在，需要安装ROCm驱动。

---

## 第2步：WSL2内安装ROCm + vLLM

### 2.1 进入WSL2
```powershell
# Windows PowerShell
wsl
```

### 2.2 安装ROCm驱动（仅第一次）
```bash
# WSL2 Ubuntu terminal
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/debian jammy main' | sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
sudo apt install -y rocm-dkms hip-runtime-amd rocm-libs

# 验证安装
rocm-smi
```

### 2.3 安装Python虚拟环境和vLLM
```bash
# WSL2内
cd /mnt/c/code-base/Taihang-llm

# 创建新的虚拟环境用于vLLM
python3 -m venv venv_vllm
source venv_vllm/bin/activate

# 安装vLLM（AMD/ROCm版本）
pip install --upgrade pip
pip install vllm[rocm]  # 自动检测ROCm

# 验证安装
python -c "import vllm; print(vllm.__version__)"
```

### 2.4 下载DeepSeek-R1模型（~40GB）
```bash
# WSL2内（虚拟环境激活状态）
# 方法A：自动下载（推荐）
# 首次运行时会自动下载，需要100+GB磁盘空间

# 方法B：预下载到指定目录
mkdir -p /mnt/c/code-base/models
export HF_HOME=/mnt/c/code-base/models

# 下载模型
python -c "
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained('deepseek-ai/deepseek-r1-distill-qwen-70b')
"
```

---

## 第3步：启动vLLM服务

### 3.1 WSL2内启动vLLM（推荐参数）
```bash
# WSL2内，虚拟环境激活状态
cd /mnt/c/code-base/Taihang-llm

python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/deepseek-r1-distill-qwen-70b \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.95 \
  --enable-prefix-caching \
  --tensor-parallel-size 1 \
  --dtype float16 \
  --seed 42
```

**参数说明：**
- `--gpu-memory-utilization 0.95`: 使用95%显存（AMD AI Max 395+ 有128GB）
- `--enable-prefix-caching`: 启用前缀缓存，加速重复推理
- `--tensor-parallel-size 1`: 单GPU（如果有多GPU改成2/4等）
- `--dtype float16`: 使用FP16减少显存占用
- `--seed 42`: 固定随机种子保证可复现性

### 3.2 WSL2 IP地址
启动后记住WSL2的IP地址（通常是 `172.x.x.x`），Windows上的Python代码需要用这个IP连接。

获取WSL2 IP：
```bash
# WSL2内
hostname -I
# 输出类似: 172.31.194.125
```

---

## 第4步：修改Windows Python代码连接vLLM

在Windows Python环境中运行推理代码，连接WSL2内的vLLM。

### 4.1 更新 `src/local_data_pipeline_inference.py`

使用新增的 vLLM OpenAI API 兼容模式：

```python
# 配置vLLM后端（替代Ollama）
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 改成你的WSL2 IP
USE_VLLM = True  # 启用vLLM
USE_OLLAMA = False  # 禁用Ollama
```

---

## 第5步：性能调优

### 5.1 监测GPU使用
```bash
# WSL2内，另开终端
watch -n 1 rocm-smi
```

### 5.2 调整并发数
vLLM内置批处理，无需手动调整 `CONCURRENT_REQUESTS`：
- Windows Python: `CONCURRENT_REQUESTS = 1-5`（vLLM自己管理队列）
- 推荐：保持 1-2，让vLLM处理批处理

### 5.3 性能基准
- **Ollama (Windows)**: ~120-150s/prompt
- **vLLM (WSL2)**: ~20-40s/prompt（~3-5倍提升）

---

## 常见问题

### Q: WSL2无法访问GPU？
A: 检查ROCm是否正确安装：
```bash
rocm-smi  # 应该显示GPU信息
```

### Q: vLLM启动超慢？
A: 首次启动会编译kernels，可能需要5-10分钟。之后会缓存。

### Q: Windows Python无法连接WSL2 vLLM？
A: 
1. 检查WSL2防火墙：`sudo ufw status` （应该是inactive）
2. 检查vLLM是否绑定 0.0.0.0:8000
3. 用正确的WSL2 IP地址（不是localhost）

### Q: 显存不足？
A: 
```bash
# 降低 --gpu-memory-utilization 到 0.8 或 0.7
# 或改用量化模型
```

---

## 部署步骤总结

| 步骤 | 位置 | 命令 |
|------|------|------|
| 1 | Windows | `wsl` 进入WSL2 |
| 2 | WSL2 | `sudo apt install rocm-dkms` 装驱动 |
| 3 | WSL2 | `pip install vllm[rocm]` 装vLLM |
| 4 | WSL2 | 运行vLLM服务器 |
| 5 | Windows | 修改Python代码连接vLLM |
| 6 | Windows | 运行推理Pipeline |

---

## 快速启动脚本

见 `vllm_startup.sh` 和 `vllm_startup.ps1`
