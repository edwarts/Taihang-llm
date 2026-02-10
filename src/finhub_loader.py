# -*- coding: utf-8 -*-
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import sys

# 添加父目录到路径，以便能导入 src 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import TARGET_SYMBOLS, API_LIMIT_PER_SEC

class FinnhubPremiumLoader:
    def __init__(self, api_key, rate_limit_per_sec=30):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1/stock/candle"
        self.rate_limit_per_sec = rate_limit_per_sec
        # 根据 API 限制计算请求间隔
        self.min_delay = 1.0 / rate_limit_per_sec  # 例如: 1/30 = 0.033 秒
        self.last_request_time = 0

    def _respect_rate_limit(self):
        """尊重 API 速率限制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_chunk(self, symbol, resolution, start_timestamp, end_timestamp):
        """抓取单个时间片段的数据"""
        params = {
            'symbol': symbol,
            'resolution': resolution,
            'from': int(start_timestamp),
            'to': int(end_timestamp),
            'token': self.api_key
        }
        
        try:
            # 尊重 API 速率限制
            self._respect_rate_limit()
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('s') == 'ok':
                df = pd.DataFrame({
                    'timestamp': pd.to_datetime(data['t'], unit='s'),
                    'open': data['o'],
                    'high': data['h'],
                    'low': data['l'],
                    'close': data['c'],
                    'volume': data['v']
                })
                return df
            elif data.get('s') == 'no_data':
                return pd.DataFrame()
            else:
                print(f"Warning: API returned status {data.get('s')}")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"Request failed: {e}")
            return pd.DataFrame()

    def fetch_full_history(self, symbol, resolution, years=20):
        """
        分页循环抓取所有历史数据 (支持自动降级)
        如果无法获取指定年份的数据，会自动尝试更少的年份
        Finnhub 每次调用建议跨度不要太大，这里设定每次抓取 1 个月的数据
        
        返回: (DataFrame, 实际获取的年份数)
        """
        # 支持的年份列表 (从目标年份逐步降级)
        fallback_years = [years] + [max(1, years - i) for i in range(1, years + 1)]
        fallback_years = sorted(set(fallback_years), reverse=True)
        
        print(f"Attempting to fetch {symbol} with fallback years: {fallback_years}")
        
        for attempt_years in fallback_years:
            print(f"\n  尝试获取 {symbol} ({attempt_years} 年)...")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * attempt_years)
            
            all_dfs = []
            current_pointer = end_date
            
            # 每次回溯 30 天 (保证数据量在单次 API 限制内)
            chunk_size = timedelta(days=30)
            
            total_chunks = int((end_date - start_date).days / 30)
            processed_chunks = 0
            
            try:
                while current_pointer > start_date:
                    chunk_start = current_pointer - chunk_size
                    
                    df_chunk = self.fetch_chunk(
                        symbol, 
                        resolution, 
                        chunk_start.timestamp(), 
                        current_pointer.timestamp()
                    )
                    
                    if not df_chunk.empty:
                        all_dfs.append(df_chunk)
                    
                    # 更新指针和进度
                    current_pointer = chunk_start
                    processed_chunks += 1
                    if processed_chunks % 10 == 0:
                        print(f"    Progress: {processed_chunks}/{total_chunks} chunks downloaded...")
                
                if not all_dfs:
                    # 当前年份没有获取到数据，继续尝试下一个年份
                    print(f"  ⚠️  {symbol} ({attempt_years} 年) 无数据")
                    continue
                
                # 成功获取数据
                full_df = pd.concat(all_dfs).sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)
                print(f"  ✅ {symbol} ({attempt_years} 年) 成功获取 {len(full_df)} 条数据")
                return full_df, attempt_years
                
            except Exception as e:
                print(f"  ❌ {symbol} ({attempt_years} 年) 获取失败: {e}")
                continue
        
        # 所有年份都无法获取
        print(f"  ❌ {symbol} 无法获取任何年份的数据")
        return pd.DataFrame(), 0

        # 合并所有数据
        full_df = pd.concat(all_dfs).sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)
        
        print(f"Download Complete. Total Records: {len(full_df)}")
        return full_df

# 使用示例（你可以单独运行这个文件来下载数据并存为 CSV）
if __name__ == "__main__":
    # 强制 UTF-8 输出 (Windows 兼容性)
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # 从环境变量获取 API Key
    API_KEY = os.getenv("FINNHUB_API_KEY")
    
    if not API_KEY:
        print("[ERROR] Please set FINNHUB_API_KEY environment variable")
        print("[INFO] Setup instructions:")
        print("   Windows (PowerShell): $env:FINNHUB_API_KEY = 'your_key'")
        print("   Windows (CMD): set FINNHUB_API_KEY=your_key")
        print("   Linux/Mac: export FINNHUB_API_KEY=your_key")
        exit(1)
    
    # 初始化加载器，使用配置中的 API 限制
    loader = FinnhubPremiumLoader(API_KEY, rate_limit_per_sec=API_LIMIT_PER_SEC)
    
    # 用户配置
    resolution = "5"  # 5分钟线
    years = 15  # 获取 2 年的数据
    
    print("=" * 70)
    print("🚀 Finnhub Premium 批量数据下载器")
    print("=" * 70)
    print(f"📊 分辨率: {resolution}分钟")
    print(f"📅 数据年限: {years} 年")
    print(f"🎯 股票数量: {len(TARGET_SYMBOLS)}")
    print(f"⚡ API 限制: {API_LIMIT_PER_SEC} 请求/秒")
    print("=" * 70)
    
    # 创建输出目录
    output_dir = "data/premium_history"
    os.makedirs(output_dir, exist_ok=True)
    
    successful_downloads = []
    failed_symbols = []
    download_results = {}  # 记录每个股票的实际下载年份
    
    # 循环处理每个股票
    for idx, symbol in enumerate(TARGET_SYMBOLS, 1):
        try:
            print(f"\n[{idx}/{len(TARGET_SYMBOLS)}] 处理 {symbol}...")
            
            # 获取历史数据 (支持自动降级)
            df, actual_years = loader.fetch_full_history(symbol, resolution, years=years)
            
            if df.empty or actual_years == 0:
                print(f"❌ {symbol} 无法获取任何数据，将从列表中移除")
                failed_symbols.append(symbol)
                continue
            
            # 保存到本地
            output_file = f"{output_dir}/{symbol}_{resolution}m_{actual_years}y_history.csv"
            df.to_csv(output_file, index=False)
            print(f"✅ {symbol} 保存成功: {len(df)} 条记录 (实际年份: {actual_years}年) -> {output_file}")
            successful_downloads.append(symbol)
            download_results[symbol] = actual_years
            
        except Exception as e:
            print(f"❌ {symbol} 下载失败: {e}")
            failed_symbols.append(symbol)
            continue
    
    # 总结
    print("\n" + "=" * 70)
    print("📊 下载完成总结")
    print("=" * 70)
    print(f"✅ 成功: {len(successful_downloads)}/{len(TARGET_SYMBOLS)}")
    print(f"❌ 失败/移除: {len(failed_symbols)}/{len(TARGET_SYMBOLS)}")
    
    if successful_downloads:
        print(f"\n✅ 成功的股票 ({len(successful_downloads)}):")
        for sym in successful_downloads:
            actual_years = download_results.get(sym, years)
            print(f"   - {sym} ({actual_years}年)")
    
    if failed_symbols:
        print(f"\n❌ 需要移除的股票 ({len(failed_symbols)}):")
        for sym in failed_symbols:
            print(f"   - {sym}")
        
        # 提示更新 config.py
        print(f"\n💡 建议: 将以下股票从 TARGET_SYMBOLS 中移除:")
        print(f"   {', '.join(failed_symbols)}")
    
    print("=" * 70)
    
    # 生成清理后的 TARGET_SYMBOLS 列表
    if failed_symbols:
        cleaned_symbols = [s for s in TARGET_SYMBOLS if s not in failed_symbols]
        
        # 生成要更新的代码
        print("\n📝 更新 config.py 的新代码:")
        print("=" * 70)
        print("TARGET_SYMBOLS = [")
        
        # 按类别重新组织
        mag7_tech = [s for s in cleaned_symbols if s in ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX", "INTC"]]
        semis = [s for s in cleaned_symbols if s in ["AVGO", "QCOM", "TSM", "MU", "SMCI"]]
        financials = [s for s in cleaned_symbols if s in ["JPM", "BAC", "GS", "MS"]]
        crypto = [s for s in cleaned_symbols if s in ["COIN", "MARA", "PYPL", "SQ"]]
        meme = [s for s in cleaned_symbols if s in ["GME", "AMC", "PLTR", "HOOD", "DJT", "SOFI", "BA"]]
        
        if mag7_tech:
            print(f"    # Mag 7 / Big Tech")
            print(f"    {repr(mag7_tech)},")
        if semis:
            print(f"    # Semiconductors / AI")
            print(f"    {repr(semis)},")
        if financials:
            print(f"    # Financials")
            print(f"    {repr(financials)},")
        if crypto:
            print(f"    # Crypto / Fintech")
            print(f"    {repr(crypto)},")
        if meme:
            print(f"    # Meme / High Volatility / Others")
            print(f"    {repr(meme)},")
        
        print("]")
        print("=" * 70)