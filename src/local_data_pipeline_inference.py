# -*- coding: utf-8 -*-
"""
Local DeepSeek R1 Inference Pipeline using Ollama
Processes trading prompts through local LLM for reasoning-based trading analysis
"""

import json
import os
import sys
import requests
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import config
from src.config import TARGET_SYMBOLS

# ================= Configuration =================
# Backend selection: 'lm_studio' | 'vllm' | 'ollama'
INFERENCE_BACKEND = "lm_studio"  # ✅ LM Studio - complete ROCm + LLAMA.cpp support

# LM Studio settings (OpenAI API compatible, runs on Windows)
# 📊 OPTIMIZED FOR Q6 QUANTIZATION + AMD AI Max 395+
LMSTUDIO_BASE_URL = "http://localhost:1234"  # LM Studio local server
LMSTUDIO_MODEL = "local-model"  # LM Studio uses the loaded model automatically
LMSTUDIO_TIMEOUT = 600  # ⬆️ 增加到 600s (10 分钟) 用于 Q6 推理
# 💾 Recommended Model: deepseek-r1-distill-qwen-70b-q6-k (70GB, best quality/speed)
# Alternative: deepseek-r1-distill-qwen-70b-q4 (40GB, faster)
#             deepseek-r1-distill-qwen-70b (140GB, full precision)

# Ollama settings (local inference on Windows)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1:70b"
OLLAMA_TIMEOUT = 300

# vLLM settings (OpenAI API compatible, runs in WSL2)
VLLM_BASE_URL = "http://172.31.52.192:8000"  # Change to your WSL2 IP from 'hostname -I'
VLLM_MODEL = "deepseek-ai/deepseek-r1-distill-qwen-70b"
VLLM_TIMEOUT = 300

# Auto-detect backend configuration
if INFERENCE_BACKEND == "lm_studio":
    INFERENCE_BASE_URL = LMSTUDIO_BASE_URL
    INFERENCE_MODEL = LMSTUDIO_MODEL
    INFERENCE_TIMEOUT = LMSTUDIO_TIMEOUT
elif INFERENCE_BACKEND == "vllm":
    INFERENCE_BASE_URL = VLLM_BASE_URL
    INFERENCE_MODEL = VLLM_MODEL
    INFERENCE_TIMEOUT = VLLM_TIMEOUT
else:  # ollama
    INFERENCE_BASE_URL = OLLAMA_BASE_URL
    INFERENCE_MODEL = OLLAMA_MODEL
    INFERENCE_TIMEOUT = OLLAMA_TIMEOUT

# Pipeline settings
PROMPT_DIR = "data"  # Directory containing prompt files
OUTPUT_DIR = "data"  # Output directory
DEFAULT_WINDOW = "5m"  # Default timeframe
DEFAULT_YEARS = 15    # Default years of data
BATCH_SIZE = 5        # Process symbols in batches to manage memory

# 🚀 CONCURRENCY FOR Q6 + AMD AI Max 395+ (128GB shared memory)
# ⚠️ 70B Q6 模型每次推理占用大量 GPU 带宽，并发 > 1 会导致严重竞争
# LM Studio 日志实测: 并发5 时单个 prompt 处理 >6分钟，并发1 时 ~30-60秒
# 建议同时在 LM Studio 设置里把 "Parallel Requests" 也设为 1
CONCURRENT_REQUESTS = 1  # ⚡ 串行处理，GPU 全速推理单个请求

REQUEST_TIMEOUT = 600  # ⬆️ 600s (10 分钟) 避免超时

# 🎯 生成长度控制 - 保留完整思维链 (CoT) 用于 finetune 训练数据
MAX_TOKENS = 10249  # 完整思维过程，不截断

# Checkpoint settings - 断点续传，崩溃后从上次位置继续
CHECKPOINT_DIR = "data/checkpoints"

