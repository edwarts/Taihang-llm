# 🚀 vLLM 启动（修复版本）

## 最简单的启动方式

### Windows 用户 - 双击启动！
```powershell
双击: .\start_vllm.bat
```

或命令行：
```powershell
.\start_vllm.bat
```

### WSL2 / Linux 用户
```bash
bash /mnt/c/code-base/Taihang-llm/vllm_startup.sh
```

---

## 启动步骤

### 1️⃣ 准备虚拟环境（仅第一次）
```bash
wsl
cd /mnt/c/code-base/Taihang-llm
python3 -m venv venv_vllm
source venv_vllm/bin/activate
pip install vllm[rocm]
```

### 2️⃣ 启动vLLM
**Windows:**
```powershell
.\start_vllm.bat
```

**WSL2/Linux:**
```bash
source venv_vllm/bin/activate
bash vllm_startup.sh
```

### 3️⃣ 记住输出的IP地址
看这一行：
```
[INFO] WSL2 IP: 172.31.194.125
```

### 4️⃣ 配置Python代码
编辑 `src/local_data_pipeline_inference.py` 第19行：
```python
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 改成你的IP！
USE_VLLM = True
```

### 5️⃣ 运行推理
```powershell
python src/local_data_pipeline_inference.py -s AAPL
```

---

## 启动脚本说明

### start_vllm.bat（推荐）✅
- ✓ Windows批处理脚本
- ✓ 兼容性最好
- ✓ 双击即可运行
- ✓ 自动检查WSL2

### vllm_startup.ps1
- PowerShell版本
- 直接调用bash脚本
- 用法: `.\vllm_startup.ps1`

### vllm_startup.sh
- WSL2内执行的bash脚本
- 自动创建虚拟环境（如果需要）
- 自动安装vLLM（如果需要）
- 自动显示WSL2 IP

---

## 故障排查

### 问题：WSL2找不到
```
[ERROR] WSL2 not found!
```
解决：
```powershell
wsl --install Ubuntu-22.04
# 然后重启电脑
```

### 问题：虚拟环境不存在
脚本会自动创建，如果失败手动创建：
```bash
wsl
cd /mnt/c/code-base/Taihang-llm
python3 -m venv venv_vllm
source venv_vllm/bin/activate
pip install vllm[rocm]
```

### 问题：vLLM启动很慢
第一次会下载模型（~40GB）和编译kernels（5-10分钟），这是正常的。

### 问题：看不到IP地址
检查启动脚本输出，找这一行：
```
[INFO] WSL2 IP: xxx.xxx.xxx.xxx
```

如果没有，手动获取：
```bash
# WSL2终端内
hostname -I
```

---

## 快速检查清单

启动后，检查这些：

```
✓ 看到 "[START] Launching vLLM..."
✓ 看到 "WSL2 IP: 172.31.xxx.xxx"
✓ 看到 "vLLM API: http://172.31.xxx.xxx:8000"
✓ vLLM没有报错信息
```

---

## 监测GPU使用（可选）

另开一个WSL2终端：
```bash
watch -n 1 rocm-smi
```

应该看到GPU占用显著上升。

---

## 下一步

1. 启动vLLM：`.\start_vllm.bat`
2. 记住IP地址
3. 更新 `src/local_data_pipeline_inference.py`
4. 运行推理：`python src/local_data_pipeline_inference.py -s AAPL`

---

## 常用命令速查

| 任务 | 命令 |
|------|------|
| 启动vLLM | `.\start_vllm.bat` |
| 进入WSL2 | `wsl` |
| 创建虚拟环境 | `python3 -m venv venv_vllm` |
| 激活虚拟环境 | `source venv_vllm/bin/activate` |
| 获取IP | `hostname -I` (WSL2内) |
| 测试连接 | `python test_inference_backends.py` |
| 查看GPU | `rocm-smi` |

---

有问题？→ 运行 `python test_inference_backends.py` 诊断
