import os
import sys
import asyncio
import pandas as pd
import json
from datetime import datetime, timedelta
import numpy as np
import pandas_market_calendars as mcal

# Path hack
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bridge import FinnhubTickBridge
from src.processor import DeepFeatureEngineer
from src.factory import LocalDataFactory
from src.config import TARGET_SYMBOLS

# 配置与环境变量
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
MODEL_NAME = "deepseek-r1:70b" # 或使用 32b/14b 视显存而定
OUTPUT_FILE = "data/training_dataset.jsonl"
CONCURRENCY_LIMIT = 2 # 限制并发请求 Ollama 的数量

async def process_symbol(symbol, target_date, bridge, engineer, factory, semaphore):
    """处理单个股票的完整流水线，支持多个 K 线分辨率"""
    print(f"🚀 开始处理 {symbol} [{target_date}]")
    
    # 定义要处理的分辨率 (1分钟、5分钟、15分钟)
    resolutions = ['1', '5', '15']
    all_results = []
    
    for resolution in resolutions:
        try:
            # 1. 拉取 Candle 数据
            candles = bridge.fetch_candles(symbol, target_date, resolution=resolution)
            if candles is None or candles.empty:
                print(f"⚠️ {symbol} (分辨率 {resolution}m) 无 K 线数据，跳过此分辨率")
                continue

            # 2. 特征工程
            df_features = engineer.process_dataframe(candles, timeframe=f'{resolution}min')
            if df_features.empty or len(df_features) < 5:
                print(f"⚠️ {symbol} (分辨率 {resolution}m) 特征计算不足，跳过此分辨率")
                continue

            # 3. 标注未来收益 (用于 Retrospective Justification)
            # 计算未来 3 根 K 线的收益率
            df_features['future_return'] = df_features['close'].shift(-3).pct_change(3).shift(-3)
            
            # 定义 Label 逻辑
            def get_label(ret):
                if ret > 0.005: return "BUY"
                if ret < -0.005: return "SELL"
                return "HOLD"
            
            df_features['label'] = df_features['future_return'].apply(get_label)
            
            # 4. 采样：选取有意义的时刻 (波动率前 10% 或 标签非 HOLD 的时刻)
            # 标准：找到标签不是 HOLD 或 波动率在前 10% 的时刻
            interesting_moments = df_features[
                (df_features['label'] != "HOLD") | 
                (df_features['vol_gk'] > df_features['vol_gk'].quantile(0.9))
            ].tail(5) # 每个分辨率每个股票采样 5 个点

            for timestamp, row in interesting_moments.iterrows():
                try:
                    # 调试信息：显示为什么选择了这个时刻
                    is_non_hold = row['label'] != "HOLD"
                    vol_threshold = df_features['vol_gk'].quantile(0.9)
                    is_high_vol = row['vol_gk'] > vol_threshold
                    
                    reason = []
                    if is_non_hold:
                        reason.append(f"标签={row['label']}")
                    if is_high_vol:
                        reason.append(f"波动率{row['vol_gk']:.4%} > {vol_threshold:.4%}(前10%)")
                    
                    # 生成 Prompt
                    prompt = engineer.generate_llm_description(symbol, row)
                    
                    # 5. 调用 LLM 生成推理过程 (Thought)
                    reason_str = " | ".join(reason) if reason else "其他条件"
                    print(f"🧠 [{symbol}:{resolution}m] 时刻: {timestamp} | 原因: {reason_str}")
                    res = await factory.generate_thought(
                        context_prompt=prompt,
                        label=row['label'],
                        future_return=row['future_return'] if not pd.isna(row['future_return']) else 0.0,
                        semaphore=semaphore
                    )
                    
                    if res:
                        # 标记该样本的分辨率
                        res['resolution'] = f"{resolution}m"
                        all_results.append(res)
                except Exception as e:
                    print(f"❌ [{symbol}:{resolution}m] 处理时刻 {timestamp} 时出错: {e}")
                    continue
        except Exception as e:
            print(f"❌ [{symbol}:{resolution}m] 处理分辨率时出错: {e}")
            continue
    
    return all_results

async def main(start_date: str = None, end_date: str = None):
    """
    升级的主函数，支持指定交易日期范围（使用真实美股交易日历）
    
    Args:
        start_date: 起始日期 (YYYY-MM-DD 格式)，默认为昨天
        end_date: 结束日期 (YYYY-MM-DD 格式)，默认为昨天
    """
    if not FINNHUB_KEY:
        print("❌ 错误: 请设置 FINNHUB_API_KEY 环境变量")
        return

    # 初始化组件
    bridge = FinnhubTickBridge(FINNHUB_KEY)
    engineer = DeepFeatureEngineer()
    factory = LocalDataFactory(model_name=MODEL_NAME)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    # 设置默认日期范围 (如果未指定)
    if end_date is None:
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if start_date is None:
        start_date = end_date  # 默认处理单个日期
    
    # 使用美股交易日历获取真实的交易日期
    try:
        nyse = mcal.get_calendar('NYSE')
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        
        # 获取指定范围内的交易日期
        trading_schedule = nyse.schedule(start_date=start_dt, end_date=end_dt)
        target_dates = [ts.strftime('%Y-%m-%d') for ts in trading_schedule.index]
        
        if not target_dates:
            print("❌ 错误: 指定范围内没有美股交易日期")
            return
            
    except Exception as e:
        print(f"❌ 获取交易日历失败: {e}")
        print("⚠️ 回退到工作日筛选")
        
        # 备用方案：工作日筛选
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        target_dates = []
        current = start
        while current <= end:
            # 仅处理工作日 (0=周一, 4=周五)
            if current.weekday() < 5:
                target_dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
    
    print("=========================================")
    print(f"📈 Taihang-LLM 数据流水线启动 (升级版 - 美股交易日)")
    print(f"📅 日期范围: {start_date} 到 {end_date}")
    print(f"📅 美股交易日数: {len(target_dates)}")
    print(f"📅 美股交易日: {', '.join(target_dates)}")
    print(f"🤖 模型: {MODEL_NAME}")
    print(f"📋 股票池: {len(TARGET_SYMBOLS)} 只")
    print("=========================================")

    os.makedirs("data", exist_ok=True)
    
    all_records = []
    
    # 遍历每个交易日期
    for target_date in target_dates:
        print(f"\n🔄 处理美股交易日: {target_date}")
        print("-" * 50)
        
        # 串行处理股票以保护 API 额度，但内部 LLM 调用是并发的
        for sym in TARGET_SYMBOLS:
            try:
                records = await process_symbol(sym, target_date, bridge, engineer, factory, semaphore)
                if records:
                    all_records.extend(records)
                    # 实时保存，防止崩溃
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        for r in records:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"❌ 处理 {sym} 时发生未知错误: {e}")
                continue

    print("\n" + "=" * 50)
    print(f"✅ 流水线运行完成!")
    print(f"📝 总计生成训练样本: {len(all_records)}")
    print(f"📁 数据已保存至: {OUTPUT_FILE}")
    print("=" * 50)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Taihang-LLM 数据流水线（支持日期范围）")
    parser.add_argument("--start-date", type=str, default=None, help="起始日期 (YYYY-MM-DD 格式)")
    parser.add_argument("--end-date", type=str, default=None, help="结束日期 (YYYY-MM-DD 格式)")
    
    args = parser.parse_args()
    
    # 如果提供了日期参数，使用它们；否则使用默认值
    asyncio.run(main(start_date=args.start_date, end_date=args.end_date))
