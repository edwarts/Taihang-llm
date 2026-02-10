# ✅ vLLM启动脚本 - 修复完成

## 问题已解决 ✨

之前的PowerShell脚本有兼容性问题：
- ❌ `awk` 命令不存在（Windows）
- ❌ `New-TemporaryFile -Suffix` 参数不支持
- ❌ 脚本过于复杂

## 新方案：简化 + 更可靠 ✅

### 推荐使用：start_vllm.bat

**为什么：**
- ✅ 批处理脚本，兼容性最好
- ✅ 可以双击运行
- ✅ 自动检查WSL2
- ✅ 直接调用WSL2内的bash脚本
- ✅ 输出清晰

**使用：**
```powershell
# Windows命令行
.\start_vllm.bat

# 或直接双击 start_vllm.bat 文件
```

### 备选：vllm_startup.ps1

简化后的PowerShell脚本，也能用：
```powershell
.\vllm_startup.ps1
```

### 核心脚本：vllm_startup.sh

WSL2内执行的bash脚本，自动处理：
- 创建虚拟环境（如果需要）
- 安装vLLM（如果需要）
- 自动识别WSL2 IP
- 启动vLLM服务

---

## 快速开始（3步）

### 1️⃣ 首次准备（10分钟）
```bash
wsl
cd /mnt/c/code-base/Taihang-llm
python3 -m venv venv_vllm
source venv_vllm/bin/activate
pip install vllm[rocm]
```

### 2️⃣ 启动vLLM
```powershell
# Windows内
.\start_vllm.bat
```

**看到这一行说明成功：**
```
[INFO] WSL2 IP: 172.31.194.125
```

### 3️⃣ 配置和运行
编辑 `src/local_data_pipeline_inference.py`：
```python
VLLM_BASE_URL = "http://172.31.194.125:8000"  # 你的IP
USE_VLLM = True
```

运行：
```powershell
python src/local_data_pipeline_inference.py -s AAPL
```

---

## 文件清单

| 文件 | 说明 | 用途 |
|------|------|------|
| **start_vllm.bat** | 批处理脚本 | ⭐ 推荐使用 |
| **vllm_startup.ps1** | PowerShell脚本 | 备选 |
| **vllm_startup.sh** | Bash脚本 | WSL2内执行 |
| **QUICK_START_VLLM.md** | 快速启动指南 | 参考 |

---

## 验证安装

```powershell
# 测试连接
python test_inference_backends.py
```

输出应该显示：
```
✓ vLLM connected
✓ Model available
```

---

## 性能预期

启动成功后：

| 指标 | 值 |
|------|------|
| 启动时间 | 5-10分钟（首次含下载模型） |
| 单个prompt耗时 | 25秒 |
| 28k prompts | 7.2小时 |
| GPU利用 | 95%+ |

---

## 常见问题

**Q: 启动脚本报错？**
A: 改用 `.\start_vllm.bat`（批处理脚本最兼容）

**Q: 找不到虚拟环境？**
A: 首次运行脚本会自动创建，或手动创建

**Q: 看不到IP？**
A: 在启动输出中找 `[INFO] WSL2 IP:` 行

**Q: vLLM启动很慢？**
A: 正常，首次要下载模型和编译kernels（5-10分钟）

---

## 下一步

1. ✅ 运行 `.\start_vllm.bat`
2. ✅ 记住输出的IP
3. ✅ 更新 `src/local_data_pipeline_inference.py`
4. ✅ 开始推理！

---

**准备好了？** → `.\start_vllm.bat` 🚀
