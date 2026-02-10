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
        """流式解压并清洗 Tick 数据"""
        with tarfile.open(self.tar_path, "r") as tar:
            f = tar.extractfile(member_path)
            if f is None: return None
            
            # 读取 Finnhub 格式 CSV
            df = pd.read_csv(io.BytesIO(f.read()))
            df['datetime'] = pd.to_datetime(df['t'], unit='ms')
            df.set_index('datetime', inplace=True)
            
            # --- 微观结构核心算法 ---
            # 1. Tick Rule (Lee-Ready 简化版): 推断主动买/卖方向
            # diff > 0 -> Buy(+1), diff < 0 -> Sell(-1), diff = 0 -> 延续上笔
            price_change = df['p'].diff()
            df['side'] = np.where(price_change > 0, 1, np.where(price_change < 0, -1, np.nan))
            df['side'] = df['side'].ffill().fillna(0) # 0 表示无法判断的初始状态
            
            # 2. 拆分买卖量
            df['vol_buy'] = np.where(df['side'] == 1, df['v'], 0)
            df['vol_sell'] = np.where(df['side'] == -1, df['v'], 0)
            
            # 3. Dollar Value (成交金额)
            df['dollar_val'] = df['p'] * df['v']
            
            return df


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
        Process candle data (from Bridge or Tar) into feature-rich dataframe.
        raw_df should have columns: ['open', 'high', 'low', 'close', 'volume', 'vol_buy', 'vol_sell']
        """
        if raw_df.empty or len(raw_df) < 30:
            return pd.DataFrame()  # Need minimum data for indicators
        
        df = raw_df.copy()
        
        # Ensure we have vol_buy and vol_sell columns
        if 'vol_buy' not in df.columns or 'vol_sell' not in df.columns:
            price_change = df['close'].diff()
            df['side'] = np.where(price_change > 0, 1, np.where(price_change < 0, -1, 0))
            df['side'] = df['side'].replace(0, method='ffill').fillna(0)
            df['vol_buy'] = np.where(df['side'] == 1, df['volume'], 0)
            df['vol_sell'] = np.where(df['side'] == -1, df['volume'], 0)

        # Apply technical indicators using pandas_ta with error handling
        try:
            df.ta.rsi(length=14, append=True)
            df.ta.atr(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.supertrend(length=7, multiplier=3.0, append=True)
            df.ta.vwap(append=True)
            df.ta.cmf(length=20, append=True)
        except Exception as e:
            print(f"Warning: Error calculating technical indicators: {e}")
            return pd.DataFrame()

        # Validate that required columns exist (add defaults if missing)
        required_macd_cols = ['MACDh_12_26_9']
        required_cols = ['RSI_14', 'ATRr_14', 'SUPERT_7_3.0', 'VWAP_D', 'CMF_20']
        
        for col in required_macd_cols + required_cols:
            if col not in df.columns:
                print(f"Warning: Missing column {col}, adding default values")
                df[col] = 0.0

        # Calculate advanced metrics
        try:
            df = self._calc_volatility_metrics_safe(df)
            df = self._calc_market_structure(df, window=5)
            df = self._calc_order_flow_metrics(df)
            df = self._calc_statistical_features(df, window=5)  # Reduced window to 5
        except Exception as e:
            print(f"Warning: Error calculating advanced metrics: {e}")
            return pd.DataFrame()
        
        # Drop rows with NaN values more intelligently
        # First, try dropping complete NaN rows
        df_clean = df.dropna()
        
        if len(df_clean) == 0:
            # If that doesn't work, drop rows where more than 30% of columns are NaN
            df_clean = df.dropna(thresh=len(df.columns) * 0.7)
        
        if len(df_clean) == 0:
            # Last resort: drop rows where more than 50% of columns are NaN
            df_clean = df.dropna(thresh=len(df.columns) * 0.5)
        
        return df_clean

    def _calc_volatility_metrics_safe(self, df):
        """Calculate volatility metrics with proper error handling for edge cases"""
        try:
            # Avoid log(0) or log(negative) by adding small epsilon and clamping
            high_low_ratio = (df['high'] / (df['low'] + 1e-9)).clip(lower=1.0001)  # Ensure ratio > 1
            open_close_ratio = (df['close'] / (df['open'] + 1e-9)).clip(lower=0.0001, upper=10000)  # Clamp ratio
            
            # 1. Garman-Klass Volatility (with safety checks)
            log_hl = np.log(high_low_ratio)
            log_co = np.log(open_close_ratio)
            df['vol_gk'] = np.sqrt(np.abs(0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2)).fillna(0)
            
            # 2. Parkinson Volatility (simpler, based on high-low range)
            df['vol_parkinson'] = np.sqrt(np.abs((1 / (4 * np.log(2))) * log_hl**2)).fillna(0)
            
            # 3. Simple volatility based on price range
            df['vol_range'] = (df['high'] - df['low']) / df['close']
            
        except Exception as e:
            print(f"Warning: Error in volatility calculation: {e}")
            df['vol_gk'] = 0
            df['vol_parkinson'] = 0
            df['vol_range'] = 0
        
        return df

    def _calc_volatility_metrics(self, df):
        """Alias for _calc_volatility_metrics_safe for backward compatibility"""
        return self._calc_volatility_metrics_safe(df)

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

    def _calc_statistical_features(self, df, window=5):
        """计算统计学特征 (熵, 偏度, 峰度) with smaller windows"""
        try:
            # 1. Simple return-based metrics (more stable than complex entropy)
            returns = df['close'].pct_change()
            
            # Shannon Entropy with robust calculation
            def safe_entropy(x):
                # Filter out NaN and inf values
                x_clean = x[np.isfinite(x)]
                if len(x_clean) < 2:
                    return 0
                counts, _ = np.histogram(x_clean, bins=5, density=True)
                counts = counts + 1e-9
                return float(entropy(counts)) if not np.isnan(entropy(counts)) else 0
            
            df['entropy'] = returns.rolling(window).apply(safe_entropy, raw=False).fillna(0)
            
            # 2. Skewness with NaN handling
            df['skew'] = returns.rolling(window).skew().fillna(0)
            
            # 3. Kurtosis with NaN handling
            df['kurt'] = returns.rolling(window).kurt().fillna(0)
            
        except Exception as e:
            print(f"Warning: Error in statistical features: {e}")
            df['entropy'] = 0
            df['skew'] = 0
            df['kurt'] = 0
        
        return df
    
    def generate_llm_description(self, symbol, row):
        """
        生成极其详尽的市场描述文本 (Prompt)
        DeepSeek R1 喜欢数据，给它越多越好。
        添加了安全的列访问和异常处理
        """
        try:
            # 动态判定趋势状态 - 安全访问列
            supertrend_val = row.get('SUPERT_7_3.0', row['close'])
            trend_str = "多头" if supertrend_val < row['close'] else "空头"
            structure_str = "看涨FVG支撑" if row.get('fvg_bull', 0) else ("看跌FVG阻力" if row.get('fvg_bear', 0) else "无明显缺口")
            
            # 波动率分析
            vol_gk = row.get('vol_gk', 0)
            vol_status = "极度压缩" if vol_gk < 0.001 else ("剧烈波动" if vol_gk > 0.005 else "正常")
            
            # 熵分析
            entropy_val = row.get('entropy', 1.0)
            entropy_status = "市场混沌(震荡)" if entropy_val > 2.0 else "市场有序(趋势中)"
            
            # 安全获取所有字段，使用get方法避免KeyError
            close_price = row['close']
            open_price = row.get('open', close_price)
            high_price = row.get('high', close_price)
            low_price = row.get('low', close_price)
            atr = row.get('ATRr_14', 0.0)
            vol_parkinson = row.get('vol_parkinson', 0.0)
            ofi = row.get('ofi', 0.0)
            vpin = row.get('vpin', 0.0)
            kyles_lambda = row.get('kyles_lambda', 0.0)
            amihud = row.get('amihud', 0.0)
            cmf = row.get('CMF_20', 0.0)
            rsi = row.get('RSI_14', 50.0)
            macd_h = row.get('MACDh_12_26_9', 0.0)
            vwap = row.get('VWAP_D', close_price)
            swing_high = row.get('swing_high', high_price)
            swing_low = row.get('swing_low', low_price)
            
            # 计算VWAP偏差
            vwap_dev = (close_price - vwap) / vwap * 100 if vwap != 0 else 0
            
            return f"""
