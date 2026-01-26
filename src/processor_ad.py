import tarfile
import pandas as pd
import pandas_ta as ta
import numpy as np
import io
from scipy.stats import entropy, skew, kurtosis

class DeepFeatureEngineer:
    def __init__(self, tar_path):
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

    def process(self, member_path, timeframe='5min'):
        """主处理管道"""
        # 1. 获取 Tick 数据
        raw_df = self._extract_tick_data(member_path)
        if raw_df is None or raw_df.empty: return None

        # 2. 降采样 (Resampling)
        # 除了基础 OHLCV，还要聚合订单流数据
        agg_dict = {
            'p': 'ohlc',
            'v': 'sum',
            'vol_buy': 'sum',
            'vol_sell': 'sum',
            'dollar_val': 'sum',
            'side': 'count' # 这里的 count 代表 tick_count (交易笔数)
        }
        df = raw_df.resample(timeframe).apply(agg_dict)
        # 展平列名
        df.columns = ['open', 'high', 'low', 'close', 'volume', 'vol_buy', 'vol_sell', 'turnover', 'tick_count']
        df = df.dropna()

        # 3. 特征工程流水线
        # --- A. 基础 TA (Pandas TA) ---
        # 趋势
        df.ta.adx(length=14, append=True)
        df.ta.supertrend(append=True)
        df.ta.macd(append=True)
        # 震荡
        df.ta.rsi(length=14, append=True)
        df.ta.stoch(append=True)
        # 成交量
        df.ta.vwap(append=True) # 锚定 VWAP
        df.ta.obv(append=True)
        df.ta.cmf(append=True) # Chaikin Money Flow
        
        # --- B. 高级模块 ---
        df = self._calc_volatility_metrics(df)
        df = self._calc_market_structure(df)
        df = self._calc_order_flow_metrics(df)
        df = self._calc_statistical_features(df)
        
        return df.dropna()

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