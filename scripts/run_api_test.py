import sys
import os
import asyncio
import pandas as pd
import json

# 路径黑魔法：确保能导入 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bridge import FinnhubBridge
from src.processor import DeepFeatureEngineer
from src.factory import LocalDataFactory

# 你的 Finnhub Key
FINNHUB_KEY = "你的_FINNHUB_API_KEY"  # ⚠️ 替换这里，或者 os.getenv("FINNHUB_KEY")

async def run_quick_test(symbol="NVDA", days=7):
    print(f"🚀 启动 Finnhub 快速测试流程 - {symbol}")
    
    # 1. 获取数据 (API)
    bridge = FinnhubBridge(FINNHUB_KEY)
    df_raw = bridge.fetch_recent_data(symbol, days=days)
    
    if df_raw is None or df_raw.empty:
        print("❌ 获取数据失败，请检查 API Key 或网络。")
        return

    print(f"✅ 获取成功: {len(df_raw)} 条 1分钟线数据")

    # 2. 特征工程 (利用 processor.py 的计算逻辑)
    print("⚙️ 正在计算高级指标 (RSI, 熵, 波动率)...")
    
    # 这里的 trick 是：我们跳过了 processor._extract_tick_data
    # 直接调用 processor._calc_... 系列私有方法，或者直接把 bridge 的输出当做 resampled 数据
    
    # 实例化 Engineer (不需要 tar path，传 None)
    engineer = DeepFeatureEngineer(tar_path=None)
    
    # 手动触发 processor.py 中的高级计算方法
    # 因为 bridge 返回的数据格式已经适配了 resampled 后的格式
    df_features = df_raw.copy()
    
    # 调用 FeatureEngineer 的内部方法链
    df_features.ta.adx(length=14, append=True)
    df_features.ta.supertrend(append=True)
    df_features.ta.macd(append=True)
    df_features.ta.rsi(length=14, append=True)
    df_features.ta.vwap(append=True)
    
    df_features = engineer._calc_volatility_metrics(df_features)
    df_features = engineer._calc_market_structure(df_features)
    df_features = engineer._calc_order_flow_metrics(df_features) # 注意：这里用的是模拟的 vol_buy/sell
    df_features = engineer._calc_statistical_features(df_features)
    
    df_features = df_features.dropna()
    print(f"✅ 特征计算完成，有效样本: {len(df_features)}")
    print(f"   包含列: {df_features.columns.tolist()[:5]} ... (共{len(df_features.columns)}列)")

    # 3. LLM 推理测试 (调用本地 Ollama)
    print("\n🧠 调用本地 DeepSeek R1 进行采样分析...")
    
    # 实例化 Factory，复用其中的 generate_thought 方法
    # 我们不需要 run 方法，直接手动调 generate
    factory = LocalDataFactory(tar_path=None, model_name="deepseek-r1:70b")
    
    # 选取最后 3 个高波动时刻进行测试
    recent_volatile = df_features.tail(50)
    target_row = recent_volatile.iloc[-1] # 取最新的一条
    
    # 构造 Prompt
    ctx = engineer.generate_llm_description(symbol, target_row)
    print("\n--- 生成的 Prompt 预览 ---")
    print(ctx)
    print("--------------------------")
    
    # 模拟一个“未来回报”用于测试 (假设未来是涨的)
    mock_ret = 0.005 
    mock_label = "BUY"
    
    # 调用 Ollama
    sem = asyncio.Semaphore(1)
    result = await factory.generate_thought(ctx, mock_label, mock_ret, sem)
    
    if result:
        print("\n🎉 测试成功！模型输出如下：")
        print("="*40)
        print(result['output'])
        print("="*40)
        
        # 保存这个测试样本
        with open("data/api_test_sample.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False))
            print("样本已保存至 data/api_test_sample.jsonl")
    else:
        print("❌ 模型调用失败，请检查 Ollama 是否运行。")

if __name__ == "__main__":
    if FINNHUB_KEY == "你的_FINNHUB_API_KEY":
        print("⚠️ 请先在代码中填入你的 Finnhub API Key！")
    else:
        asyncio.run(run_quick_test())