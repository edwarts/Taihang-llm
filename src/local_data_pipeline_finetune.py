import pandas as pd
import numpy as np
import json
import os
import asyncio
import aiohttp
from tqdm.asyncio import tqdm
from openai import AsyncOpenAI

# 引入之前的逻辑模块 (假设你已经保存了 finnhub_loader 和 feature_engineer)
# from finnhub_loader import FinnhubPremiumLoader # 如果还没跑数据，先跑这个
# from advanced_feature_engineer import AdvancedFeatureEngineer
# from timeframe_aligner import TimeframeAligner, TrainingDataMiner

# ================= 配置区域 =================
# 本地模型设置
LOCAL_MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-AWQ" # 必须与 vllm serve 的模型名一致
LOCAL_API_BASE = "http://localhost:8000/v1"
LOCAL_API_KEY = "EMPTY" # vLLM 本地运行不需要 Key

# 项目设置
DATA_FILE = "SPY_M5_History.csv" # 之前下载好的数据
OUTPUT_FILE = "local_training_data_qwen.jsonl"
CONCURRENCY = 10 # 本地并发数，根据显卡负载调整

# ================= 1. 本地推理客户端 (Async) =================
class LocalDeepSeekGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=LOCAL_API_BASE,
            api_key=LOCAL_API_KEY,
        )

    async def generate_reasoning(self, prompt, temperature=0.6):
        """
        异步调用本地 vLLM
        """
        try:
            response = await self.client.chat.completions.create(
                model=LOCAL_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a professional quantitative trader. Output strictly in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=4096, # 给 R1 足够的思考空间
                extra_body={"repetition_penalty": 1.1} # 防止模型复读
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Inference Error: {e}")
            return None

# ================= 2. 核心管道 (集成数据挖掘) =================
class LocalPipeline:
    def __init__(self):
        self.generator = LocalDeepSeekGenerator()
        
    async def process_batch(self, mined_items):
        """批量处理挖掘出的 Prompt"""
        results = []
        
        # 使用 Semaphore 控制并发，防止本地显存 OOM 或队列积压
        sem = asyncio.Semaphore(CONCURRENCY)

        async def worker(item):
            async with sem:
                # 1. 发送 Prompt 给本地 Teacher
                response = await self.generator.generate_reasoning(item['input_prompt'])
                
                if response:
                    # 2. 格式化为训练数据
                    # 注意：我们把 "Input" 中的 Hindsight Truth (未来结果) 去掉
                    # 只要把 Prompt 截断到 "### THE TRUTH" 之前即可
                    clean_input = item['input_prompt'].split("### THE TRUTH")[0].strip()
                    
                    return {
                        "instruction": "Analyze the market data and generate a trading signal with Deep Reasoning.",
                        "input": clean_input,
                        "output": response,
                        "meta_outcome": item['future_outcome'] # 保留用于分析，训练时可丢弃
                    }
                return None

        # 创建任务列表
        tasks = [worker(item) for item in mined_items]
        
        # 使用 tqdm 显示进度
        for f in tqdm.as_completed(tasks, total=len(tasks), desc="Local Inference"):
            res = await f
            if res:
                results.append(res)
                
        return results

# ================= 3. 主程序入口 =================
# 注意：你需要把之前的 TimeframeAligner 和 TrainingDataMiner 代码粘贴在同一个文件或 import 进来

# 为了代码完整性，这里简写 Main 逻辑
async def main():
    print(f"=== Starting Local AI Trading Pipeline on AMD AI Max ===")
    
    # 1. 读取本地 CSV 数据 (不再请求 API)
    if not os.path.exists(DATA_FILE):
        print(f"Data file {DATA_FILE} not found!")
        return
        
    print("Loading and Engineering Data...")
    df = pd.read_csv(DATA_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # ... 此处插入 AdvancedFeatureEngineer 处理逻辑 ...
    # df = engineer.process(df)
    
    # 2. 挖掘样本 (CPU 任务)
    print("Aligning timeframes and mining setups...")
    # ... 此处插入 TimeframeAligner 和 TrainingDataMiner 逻辑 ...
    # miner = TrainingDataMiner(aligner)
    # mined_data = miner.run_mining(threshold=0.4) 
    
    # 假设 mined_data 已经生成，格式为 list of dict
    # 为了演示，这里手动 mock 几个数据
    if 'mined_data' not in locals():
        print("Mocking mined data for test...")
        mined_data = [{"input_prompt": "Test Prompt with Hindsight... ### THE TRUTH ...", "future_outcome": 1.5}] * 5

    print(f"Found {len(mined_data)} setups. Starting Local Inference...")
    
    # 3. 启动本地推理
    pipeline = LocalPipeline()
    training_dataset = await pipeline.process_batch(mined_data)
    
    # 4. 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(training_dataset, f, indent=2)
        
    print(f"Saved {len(training_dataset)} samples to {OUTPUT_FILE}")
    print("Ready for Fine-tuning with LLaMA Factory!")

if __name__ == "__main__":
    # Windows/Linux 异步运行兼容
    asyncio.run(main())