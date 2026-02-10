import pandas as pd
import pandas_ta as ta
import numpy as np

class AdvancedFeatureEngineer:
    def __init__(self):
        pass

    def process(self, df):
        """主入口：执行所有特征生成"""
        df = df.copy()
        df = self._add_volatility_metrics(df)
        df = self._add_order_flow_proxies(df)
        df = self._add_market_structure(df)
        df = self._add_momentum_and_trend(df)
        df = self._add_microstructure_features(df)
        return df.dropna()

    def _add_volatility_metrics(self, df):
        """
        1. 波动率与隐含波动率代理
        使用 Parkinson 和 Yang-Zhang 估算器，比单纯的 StdDev 更能反映盘中极端情绪。
        """
        try:
            # Parkinson Volatility (基于 High-Low，更能反映盘中震幅)
            # 公式: sqrt(1/(4*ln(2)) * ln(High/Low)^2)
            factor = 1 / (4 * np.log(2))
            df['Vol_Parkinson'] = np.sqrt(factor * (np.log(df['high'] / df['low']) ** 2)).rolling(14).mean()

            # ATR (真实波幅)
            df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            
            # Normalized ATR (NATR) - 用于跨资产比较波动率水平
            df['NATR'] = (df['ATR'] / df['close']) * 100

            # Bollinger Bandwidth (布林带带宽 - 衡量挤压/爆发)
            bb = ta.bbands(df['close'], length=20, std=2)
            
            # 处理不同的列名格式 (pandas_ta可能会添加额外的参数到列名)
            bb_upper_col = None
            bb_middle_col = None
            bb_lower_col = None
            
            for col in bb.columns:
                if 'BBU' in col:
                    bb_upper_col = col
                elif 'BBM' in col:
                    bb_middle_col = col
                elif 'BBL' in col:
                    bb_lower_col = col
            
            if bb_upper_col and bb_middle_col and bb_lower_col:
                df['BB_Width'] = (bb[bb_upper_col] - bb[bb_lower_col]) / bb[bb_middle_col]
            else:
                print(f"[WARNING] Could not find Bollinger Bands columns. Available: {bb.columns.tolist()}")
                df['BB_Width'] = np.nan
            
            # 历史波动率 (HV) - 作为 Implied Volatility (IV) 的基准参考
            df['Log_Ret'] = np.log(df['close'] / df['close'].shift(1))
            df['Hist_Vol_20'] = df['Log_Ret'].rolling(20).std() * np.sqrt(252 * 78) # 假设M5数据，年化处理

            return df
            
        except Exception as e:
            print(f"[ERROR] Error in _add_volatility_metrics: {e}")
            # Return df with NaN values to avoid complete failure
            return df

    def _add_order_flow_proxies(self, df):
        """
        2. 订单流与资金流向 (Order Flow & Liquidity)
        由于没有 L2 数据，我们使用 'Tick Volume Proxy' 和 VWAP 结构。
        """
        try:
            # VWAP (成交量加权平均价) - 机构交易员的核心基准
            # pandas-ta 的 vwap 需要 datetime index
            if 'timestamp' not in df.index.names:
                df.set_index('timestamp', inplace=True, drop=False)
            
            vwap_result = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
            if vwap_result is not None:
                df['VWAP'] = vwap_result
            else:
                print("[WARNING] VWAP calculation failed, setting to NaN")
                df['VWAP'] = np.nan
            
            # MFI (Money Flow Index) - 结合价格和成交量的 RSI
            mfi_result = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
            df['MFI'] = mfi_result if mfi_result is not None else np.nan
            
            # CMF (Chaikin Money Flow) - 衡量大资金吸筹/派发
            # 公式核心: ((Close-Low) - (High-Close)) / (High-Low) * Vol
            cmf_result = ta.cmf(df['high'], df['low'], df['close'], df['volume'], length=20)
            df['CMF'] = cmf_result if cmf_result is not None else np.nan

            # Force Index (强力指数) - 衡量价格变动的力量
            # 价格变动 * 成交量
            efi_result = ta.efi(df['close'], df['volume'], length=13)
            df['Force_Index'] = efi_result if efi_result is not None else np.nan
            
            # Pseudo-CVD (伪累计成交量增量)
            # 逻辑：如果是阳线，假设 Volume 为买入；阴线为卖出。
            # 改进版：根据 Close 在 High-Low 中的位置分配 Volume
            buy_vol_proxy = df['volume'] * ((df['close'] - df['low']) / (df['high'] - df['low'] + 1e-9))
            sell_vol_proxy = df['volume'] * ((df['high'] - df['close']) / (df['high'] - df['low'] + 1e-9))
            df['Delta_Vol'] = buy_vol_proxy - sell_vol_proxy
            df['CVD'] = df['Delta_Vol'].cumsum() # 累计值，用于看背离

            return df
            
        except Exception as e:
            print(f"[ERROR] Error in _add_order_flow_proxies: {e}")
            return df

    def _add_market_structure(self, df):
        """
        3. 市场结构 (Market Structure)
        识别 Swing High/Low，这是 Price Action 的核心。
        """
        try:
            window = 5 # 左右各看5根K线来确定高低点
            
            # 识别局部高点 (Pivot High)
            df['is_swing_high'] = df['high'].rolling(window*2+1, center=True).max() == df['high']
            # 识别局部低点 (Pivot Low)
            df['is_swing_low'] = df['low'].rolling(window*2+1, center=True).min() == df['low']
            
            # 填充最近的一个 Swing High/Low 价格，方便 LLM 比较当前价格与结构位
            df['Last_Swing_High'] = df['high'].where(df['is_swing_high']).ffill()
            df['Last_Swing_Low'] = df['low'].where(df['is_swing_low']).ffill()
            
            # 结构突破信号 (BOS - Break of Structure)
            # 如果当前收盘价 > 上一个 Swing High -> Bullish BOS
            df['BOS_Bullish'] = (df['close'] > df['Last_Swing_High'].shift(1)) & (df['close'].shift(1) <= df['Last_Swing_High'].shift(1))
            df['BOS_Bearish'] = (df['close'] < df['Last_Swing_Low'].shift(1)) & (df['close'].shift(1) >= df['Last_Swing_Low'].shift(1))

            return df
            
        except Exception as e:
            print(f"[ERROR] Error in _add_market_structure: {e}")
            return df

    def _add_microstructure_features(self, df):
        """
        4. Micro-structure features (Wick, Body, Efficiency Ratio, Distance from VWAP)
        """
        try:
            # Effective Spread Estimate (Effective spread estimation)
            # Roll model (1984): Spread = 2 * sqrt(-Cov(Delta P_t, Delta P_t-1))
            # Using simpler High-Low relative to Close ratio to measure liquidity tightness
            df['Wick_Upper'] = df['high'] - np.maximum(df['close'], df['open'])
            df['Wick_Lower'] = np.minimum(df['close'], df['open']) - df['low']
            df['Body_Size'] = np.abs(df['close'] - df['open'])
            
            # Candle Efficiency (Candle efficiency)
            # If large volume but small body -> Absorption/Resistance
            df['Efficiency_Ratio'] = df['Body_Size'] / (df['volume'] + 1) 
            
            # Price retracement depth (relative to current Trend)
            if 'VWAP' in df.columns:
                df['Dist_from_VWAP'] = (df['close'] - df['VWAP']) / (df['VWAP'] + 1e-10) * 100
            else:
                df['Dist_from_VWAP'] = np.nan
            
            return df
        except Exception as e:
            print(f"[ERROR] Error in _add_microstructure_features: {e}")
            return df

    def _add_momentum_and_trend(self, df):
        """
        5. Momentum and Trend features (RSI, MACD, ADX)
        """
        try:
            # RSI (Relative Strength Index)
            rsi_result = ta.rsi(df['close'], length=14)
            if rsi_result is not None and not rsi_result.empty:
                df['RSI'] = rsi_result
            else:
                df['RSI'] = np.nan
            
            # MACD (Moving Average Convergence Divergence)
            macd_result = ta.macd(df['close'])
            if macd_result is not None and not macd_result.empty:
                df['MACD'] = macd_result.iloc[:, 0]
                df['MACD_SIGNAL'] = macd_result.iloc[:, 1]
                df['MACD_HIST'] = macd_result.iloc[:, 2]
            else:
                df['MACD'] = np.nan
                df['MACD_SIGNAL'] = np.nan
                df['MACD_HIST'] = np.nan
            
            # ADX (Average Directional Index - Trend Strength)
            adx_result = ta.adx(df['high'], df['low'], df['close'], length=14)
            if adx_result is not None and not adx_result.empty:
                # Find ADX column dynamically
                adx_col = None
                for col in adx_result.columns:
                    if 'ADX' in col and '14' in col:
                        adx_col = col
                        break
                if adx_col:
                    df['ADX'] = adx_result[adx_col]
                else:
                    df['ADX'] = np.nan
            else:
                df['ADX'] = np.nan
            
            return df
        except Exception as e:
            print(f"[ERROR] Error in _add_momentum_and_trend: {e}")
            return df

# ---------------- 使用示例 ----------------
if __name__ == "__main__":
    # 假设你已经有了 df
    # loader = MarketDataLoader(...)
    # df = loader.fetch_candles(...)
    
    # 为了演示，生成假数据
    dates = pd.date_range(start="2023-01-01", periods=200, freq="5T")
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(100, 105, 200),
        'high': np.random.uniform(105, 110, 200),
        'low': np.random.uniform(95, 100, 200),
        'close': np.random.uniform(100, 105, 200),
        'volume': np.random.randint(1000, 10000, 200)
    })
    
    engineer = AdvancedFeatureEngineer()
    df_processed = engineer.process(df)
    
    print("生成的特征列:", df_processed.columns.tolist())
    print(df_processed[['close', 'VWAP', 'CVD', 'Vol_Parkinson', 'BOS_Bullish']].tail())