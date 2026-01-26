import tarfile
import pandas as pd
import pandas_ta as ta
import numpy as np
import io
from scipy.stats import entropy
from .config import TARGET_SYMBOLS # 导入白名单

class DeepFeatureEngineer:
    def __init__(self, tar_path=None):
        self.tar_path = tar_path

    def _extract_tick_data(self, member_path):
        """(原有逻辑不变，省略...)"""
        # ... 这里保留你上一版 processor.py 中 _extract_tick_data 的完整代码 ...
        # 只需要确保它接受 DataFrame 输入或者文件流
        pass 

    # --- 新增：带过滤的 Tar 遍历 ---
    def process_tar_filtered(self, callback_func):
        """
        遍历 Tar 包，但只处理 TARGET_SYMBOLS 中的股票。
        callback_func: 用于接收处理好的 dataframe 的回调函数
        """
        if not self.tar_path: return

        with tarfile.open(self.tar_path, "r") as tar:
            # 这一步在文件极大时可能会慢，可以改为 yield member
            for member in tar:
                if not member.name.endswith('.csv'): continue
                
                # Check: 文件名是否包含白名单股票 (例如 "trade/AAPL.csv")
                # 这种检查方式简单且高效
                found_symbol = None
                for sym in TARGET_SYMBOLS:
                    if f"/{sym}.csv" in member.name or f"\\{sym}.csv" in member.name:
                        found_symbol = sym
                        break
                
                if not found_symbol:
                    continue # 跳过非目标股票

                print(f"⚙️ 处理历史数据: {found_symbol}")
                raw_df = self._extract_tick_data(member.name) # 需确保你的 _extract_tick_data 适配这个调用
                
                if raw_df is not None:
                    # 复用之前的 pipeline
                    df_features = self.process_dataframe(raw_df)
                    callback_func(found_symbol, df_features)

    def process_dataframe(self, raw_df, timeframe='5min'):
        """
        [重构] 将核心处理逻辑独立出来，以便 Bridge 和 Tar 都能复用
        """
        # 这里放入上一版 process() 方法中从 resample 到 return df 的所有代码
        # 1. Resample
        agg_dict = {
            'p': 'ohlc', 'v': 'sum', 
            # 注意: 如果是 Tar 数据, side 需要先计算; 如果是 Bridge 数据, 这里要确保 logic 一致
            # 建议在传入 process_dataframe 之前，raw_df 已经有了 'p' 和 'v'
        }
        
        # --- 补全 Tick Rule 逻辑 (防止 Bridge 数据没有 side) ---
        if 'side' not in raw_df.columns:
            price_change = raw_df['p'].diff()
            raw_df['side'] = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
            raw_df['side'] = raw_df['side'].replace(0, method='ffill').fillna(0)
            raw_df['vol_buy'] = np.where(raw_df['side'] == 1, raw_df['v'], 0)
            raw_df['vol_sell'] = np.where(raw_df['side'] == -1, raw_df['v'], 0)

        df = raw_df.resample(timeframe).apply({
            'p': 'ohlc',
            'v': 'sum',
            'vol_buy': 'sum',
            'vol_sell': 'sum'
        })
        df.columns = ['open', 'high', 'low', 'close', 'volume', 'vol_buy', 'vol_sell']
        df = df.dropna()

        # 2. 调用所有内部计算方法 (复用上一版代码)
        # 需确保 processor 类里包含这些 _calc 方法
        df.ta.adx(length=14, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, append=True)
        df.ta.atr(length=14, append=True)
        
        # 假设你保留了上一版的所有 _calc_xxx 方法
        df = self._calc_volatility_metrics(df)
        df = self._calc_market_structure(df)
        df = self._calc_order_flow_metrics(df)
        df = self._calc_statistical_features(df)
        
        return df.dropna()

    # --- 必须保留这些辅助计算方法 (从上一版复制) ---
    def _calc_volatility_metrics(self, df):
        """计算高级波动率指标 (比简单的 StdDev 更准确)"""
        # 1. Garman-Klass Volatility (利用 OHLC 信息，比收盘价波动率效率高 8 倍)
        # Formula: 0.5 * ln(H/L)^2 - (2ln2 - 1) * ln(C/O)^2
        log_hl = np.log(df['high'] / df['low'])
        log_co = np.log(df['close'] / df['open'])
        df['vol_gk'] = np.sqrt(0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2)
        
        # 2. Parkinson Volatility (仅基于极差)
        df['vol_parkinson'] = np.sqrt((1 / (4 * np.log(2))) * log_hl**2)
        
        # 3. Roger-Satchell (适合有趋势时使用)
        df['vol_rs'] = np.sqrt(np.log(df['high'] / df['close']) * np.log(df['high'] / df['open']) + \
                               np.log(df['low'] / df['close']) * np.log(df['low'] / df['open']))
        
        return df

    def _calc_market_structure(self, df, window=5):
        """计算市场结构与分形几何 (SMC 概念)"""
        # 1. Swing High/Low (分形) - 注意：这里为了不偷看未来，我们使用滞后判断
        # 如果 i-2 是过去5根K线的最高点，那它就是一个 Swing High
        df['swing_high'] = df['high'].rolling(window=window).max()
        df['swing_low'] = df['low'].rolling(window=window).min()
        
        # 2. Fair Value Gap (FVG) 检测
        # 看涨 FVG: 当前K线低点 > 前2根K线高点
        df['fvg_bull'] = (df['low'] > df['high'].shift(2)).astype(int)
        # 看跌 FVG: 当前K线高点 < 前2根K线低点
        df['fvg_bear'] = (df['high'] < df['low'].shift(2)).astype(int)
        
        # 3. 支撑/阻力强度 (基于成交量加权的 Swing 点)
        # 简单逻辑：Swing High 处的成交量越大，阻力越强
        df['res_strength'] = df['volume'] * (df['high'] == df['swing_high']).astype(int)
        df['sup_strength'] = df['volume'] * (df['low'] == df['swing_low']).astype(int)
        
        return df

    def _calc_order_flow_metrics(self, df):
        """计算高级订单流与流动性指标"""
        # 1. OFI (Order Flow Imbalance) - 核心指标
        df['ofi'] = df['vol_buy'] - df['vol_sell']
        
        # 2. VPIN Proxy (知情交易概率代理)
        # VPIN = |BuyVol - SellVol| / TotalVol (简单版)
        df['vpin'] = df['ofi'].abs() / (df['volume'] + 1e-9)
        
        # 3. Amihud Illiquidity (非流动性指标)
        # 价格变动绝对值 / 成交额。值越大，撬动价格所需资金越少（流动性越差）
        df['amihud'] = df['close'].pct_change().abs() / (df['volume'] * df['close'] + 1e-9) * 1e6
        
        # 4. Kyle's Lambda (市场冲击成本)
        # Lambda = (Price Change) / (Net Order Flow)
        # 衡量每 1 单位净成交量推动了多少价格
        df['kyles_lambda'] = df['close'].diff() / (df['ofi'] + 1e-9)
        
        # 5. Effective Spread (Roll's Model 简化版)
        # 基于价格序列的自协方差估算买卖价差 (Proxy for Bid-Ask Spread)
        # 这里用 High-Low 效率比替代
        df['eff_spread_proxy'] = (df['high'] - df['low']) / df['close']
        
        return df

    def _calc_statistical_features(self, df, window=20):
        """计算统计学特征 (熵, 偏度, 峰度)"""
        # 1. Shannon Entropy (香农熵) - 衡量市场是有序(趋势)还是混沌(震荡)
        # 我们对过去 N 根 K 线的收益率分布计算熵
        def get_entropy(x):
            counts, _ = np.histogram(x, bins=10, density=True)
            return entropy(counts + 1e-9)
        
        df['entropy'] = df['close'].pct_change().rolling(window).apply(get_entropy, raw=True)
        
        # 2. Skewness (偏度) - 收益率分布是否左偏/右偏 (黑天鹅预警)
        df['skew'] = df['close'].pct_change().rolling(window).skew()
        
        # 3. Kurtosis (峰度) - 肥尾效应
        df['kurt'] = df['close'].pct_change().rolling(window).kurt()
        
        return df
    
    def generate_llm_description(self, symbol, row):
        """
        生成极其详尽的市场描述文本 (Prompt)
        DeepSeek R1 喜欢数据，给它越多越好。
        """
        # 动态判定趋势状态
        trend_str = "多头" if row['SUPERT_7_3.0'] < row['close'] else "空头"
        structure_str = "看涨FVG支撑" if row['fvg_bull'] else ("看跌FVG阻力" if row['fvg_bear'] else "无明显缺口")
        
        # 波动率分析
        vol_status = "极度压缩" if row['vol_gk'] < 0.001 else ("剧烈波动" if row['vol_gk'] > 0.005 else "正常")
        
        # 熵分析
        entropy_status = "市场混沌(震荡)" if row['entropy'] > 2.0 else "市场有序(趋势中)"
        
        return f"""
### 深度市场分析报告 ({symbol} | {row.name})

**1. 价格行为与结构 (Price Action & Structure)**
- **现价**: {row['close']:.2f} (O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f})
- **SuperTrend**: 当前处于 **{trend_str}** 区域 (支撑/阻力位: {row['SUPERT_7_3.0']:.2f})。
- **市场结构**: {structure_str}。近期 Swing High: {row['swing_high']:.2f}, Swing Low: {row['swing_low']:.2f}。
- **熵值 (Entropy)**: {row['entropy']:.2f} -> 指示 **{entropy_status}**。

**2. 高阶波动率 (Volatility)**
- **Garman-Klass Vol**: {row['vol_gk']*100:.4f}% ({vol_status})
- **ATR (14)**: {row['ATRr_14']:.2f}
- **Implied Vol Proxy (Parkinson)**: {row['vol_parkinson']*100:.4f}%

**3. 订单流与微观结构 (Order Flow & Microstructure)**
- **OFI (订单流失衡)**: {row['ofi']:.0f} (正数=主动买入强)。
- **VPIN (知情交易概率)**: {row['vpin']:.2f} (值越高，大资金异动概率越大)。
- **Kyle's Lambda (冲击成本)**: {row['kyles_lambda']:.6f} (值越大，流动性越枯竭)。
- **Amihud 非流动性**: {row['amihud']:.6f}。
- **资金流向 (CMF)**: {row['CMF_20']:.3f}。

**4. 传统技术指标 (Technicals)**
- **RSI(14)**: {row['RSI_14']:.1f}
- **MACD**: Histogram {row['MACDh_12_26_9']:.3f}
- **VWAP**: {row['VWAP_D']:.2f} (当前偏差: {(row['close']-row['VWAP_D'])/row['VWAP_D']*100:.2f}%)
"""