# ================= 1. Ollama Inference Client =================
class OllamaDeepSeekInferencer:
    """
    Unified inference client supporting multiple backends:
    - LM Studio: Windows native, complete ROCm + LLAMA.cpp support (RECOMMENDED)
    - vLLM: WSL2 GPU acceleration via OpenAI API
    - Ollama: Windows local inference (fallback)
    """
    
    def __init__(self, backend=None, base_url=None, model=None, timeout=300):
        self.backend = backend or INFERENCE_BACKEND
        self.base_url = base_url or INFERENCE_BASE_URL
        self.model = model or INFERENCE_MODEL
        self.timeout = timeout or INFERENCE_TIMEOUT
        self.session = requests.Session()
        
        # Configure connection pooling for better performance
        adapter = requests.adapters.HTTPAdapter(pool_connections=CONCURRENT_REQUESTS, pool_maxsize=CONCURRENT_REQUESTS)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        print(f"[INFO] Configured {self.backend.upper()} backend: {self.base_url}", flush=True)
        print(f"[INFO] Connection pool: {CONCURRENT_REQUESTS} max connections", flush=True)
        self._verify_connection()
    
    def _verify_connection(self):
        """Verify inference backend is running"""
        try:
            if self.backend == "lm_studio":
                # LM Studio uses OpenAI API
                print(f"[INFO] Verifying LM Studio connection at {self.base_url}...", flush=True)
                response = requests.get(f"{self.base_url}/v1/models", timeout=10)
                if response.status_code == 200:
                    models = response.json().get('data', [])
                    model_names = [m['id'] for m in models] if models else ["local-model"]
                    print(f"[INFO] LM Studio is running. Available models: {model_names}", flush=True)
                else:
                    print(f"[WARNING] LM Studio API returned status {response.status_code}", flush=True)
            elif self.backend == "vllm":
                # vLLM uses OpenAI API
                print(f"[INFO] Verifying vLLM connection at {self.base_url}...", flush=True)
                response = requests.get(f"{self.base_url}/v1/models", timeout=10)
                if response.status_code == 200:
                    models = response.json().get('data', [])
                    model_names = [m['id'] for m in models]
                    print(f"[INFO] vLLM is running. Available models: {model_names}", flush=True)
                else:
                    print(f"[WARNING] vLLM API returned status {response.status_code}", flush=True)
            else:  # ollama
                # Ollama API
                print(f"[INFO] Verifying Ollama connection at {self.base_url}...", flush=True)
                response = requests.get(f"{self.base_url}/api/tags", timeout=10)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    model_names = [m['name'] for m in models]
                    print(f"[INFO] Ollama is running. Available models: {model_names}", flush=True)
                else:
                    print(f"[WARNING] Ollama returned status {response.status_code}", flush=True)
                    
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Cannot connect to {self.backend.upper()} at {self.base_url}", flush=True)
            if self.backend == "lm_studio":
                print("[HINT] Make sure LM Studio is running: Start LM Studio app and load a model", flush=True)
            elif self.backend == "vllm":
                print("[HINT] Make sure vLLM is running in WSL2 and IP is correct", flush=True)
                print(f"[HINT] Check WSL2 IP: wsl command: hostname -I", flush=True)
            else:
                print("[HINT] Make sure Ollama is running: ollama serve", flush=True)
            raise RuntimeError(f"{self.backend} service not available")
    
    def generate_reasoning(self, prompt, temperature=0.7, max_retries=2):
        """
        Send prompt to inference backend using STREAMING mode.
        Streaming keeps the HTTP connection alive while tokens are generated,
        preventing timeout even for very long responses (70B models can take 10-30 min).
        """
        import time as _time
        
        for attempt in range(max_retries + 1):
            try:
                if self.backend in ["lm_studio", "vllm"]:
                    return self._stream_openai_chat(prompt, temperature)
                else:  # ollama
                    return self._stream_ollama(prompt, temperature)
                        
            except requests.exceptions.ConnectionError as e:
                print(f"[ERROR] Connection failed (attempt {attempt+1}/{max_retries+1}): {e}", flush=True)
                if attempt < max_retries:
                    _time.sleep(2 ** attempt)
                    continue
                return None
            except requests.exceptions.Timeout:
                print(f"[ERROR] Connection timeout (attempt {attempt+1}/{max_retries+1})", flush=True)
                if attempt < max_retries:
                    _time.sleep(2 ** attempt)
                    continue
                return None
            except Exception as e:
                print(f"[ERROR] Inference failed: {e}", flush=True)
                if attempt < max_retries:
                    _time.sleep(2 ** attempt)
                    continue
                return None
        return None
    
    def _stream_openai_chat(self, prompt, temperature=0.7):
        """
        Stream response from OpenAI-compatible API (LM Studio / vLLM).
        Uses Server-Sent Events (SSE) - connection stays alive as tokens arrive.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a specialized trading AI for financial analysis."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": MAX_TOKENS,
            "stream": True  # ✅ Streaming mode - no timeout!
        }
        
        # timeout=(connect_timeout, read_timeout_per_chunk)
        # read timeout only triggers if NO data arrives for this many seconds
        response = self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=(30, 300),  # 30s to connect, 300s max silence between chunks
            stream=True
        )
        
        if response.status_code != 200:
            print(f"[ERROR] {self.backend.upper()} API returned status {response.status_code}", flush=True)
            print(f"[ERROR] Response: {response.text[:200]}", flush=True)
            return None
        
        # Collect streamed tokens
        collected_content = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            # SSE format: "data: {json}" or "data: [DONE]"
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        collected_content.append(content)
                except json.JSONDecodeError:
                    continue
        
        response.close()
        
        full_response = ''.join(collected_content)
        return full_response if full_response else None
    
    def _stream_ollama(self, prompt, temperature=0.7):
        """
        Stream response from Ollama API.
        Ollama streams JSON objects, one per line.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "top_p": 0.9,
            "stream": True  # ✅ Streaming mode
        }
        
        response = self.session.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=(30, 300),
            stream=True
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Ollama API returned status {response.status_code}", flush=True)
            return None
        
        collected_content = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
                token = chunk.get('response', '')
                if token:
                    collected_content.append(token)
                if chunk.get('done', False):
                    break
            except json.JSONDecodeError:
                continue
        
        response.close()
        
        full_response = ''.join(collected_content)
        return full_response if full_response else None
    
    def close(self):
        """Close the HTTP session and release connection pool resources"""
        try:
            self.session.close()
            print("[INFO] HTTP session closed.", flush=True)
        except Exception:
            pass