### 深度市场分析报告 ({symbol} | {row.name})

**1. 价格行为与结构 (Price Action & Structure)**
- **现价**: {close_price:.2f} (O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f})
- **SuperTrend**: 当前处于 **{trend_str}** 区域 (支撑/阻力位: {supertrend_val:.2f})。
- **市场结构**: {structure_str}。近期 Swing High: {swing_high:.2f}, Swing Low: {swing_low:.2f}。
- **熵值 (Entropy)**: {entropy_val:.2f} -> 指示 **{entropy_status}**。

**2. 高阶波动率 (Volatility)**
- **Garman-Klass Vol**: {vol_gk*100:.4f}% ({vol_status})
- **ATR (14)**: {atr:.2f}
- **Implied Vol Proxy (Parkinson)**: {vol_parkinson*100:.4f}%

**3. 订单流与微观结构 (Order Flow & Microstructure)**
- **OFI (订单流失衡)**: {ofi:.0f} (正数=主动买入强)。
- **VPIN (知情交易概率)**: {vpin:.2f} (值越高，大资金异动概率越大)。
- **Kyle's Lambda (冲击成本)**: {kyles_lambda:.6f} (值越大，流动性越枯竭)。
- **Amihud 非流动性**: {amihud:.6f}。
- **资金流向 (CMF)**: {cmf:.3f}。

**4. 传统技术指标 (Technicals)**
- **RSI(14)**: {rsi:.1f}
- **MACD**: Histogram {macd_h:.3f}
- **VWAP**: {vwap:.2f} (当前偏差: {vwap_dev:.2f}%)
"""
        except Exception as e:
            print(f"Error in generate_llm_description: {e}")
            # 返回最小化的描述
            return f"### 市场分析报告 ({symbol} | {row.name})\n\n数据处理中出现异常: {e}"