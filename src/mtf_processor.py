import pandas as pd
import pandas_ta as ta

class MultiTimeframeProcessor:
    def __init__(self, df_m5):
        self.df_m5 = df_m5.copy()
        self.df_m5['timestamp'] = pd.to_datetime(self.df_m5['timestamp'])
        self.df_m5.set_index('timestamp', inplace=True)

    def resample_data(self, timeframe):
        """
        将M5数据重采样为指定周期 (e.g., '1h', '4h', '1d')
        """
        logic = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        df_resampled = self.df_m5.resample(timeframe).agg(logic).dropna()
        
        # 重新计算该周期的基础指标
        df_resampled['EMA_200'] = ta.ema(df_resampled['close'], length=200)
        df_resampled['RSI'] = ta.rsi(df_resampled['close'], length=14)
        return df_resampled

    def get_key_levels(self, df, lookback=20):
        """提取最近 N 根K线的关键支撑/阻力位 (Swing High/Low)"""
        highs = df['high'].rolling(5, center=True).max()
        lows = df['low'].rolling(5, center=True).min()
        
        # 获取最近的两个 Swing Levels
        last_high = highs.dropna().iloc[-lookback:].max()
        last_low = lows.dropna().iloc[-lookback:].min()
        
        return {
            "Resistance": last_high,
            "Support": last_low,
            "Trend": "Bullish" if df['close'].iloc[-1] > df['EMA_200'].iloc[-1] else "Bearish"
        }

    def prepare_hierarchical_context(self, current_timestamp):
        """
        核心函数：构建金字塔上下文
        """
        # 1. 切片截止到当前时间
        end_time = current_timestamp
        # 确保不通过未来函数，只取 end_time 之前的数据
        mask_m5 = self.df_m5.index <= end_time
        
        if not mask_m5.any(): return None
        
        # 2. 生成各周期数据快照
        df_history = self.df_m5.loc[mask_m5]
        
        # D1 (宏观): 取过去 50 天
        df_d1 = self.resample_data('1D')
        df_d1 = df_d1[df_d1.index <= end_time].tail(50)
        d1_levels = self.get_key_levels(df_d1, lookback=50)
        
        # H4 (结构): 取过去 50 根
        df_h4 = self.resample_data('4h')
        df_h4 = df_h4[df_h4.index <= end_time].tail(50)
        h4_levels = self.get_key_levels(df_h4, lookback=20)
        
        # H1 (趋势): 取过去 24 根
        df_h1 = self.resample_data('1h')
        df_h1 = df_h1[df_h1.index <= end_time].tail(24)
        
        # M5 (微观/执行): 取过去 60 根 (5小时)
        df_m5_recent = df_history.tail(60).copy()
        
        return {
            "D1_Context": d1_levels,
            "H4_Context": h4_levels,
            "H1_Recent": df_h1.tail(5)[['open','high','low','close','volume']].to_string(header=False),
            "M5_Detailed": df_m5_recent[['open','high','low','close','volume']].to_string()
        }