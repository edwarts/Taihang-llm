import sys
import os
import asyncio
import pandas as pd
from datetime import datetime, timedelta

# Path hack
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bridge import FinnhubTickBridge
from src.processor import DeepFeatureEngineer
from src.factory import LocalDataFactory
from src.config import TARGET_SYMBOLS

# ⚠️ 填入你的 Premium Key
PREMIUM_KEY = "YOUR_PREMIUM_KEY_HERE"

async def main():
    print("=========================================")
    print("   Finnhub Premium Real-Tick Test")
    print("=========================================")
    
    # 1. 初始化
    bridge = FinnhubTickBridge(PREMIUM_KEY)
    engineer = DeepFeatureEngineer() # 不需要 Tar 路径
    factory = LocalDataFactory(tar_path=None, model_name="deepseek-r1:70b")
    
    # 2. 选取几只代表性股票进行测试 (避免跑完30只太慢)
    test_symbols = ["NVDA", "GME", "JPM"] 
    target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 测试日期: {target_date}")
    print(f"🎯 目标股票: {test_symbols}")

    for sym in test_symbols:
        print(f"\n>>> 处理 {sym} ...")
        
        # A. 拉取真实 Tick
        raw_ticks = bridge.fetch_real_ticks(sym, target_date)
        if raw_ticks is None: continue
        
        # B. 特征工程 (这是真正的计算，不再是模拟!)
        print(f"   计算订单流与市场结构 (Ticks: {len(raw_ticks)})...")
        # 传入 API 返回的 DataFrame 直接处理
        df_features = engineer.process_dataframe(raw_ticks, timeframe='5min')
        
        if df_features.empty:
            print("   数据不足，跳过")
            continue
            
        # C. 选取一个高熵(High Entropy)或高波动时刻
        # 我们希望测试模型在混乱/剧烈波动时的表现
        high_vol_row = df_features.sort_values('vol_gk').iloc[-1]
        
        # D. 生成 Prompt
        prompt = engineer.generate_llm_description(sym, high_vol_row)
        
        # E. 发送给 Ollama
        print("   🧠 发送给 DeepSeek R1 进行推理...")
        sem = asyncio.Semaphore(1)
        # 伪造一个 label 用于测试 factory 接口 (实际生产中这里是用来生成训练数据的)
        res = await factory.generate_thought(prompt, "Unknown", 0.0, sem)
        
        if res:
            print("\n🤖 模型分析结果:")
            print("-" * 30)
            print(res['output'])
            print("-" * 30)
        
        # 可选：保存中间数据验证
        # df_features.to_csv(f"data/debug_{sym}.csv")

if __name__ == "__main__":
    if "YOUR_PREMIUM" in PREMIUM_KEY:
        print("❌ 请在脚本中填入 Finnhub Premium API Key")
    else:
        asyncio.run(main())