# ================= 2. Year Filtering (黄金切片法) =================
def golden_section_years(all_years, n_select):
    """
    使用黄金切片法从全部年份中选择 n_select 个代表性年份。
    黄金比例间隔确保覆盖牛市、熊市、高波动、低波动等不同市场状态。
    
    Args:
        all_years: Sorted list of all available years (e.g., [2011, 2012, ..., 2025])
        n_select: Number of years to select
        
    Returns:
        Sorted list of selected years
    """
    if n_select >= len(all_years):
        return all_years
    
    if n_select <= 0:
        return []
    
    if n_select == 1:
        return [all_years[len(all_years) // 2]]
    
    # 黄金比例 φ = 1.618...
    PHI = 1.6180339887
    
    # 使用黄金比例间隔在 [0, len-1] 范围内生成 n_select 个均匀分布的索引
    # 公式: index_i = (i * φ * len / n_select) mod len, 然后取最近整数
    total = len(all_years)
    indices = set()
    
    # 始终包含首尾年份（最早和最近的市场状态）
    indices.add(0)
    indices.add(total - 1)
    
    # 用黄金比例填充中间
    for i in range(1, n_select * 3):  # oversample then pick
        idx = int((i * PHI * total / n_select) % total)
        indices.add(idx)
        if len(indices) >= n_select:
            break
    
    # 如果还不够，补充均匀间隔
    while len(indices) < n_select:
        step = total / (n_select - len(indices) + 1)
        for i in range(total):
            idx = int(i * step) % total
            indices.add(idx)
            if len(indices) >= n_select:
                break
    
    selected = sorted([all_years[i] for i in sorted(indices)[:n_select]])
    return selected


def filter_prompts_by_years(prompts, selected_years):
    """
    按年份过滤 prompts。从 custom_id (格式: SYMBOL_YYYY-MM-DD HH:MM:SS) 提取年份。
    
    Args:
        prompts: List of prompt records
        selected_years: List/set of years to keep (e.g., [2018, 2019, 2020])
        
    Returns:
        Filtered list of prompts
    """
    import re
    year_set = set(str(y) for y in selected_years)
    filtered = []
    
    for record in prompts:
        custom_id = record.get('custom_id', '')
        # Extract year from custom_id: "AAPL_2011-01-25 20:00:00" → "2011"
        match = re.search(r'_(\d{4})-', custom_id)
        if match and match.group(1) in year_set:
            filtered.append(record)
    
    return filtered


def get_available_years(prompts):
    """从 prompts 中提取所有可用年份"""
    import re
    years = set()
    for record in prompts:
        custom_id = record.get('custom_id', '')
        match = re.search(r'_(\d{4})-', custom_id)
        if match:
            years.add(int(match.group(1)))
    return sorted(years)


# ================= 3. Prompt File Loader =================
def _try_load_jsonl(filepath, mode_label=""):
    """读取 JSONL 文件，返回 records 列表或 None"""
    try:
        records = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        filename = os.path.basename(filepath)
        print(f"[SUCCESS] {mode_label} Loaded {len(records)} prompts from {filename}", flush=True)
        return records
    except Exception as e:
        print(f"[ERROR] Failed to load {filepath}: {e}", flush=True)
        return None


def load_prompt_file(symbol, window=DEFAULT_WINDOW, years=DEFAULT_YEARS,
                     prompt_dir=PROMPT_DIR, filtered=False, select_years=None):
    """
    Load prompt file with fallback strategy
    
    Filename format (按优先级查找): 
        1. 带年份标签: deepseek_r1_input_prompts_[filtered_]SYMBOL_WINDOW_YEARSy_y2020-2022.jsonl
        2. 无年份标签: deepseek_r1_input_prompts_[filtered_]SYMBOL_WINDOW_YEARSy.jsonl
        3. Fallback 少年份
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        window: Timeframe (e.g., '5m')
        years: Historical years (e.g., 15)
        prompt_dir: Directory containing prompt files
        filtered: 是否读取精简版 (filtered_) prompts
        select_years: 指定年份列表, 用于匹配文件名中的年份标签
        
    Returns:
        List of prompt records, or None if not found
    """
    tag = "filtered_" if filtered else ""
    year_tag = format_year_tag(select_years)
    mode_label = "[FILTERED]" if filtered else "[STANDARD]"
    
    # 搜索候选文件 (按优先级)
    candidates = []
    
    # 优先级 1: 精确匹配 (带年份标签)
    if year_tag:
        for try_years in range(years, 0, -1):
            candidates.append(f"deepseek_r1_input_prompts_{tag}{symbol}_{window}_{try_years}y{year_tag}.jsonl")
    
    # 优先级 2: 无年份标签 (全量文件)
    for try_years in range(years, 0, -1):
        candidates.append(f"deepseek_r1_input_prompts_{tag}{symbol}_{window}_{try_years}y.jsonl")
    
    # 逐个尝试
    for filename in candidates:
        filepath = os.path.join(prompt_dir, filename)
        if os.path.exists(filepath):
            result = _try_load_jsonl(filepath, mode_label)
            if result is not None:
                return result
    
    print(f"[ERROR] No prompt file found for {symbol} (filtered={filtered}, years={year_tag or 'all'})", flush=True)
    print(f"[HINT] Tried {len(candidates)} candidates in {prompt_dir}", flush=True)
    return None

# ================= 3. Core Inference Pipeline =================
class LocalInferencePipeline:
    """
    Pipeline for processing prompts through local DeepSeek-R1
    Features: 断点续传 (checkpoint/resume), 逐条保存, 实时进度显示
    """
    
    def __init__(self, output_dir=OUTPUT_DIR):
        self.inferencer = OllamaDeepSeekInferencer(
            base_url=INFERENCE_BASE_URL,
            model=INFERENCE_MODEL,
            timeout=INFERENCE_TIMEOUT,
            backend=INFERENCE_BACKEND
        )
        self.output_dir = output_dir
        self.checkpoint_dir = CHECKPOINT_DIR
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.inferencer.close()
    
    def _get_checkpoint_path(self, symbol, window, years, year_tag=""):
        """Get checkpoint file path for a symbol"""
        return os.path.join(self.checkpoint_dir, f"ckpt_{symbol}_{window}_{years}y{year_tag}.json")
    
    def _scan_output_file(self, output_path):
        """
        扫描已有输出文件，提取所有已完成的 custom_id。
        这是断点续传的真实数据源 — 即使 checkpoint 文件丢失也能恢复。
        """
        completed_ids = set()
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                cid = record.get('custom_id', '')
                                if cid:
                                    completed_ids.add(cid)
                            except json.JSONDecodeError:
                                continue  # skip corrupted lines
                if completed_ids:
                    print(f"[SCAN] Found {len(completed_ids)} completed results in output file", flush=True)
            except Exception as e:
                print(f"[WARNING] Failed to scan output file: {e}", flush=True)
        return completed_ids
    
    def _load_checkpoint(self, symbol, window, years, year_tag=""):
        """
        Load checkpoint - returns set of completed custom_ids.
        双重恢复: 先从 checkpoint JSON 读取，再从输出文件扫描，取并集。
        即使 checkpoint 丢失，只要输出文件在就能恢复进度。
        """
        ckpt_ids = set()
        
        # Source 1: checkpoint JSON file (快速索引)
        ckpt_path = self._get_checkpoint_path(symbol, window, years, year_tag)
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                ckpt_ids = set(data.get('completed_ids', []))
                print(f"[RESUME] Checkpoint file: {len(ckpt_ids)} IDs", flush=True)
            except Exception as e:
                print(f"[WARNING] Checkpoint JSON corrupted: {e}", flush=True)
        
        # Source 2: scan existing output JSONL file (真实数据源, 最可靠)
        output_path = self._get_output_path(symbol, window, years, year_tag)
        output_ids = self._scan_output_file(output_path)
        
        # Merge: take union of both sources
        completed_ids = ckpt_ids | output_ids
        
        # If output file recovered extra IDs not in checkpoint, re-sync checkpoint
        recovered = output_ids - ckpt_ids
        if recovered:
            print(f"[RECOVER] Recovered {len(recovered)} IDs from output file (not in checkpoint)", flush=True)
            self._save_checkpoint(symbol, window, years, completed_ids, year_tag)
        
        if completed_ids:
            print(f"[RESUME] Total: {len(completed_ids)} prompts already completed (will skip)", flush=True)
        
        return completed_ids
    
    def _save_checkpoint(self, symbol, window, years, completed_ids, year_tag=""):
        """Save checkpoint with completed custom_ids"""
        ckpt_path = self._get_checkpoint_path(symbol, window, years, year_tag)
        try:
            with open(ckpt_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'symbol': symbol,
                    'completed_ids': list(completed_ids),
                    'count': len(completed_ids),
                    'updated_at': datetime.now().isoformat()
                }, f)
        except Exception:
            pass  # Checkpoint save failure is non-fatal
    
    def _get_output_path(self, symbol, window, years, year_tag=""):
        """Get output JSONL file path"""
        output_filename = f"deepseek_r1_reasoning_{symbol}_{window}_{years}y{year_tag}.jsonl"
        return os.path.join(self.output_dir, output_filename)
    
    def _append_result(self, output_path, result):
        """Append a single result to the output JSONL file (incremental save)"""
        try:
            with open(output_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[ERROR] Failed to append result: {e}", flush=True)
    
    def process_symbol(self, symbol, prompts, window=DEFAULT_WINDOW, years=DEFAULT_YEARS,
                       limit=None, select_years=None):
        """
        Process prompts for a single symbol through DeepSeek-R1.
        逐条发送、逐条保存、支持断点续传。
        
        Args:
            symbol: Stock symbol
            prompts: List of prompt records
            window: Timeframe window
            years: Years of data
            limit: Max number of prompts to process (None = all)
            select_years: 指定年份列表, 用于匹配输出/checkpoint 文件名
            
        Returns:
            Number of successfully processed prompts
        """
        if not prompts:
            print(f"[ERROR] No prompts to process for {symbol}", flush=True)
            return 0
        
        year_tag = format_year_tag(select_years)
        
        # Load checkpoint to skip already-completed prompts
        completed_ids = self._load_checkpoint(symbol, window, years, year_tag)
        output_path = self._get_output_path(symbol, window, years, year_tag)
        
        # Parse all prompt tasks
        prompt_tasks = []
        for idx, prompt_record in enumerate(prompts, 1):
            try:
                if isinstance(prompt_record, dict):
                    if 'body' in prompt_record:
                        prompt_text = prompt_record['body']['messages'][-1]['content']
                        custom_id = prompt_record.get('custom_id', f"{symbol}_{idx}")
                    else:
                        prompt_text = prompt_record.get('input_prompt', str(prompt_record))
                        custom_id = f"{symbol}_{idx}"
                else:
                    prompt_text = str(prompt_record)
                    custom_id = f"{symbol}_{idx}"
                prompt_tasks.append((idx, prompt_text, custom_id))
            except Exception as e:
                print(f"[ERROR] Failed to parse prompt {idx}: {e}", flush=True)
                continue
        
        # Filter out already completed tasks
        remaining_tasks = [(idx, pt, cid) for idx, pt, cid in prompt_tasks if cid not in completed_ids]
        
        # Apply limit
        if limit and limit < len(remaining_tasks):
            remaining_tasks = remaining_tasks[:limit]
        
        total_done = len(completed_ids)
        total_all = len(prompt_tasks)
        
        if not remaining_tasks:
            print(f"[INFO] {symbol}: All {total_all} prompts already completed (from checkpoint + output scan)", flush=True)
            return total_done
        
        print(f"\n[INFO] {symbol}: {len(remaining_tasks)} remaining / {total_all} total ({total_done} already done)", flush=True)
        
        # NOTE: 永远不清空已有输出文件! 始终用 append 模式写入。
        # 已完成的 prompt 通过 completed_ids 跳过，不会重复写入。
        
        # Process prompts one at a time (sequential for max GPU speed)
        success_count = 0
        fail_count = 0
        import time as _time
        
        pbar = tqdm(remaining_tasks, desc=f"Inferencing {symbol}", unit="prompt",
                     initial=0, total=len(remaining_tasks))
        
        for idx, prompt_text, custom_id in pbar:
            try:
                t0 = _time.time()
                reasoning_output = self.inferencer.generate_reasoning(prompt_text)
                elapsed = _time.time() - t0
                
                if reasoning_output:
                    result = {
                        "symbol": symbol,
                        "custom_id": custom_id,
                        "prompt": prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text,
                        "reasoning": reasoning_output,
                        "window": window,
                        "years": years
                    }
                    # Append immediately to output file (crash-safe)
                    self._append_result(output_path, result)
                    
                    # Update checkpoint
                    completed_ids.add(custom_id)
                    self._save_checkpoint(symbol, window, years, completed_ids, year_tag)
                    
                    success_count += 1
                    pbar.set_postfix(ok=success_count, fail=fail_count, 
                                     last=f"{elapsed:.0f}s", refresh=True)
                else:
                    fail_count += 1
                    pbar.set_postfix(ok=success_count, fail=fail_count, refresh=True)
                    
            except KeyboardInterrupt:
                print(f"\n[INTERRUPTED] Saving progress... ({success_count} done, checkpoint saved)", flush=True)
                self._save_checkpoint(symbol, window, years, completed_ids, year_tag)
                raise
            except Exception as e:
                fail_count += 1
                print(f"\n[ERROR] Prompt {idx} ({custom_id}) failed: {e}", flush=True)
                continue
        
        pbar.close()
        total_done = len(completed_ids)
        print(f"[RESULT] {symbol}: {success_count} new + {total_done - success_count} resumed = {total_done}/{total_all} total", flush=True)
        return total_done

# ================= Helper: Parse year arguments =================
def parse_year_args(year_args):
    """
    解析年份参数，支持单个年份和范围格式
    
    Examples:
        ['2018', '2019', '2020']  -> [2018, 2019, 2020]
        ['2018-2022']             -> [2018, 2019, 2020, 2021, 2022]
        ['2018-2020', '2023']     -> [2018, 2019, 2020, 2023]
    """
    years = set()
    for arg in year_args:
        if '-' in arg and not arg.startswith('-'):
            # Range format: "2018-2022"
            parts = arg.split('-')
            if len(parts) == 2:
                try:
                    start, end = int(parts[0]), int(parts[1])
                    years.update(range(start, end + 1))
                except ValueError:
                    print(f"[WARNING] Invalid year range: {arg}, skipping", flush=True)
        else:
            try:
                years.add(int(arg))
            except ValueError:
                print(f"[WARNING] Invalid year: {arg}, skipping", flush=True)
    return sorted(years)


def format_year_tag(year_list):
    """
    将年份列表转为文件名标签，每个年份显式列出
    
    Examples:
        [2020, 2021, 2022]              -> '_y2020_2021_2022'
        [2008, 2017, 2020, 2021, 2022]  -> '_y2008_2017_2020_2021_2022'
        [2021]                          -> '_y2021'
        None 或 []                      -> ''  (不加标签)
    """
    if not year_list:
        return ""
    years = sorted(year_list)
    return "_y" + "_".join(str(y) for y in years)


# ================= 4. Main Pipeline Orchestrator =================
def main(symbols=None, window=DEFAULT_WINDOW, years=DEFAULT_YEARS, prompt_dir=PROMPT_DIR,
         limit=None, years_select=None, golden_slice=None, filtered=False):
    """
    Main pipeline orchestrator with checkpoint/resume + year filtering support
    
    Args:
        symbols: List of symbols to process, or None to process all from config
        window: Timeframe window (default: 5m)
        years: Historical years (default: 15)
        prompt_dir: Directory containing prompt files
        limit: Max prompts per symbol (None = all)
        years_select: Explicit list of years to process (e.g., [2018, 2019, 2020])
        golden_slice: Auto-select N years using golden section method
        filtered: 是否读取精简版 (波动率+RSI过滤后) prompts
    """
    
    # 如果 filtered 模式且 prompt_dir 仍是默认值，自动切换到 data/filtered_q/
    if filtered and prompt_dir == PROMPT_DIR:
        prompt_dir = os.path.join("data", "filtered_q")
        print(f"[INFO] Filtered mode: auto-switched prompt_dir to {prompt_dir}", flush=True)
    
    # Determine symbols to process
    symbols_to_process = symbols if symbols else TARGET_SYMBOLS
    
    data_mode = "FILTERED (high-volatility + RSI extreme)" if filtered else "STANDARD (all prompts)"
    print("=" * 70, flush=True)
    print("[START] Local DeepSeek-R1 Inference Pipeline", flush=True)
    print("=" * 70, flush=True)
    print(f"[CONFIG] Data mode: {data_mode}", flush=True)
    print(f"[CONFIG] Backend: {INFERENCE_BACKEND}", flush=True)
    print(f"[CONFIG] API URL: {INFERENCE_BASE_URL}", flush=True)
    print(f"[CONFIG] Model timeout: {INFERENCE_TIMEOUT}s", flush=True)
    print(f"[CONFIG] Max tokens: {MAX_TOKENS}", flush=True)
    print(f"[CONFIG] Symbols: {len(symbols_to_process)}", flush=True)
    print(f"[CONFIG] Window: {window}", flush=True)
    print(f"[CONFIG] Years: {years}", flush=True)
    print(f"[CONFIG] Prompt dir: {prompt_dir}", flush=True)
    if years_select:
        print(f"[CONFIG] Year filter: {years_select}", flush=True)
    if golden_slice:
        print(f"[CONFIG] Golden slice: auto-select {golden_slice} years", flush=True)
    if limit:
        print(f"[CONFIG] Limit: {limit} prompts per symbol", flush=True)
    print(f"[CONFIG] Checkpoint dir: {CHECKPOINT_DIR}", flush=True)
    print(f"[CONFIG] Mode: Sequential (1 request at a time for max GPU speed)", flush=True)
    print("=" * 70, flush=True)
    
    with LocalInferencePipeline(output_dir=OUTPUT_DIR) as pipeline:
        successful = []
        failed = []
        
        for sym_idx, symbol in enumerate(symbols_to_process, 1):
            try:
                print(f"\n[{sym_idx}/{len(symbols_to_process)}] Processing {symbol}...", flush=True)
                
                # Load prompts
                prompts = load_prompt_file(symbol, window, years, prompt_dir,
                                          filtered=filtered, select_years=years_select)
                if not prompts:
                    failed.append(symbol)
                    continue
                
                # Apply year filtering
                if years_select or golden_slice:
                    available_years = get_available_years(prompts)
                    
                    if golden_slice:
                        # 黄金切片法自动选择 N 个代表性年份
                        selected = golden_section_years(available_years, golden_slice)
                        print(f"[GOLDEN] Available years: {available_years}", flush=True)
                        print(f"[GOLDEN] Selected {len(selected)} years: {selected}", flush=True)
                    else:
                        selected = [y for y in years_select if y in available_years]
                        missing = [y for y in years_select if y not in available_years]
                        if missing:
                            print(f"[WARNING] Years not found in data: {missing}", flush=True)
                        print(f"[FILTER] Selected years: {selected}", flush=True)
                    
                    original_count = len(prompts)
                    prompts = filter_prompts_by_years(prompts, selected)
                    print(f"[FILTER] {symbol}: {len(prompts)}/{original_count} prompts after year filter", flush=True)
                
                if not prompts:
                    print(f"[WARNING] No prompts remaining after filter for {symbol}", flush=True)
                    failed.append(symbol)
                    continue
                
                # Run inference (with checkpoint/resume)
                done_count = pipeline.process_symbol(symbol, prompts, window, years,
                                                    limit=limit, select_years=years_select)
                
                if done_count > 0:
                    successful.append((symbol, done_count))
                else:
                    failed.append(symbol)
                    
            except KeyboardInterrupt:
                print(f"\n[INTERRUPTED] Pipeline stopped by user. Progress saved to checkpoints.", flush=True)
                print(f"[HINT] Re-run the same command to resume from where you left off.", flush=True)
                break
            except Exception as e:
                print(f"[ERROR] {symbol} processing failed: {e}", flush=True)
                import traceback
                traceback.print_exc()
                failed.append(symbol)
                continue
        
        # Summary report
        print("\n" + "=" * 70, flush=True)
        print("[SUMMARY] DeepSeek-R1 Inference Report", flush=True)
        print("=" * 70, flush=True)
        print(f"[RESULT] Successful: {len(successful)}/{len(symbols_to_process)}", flush=True)
        print(f"[RESULT] Failed: {len(failed)}/{len(symbols_to_process)}", flush=True)
        
        if successful:
            print(f"\n[SUCCESS] Processed symbols:", flush=True)
            for symbol, count in successful:
                print(f"  - {symbol}: {count} reasoning outputs", flush=True)
        
        if failed:
            print(f"\n[FAILED] Failed symbols: {', '.join(failed)}", flush=True)
        
        print("=" * 70, flush=True)
        print("[COMPLETE] Inference pipeline finished!", flush=True)
        print(f"[OUTPUT] Results saved to: {OUTPUT_DIR}/", flush=True)
        print(f"[HINT] Checkpoints saved to: {CHECKPOINT_DIR}/", flush=True)
        print(f"[HINT] Re-run same command to resume incomplete symbols.", flush=True)

# ================= 5. Command-line Interface =================
if __name__ == "__main__":
    import argparse
    
    # Force UTF-8 output for Windows compatibility (safe method)
    # NOTE: 不要使用 io.TextIOWrapper 包装 sys.stdout，会导致缓冲死锁
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        # Fallback: set environment variable for child processes
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    parser = argparse.ArgumentParser(
        description="Local DeepSeek-R1 Inference Pipeline (supports checkpoint/resume + year filtering)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 测试: 只处理 AAPL 的前 3 个 prompt
  python src/local_data_pipeline_inference.py -s AAPL --limit 3
  
  # 处理指定年份 (2020-2024)
  python src/local_data_pipeline_inference.py -s AAPL --years-select 2020 2021 2022 2023 2024
  
  # 黄金切片法: 自动从15年中选5个代表性年份
  python src/local_data_pipeline_inference.py -s AAPL --golden-slice 5
  
  # 处理单个 symbol (全部 prompts, 支持断点续传)
  python src/local_data_pipeline_inference.py -s AAPL
  
  # 崩溃后恢复: 直接重新运行相同命令，会自动跳过已完成的
  python src/local_data_pipeline_inference.py -s AAPL
  
  # 黄金切片 5 年 + 所有 symbols
  python src/local_data_pipeline_inference.py --golden-slice 5
  
  # === 指定年份 ===
  # 连续年份 + 全部 symbols → 读取 _y2020-2024 文件
  python src/local_data_pipeline_inference.py --run-years 2020-2024
  
  # 非连续年份 + 全部 symbols → 读取 _y2008_2017_2021-2022 文件
  python src/local_data_pipeline_inference.py --run-years 2008 2017 2021 2022
  
  # 单个 symbol + 非连续年份
  python src/local_data_pipeline_inference.py -s AAPL --run-years 2008 2017 2021 2022
  
  # 混合范围 → 读取 _y2018-2020_2023-2024 文件
  python src/local_data_pipeline_inference.py --run-years 2018-2020 2023 2024
  
  # 指定年份 + 精简版数据
  python src/local_data_pipeline_inference.py --run-years 2020-2024 --filtered
  
  # === 精简版数据 (波动率+RSI过滤后, 数据量大幅减少) ===
  # 读取 data/filtered_q/ 下的精简版 prompts
  python src/local_data_pipeline_inference.py -s AAPL --filtered
  
  # 精简版 + 黄金切片 + 所有 symbols
  python src/local_data_pipeline_inference.py --filtered --golden-slice 5
        """
    )
    
    parser.add_argument(
        '-s', '--symbols',
        nargs='+',
        default=None,
        help='Symbols to process (space-separated). Default: all from config.py'
    )
    
    parser.add_argument(
        '-w', '--window',
        type=str,
        default=DEFAULT_WINDOW,
        choices=['1m', '5m', '15m', '30m', '60m', 'D'],
        help=f'Timeframe window (default: {DEFAULT_WINDOW})'
    )
    
    parser.add_argument(
        '-y', '--years',
        type=int,
        default=DEFAULT_YEARS,
        help=f'Historical data years (default: {DEFAULT_YEARS})'
    )
    
    parser.add_argument(
        '-n', '--limit',
        type=int,
        default=None,
        help='Max number of prompts to process per symbol (default: all)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=MAX_TOKENS,
        help=f'Max tokens to generate per response (default: {MAX_TOKENS}). Lower = faster.'
    )
    
    parser.add_argument(
        '-c', '--concurrency',
        type=int,
        default=CONCURRENT_REQUESTS,
        help=f'Concurrent requests (default: {CONCURRENT_REQUESTS}). Use >1 with small models.'
    )
    
    parser.add_argument(
        '--years-select',
        nargs='+',
        type=int,
        default=None,
        help='Specific years to process (e.g., --years-select 2020 2021 2022 2023 2024)'
    )
    
    parser.add_argument(
        '--golden-slice',
        type=int,
        default=None,
        help='Auto-select N representative years using golden section method (e.g., --golden-slice 5)'
    )
    
    parser.add_argument(
        '--run-years',
        nargs='+',
        type=str,
        default=None,
        help='指定年份运行全部 config.py symbols (支持范围: --run-years 2020-2024 或 2018 2020 2023)'
    )
    
    parser.add_argument(
        '--prompt-dir',
        type=str,
        default=PROMPT_DIR,
        help=f'Directory containing prompt files (default: {PROMPT_DIR})'
    )
    
    parser.add_argument(
        '--filtered',
        action='store_true',
        default=False,
        help='读取精简版 prompts (波动率+RSI过滤后), 自动从 data/filtered_q/ 加载'
    )
    
    parser.add_argument(
        '--ollama-url',
        type=str,
        default=OLLAMA_BASE_URL,
        help=f'Ollama service URL (default: {OLLAMA_BASE_URL})'
    )
    
    args = parser.parse_args()
    
    # Apply runtime overrides
    if args.max_tokens != MAX_TOKENS:
        import src.local_data_pipeline_inference as _self
        _self.MAX_TOKENS = args.max_tokens
    if args.concurrency != CONCURRENT_REQUESTS:
        import src.local_data_pipeline_inference as _self
        _self.CONCURRENT_REQUESTS = args.concurrency
    
    # --run-years: 解析年份, 可配合 -s 指定 symbol 或省略 -s 跑全部
    run_symbols = args.symbols
    run_years_select = args.years_select
    
    if args.run_years:
        parsed_years = parse_year_args(args.run_years)
        if not parsed_years:
            print("[ERROR] --run-years 未解析到有效年份, 请检查格式 (如: 2020-2024 或 2008 2017 2021 2022)")
            sys.exit(1)
        
        run_years_select = parsed_years
        
        if args.symbols:
            # 指定 symbol(s) + 指定年份
            run_symbols = args.symbols
            print(f"[RUN-YEARS] Symbols: {run_symbols}", flush=True)
        else:
            # 未指定 symbol → 全部 symbols
            run_symbols = None
            print(f"[RUN-YEARS] 处理全部 {len(TARGET_SYMBOLS)} 个 symbols: {', '.join(TARGET_SYMBOLS)}", flush=True)
        
        print(f"[RUN-YEARS] 指定年份: {parsed_years}", flush=True)
        print(f"[RUN-YEARS] 文件标签: {format_year_tag(parsed_years)}", flush=True)
    
    try:
        main(
            symbols=run_symbols,
            window=args.window,
            years=args.years,
            prompt_dir=args.prompt_dir,
            limit=args.limit,
            years_select=run_years_select,
            golden_slice=args.golden_slice,
            filtered=args.filtered
        )
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Pipeline stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
