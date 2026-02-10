import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import timedelta
import json
from tqdm import tqdm  # 进度条

# ================= 1. 多周期对齐引擎 (The Engine) =================
class TimeframeAligner:
    def __init__(self, df_m5):
        """
        初始化时传入原始 M5 数据。
        自动生成 H1, H4, D1 数据层。
        """
        self.df_m5 = df_m5.copy()
        self.df_m5['timestamp'] = pd.to_datetime(self.df_m5['timestamp'])
        self.df_m5.set_index('timestamp', inplace=True)
        
        # 预计算各周期数据
        print("Resampling and calculating levels...")
        self.df_h1 = self._process_timeframe(self.df_m5, '1h', 20)
        self.df_h4 = self._process_timeframe(self.df_m5, '4h', 50) # H4看更长
        self.df_d1 = self._process_timeframe(self.df_m5, '1d', 50)
        
        # 为了快速查找，将 M5 排序
        self.df_m5.sort_index(inplace=True)

    def _process_timeframe(self, df_source, resample_rule, lookback):
        """重采样 + 计算关键位 (Swing High/Low)"""
        agg_dict = {
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }
        df_res = df_source.resample(resample_rule).agg(agg_dict).dropna()
        
        # 1. 基础趋势
        df_res['EMA_200'] = ta.ema(df_res['close'], length=200)
        
        # 2. 识别 Swing Points (关键阻力/支撑)
        # 逻辑：过去 N 根 K 线里的最高/最低点
        df_res['Swing_High'] = df_res['high'].rolling(lookback, min_periods=lookback).max()
        df_res['Swing_Low'] = df_res['low'].rolling(lookback, min_periods=lookback).min()
        
        # 3. 标记是否突破 (用于 Context 描述)
        df_res['Trend_Status'] = np.where(df_res['close'] > df_res['EMA_200'], 'Bullish', 'Bearish')
        
        return df_res

    def get_context_snapshot(self, current_time):
        """
        获取某一时刻的'金字塔'全景数据
        """
        # 1. 获取截止当前时间的最近 D1/H4/H1 行数据
        # 使用 asof 查找最近的一个【过去】时间点（避免未来函数）
        
        # D1: 我们只能看"昨天"或"今天开盘前"的数据，不能看今天的收盘
        # 这里简化逻辑：取当前时间点的最近一条重采样数据
        try:
            d1_row = self.df_d1.loc[:current_time].iloc[-1]
            h4_row = self.df_h4.loc[:current_time].iloc[-1]
            h1_rows = self.df_h1.loc[:current_time].tail(5) # 过去5小时
            m5_rows = self.df_m5.loc[:current_time].tail(24) # 过去2小时 (24根)
        except IndexError:
            return None # 数据不足

        # 2. 构建文本描述
        context = {
            "macro_d1": {
                "trend": d1_row['Trend_Status'],
                "key_resistance": f"{d1_row['Swing_High']:.2f}",
                "key_support": f"{d1_row['Swing_Low']:.2f}"
            },
            "structure_h4": {
                "trend": h4_row['Trend_Status'],
                "last_high": f"{h4_row['high']:.2f}",
                "last_low": f"{h4_row['low']:.2f}"
            },
            "recent_h1_str": h1_rows[['open','high','low','close','volume']].to_string(header=False),
            "recent_m5_str": m5_rows[['open','high','low','close','volume','RSI']].to_string()
            # 注意：需要在M5预处理里加RSI，这里假设已有
        }
        return context

# ================= 2. 高价值训练样本挖掘器 =================
class TrainingDataMiner:
    """
    从 M5 数据中挖掘高价值训练样本。
    支持两种模式:
    - 标准模式 (filtered=False): 仅按 future outcome threshold 过滤
    - 精简模式 (filtered=True): 额外添加实时波动率 + RSI 极值过滤，只保留真正有行情的时刻
    """

    # 🎯 智能过滤默认参数
    DEFAULT_VOLATILITY_THRESHOLD = 0.003  # M5 单根 K 线波动率阈值 (0.3%)
    DEFAULT_RSI_OVERSOLD = 30              # RSI 超卖阈值 (< 30 = 极端超卖)
    DEFAULT_RSI_OVERBOUGHT = 70            # RSI 超买阈值 (> 70 = 极端超买)

    def __init__(self, aligner, output_file="finetune_data.jsonl",
                 filtered=False, vol_threshold=None,
                 rsi_oversold=None, rsi_overbought=None):
        self.aligner = aligner
        self.output_file = output_file

        # 过滤配置
        self.filtered = filtered
        self.vol_threshold = vol_threshold if vol_threshold is not None else self.DEFAULT_VOLATILITY_THRESHOLD
        self.rsi_oversold = rsi_oversold if rsi_oversold is not None else self.DEFAULT_RSI_OVERSOLD
        self.rsi_overbought = rsi_overbought if rsi_overbought is not None else self.DEFAULT_RSI_OVERBOUGHT

    def calculate_future_outcome(self, df, index_pos, horizon=12):
        """
        计算未来收益 (Hindsight Truth)
        horizon=12: 向后看12根M5 K线 (即1小时)
        """
        if index_pos + horizon >= len(df):
            return None

        current_price = df.iloc[index_pos]['close']
        future_price = df.iloc[index_pos + horizon]['close']

        # 计算最大浮动盈亏 (MFE/MAE) 会更精确，这里简化用收盘价
        pct_change = (future_price - current_price) / current_price * 100
        return pct_change

    def check_candle_filter(self, row):
        """
        🎯 智能过滤: 只把算力用在刀刃上

        检查当前 K 线是否值得送去 Teacher (DeepSeek R1) 推理。
        
        核心判断 (4 步):
            1. 获取当前 K 线数据
            2. 计算波动率 (high - low) / open
            3. 计算 RSI 是否极值 (> 70 超买 或 < 30 超卖)
            4. 只有 "既没波动 AND RSI 也不极端" 才跳过
               反之: 有波动 OR RSI 极端 → 保留
               
        Returns:
            (pass_filter: bool, reason: str)
        """
        # Step 1 & 2: 计算波动率
        if row['open'] > 0:
            volatility = (row['high'] - row['low']) / row['open']
        else:
            return False, "invalid_open"

        # Step 3: 计算 RSI 是否处于极值区
        is_rsi_extreme = False
        if 'RSI' in row.index:
            rsi = row['RSI']
            if pd.notna(rsi):
                is_rsi_extreme = (rsi > self.rsi_overbought or rsi < self.rsi_oversold)

        # Step 4: 核心判断 — 既没波动，RSI 也不极端 → 跳过
        if volatility < self.vol_threshold and not is_rsi_extreme:
            return False, "low_vol_and_rsi_neutral"

        return True, "pass"

    def generate_mining_prompt(self, context, outcome, horizon_mins=60):
        """
        生成带有'标准答案'的 Prompt，用于训练 R1 归因
        """
        outcome_str = "RALLIED (Went Up)" if outcome > 0 else "DUMPED (Went Down)"

        prompt = f"""
### ROLE
You are a master Quant Trader identifying the causality behind market moves.

### MARKET CONTEXT (The Setup)
[1. MACRO D1] Trend: {context['macro_d1']['trend']} | Supp: {context['macro_d1']['key_support']} | Res: {context['macro_d1']['key_resistance']}
[2. STRUCTURE H4] Trend: {context['structure_h4']['trend']} | High: {context['structure_h4']['last_high']} | Low: {context['structure_h4']['last_low']}
[3. H1 RECENT]
{context['recent_h1_str']}

[4. M5 EXECUTION DATA (Current moment is end of list)]
{context['recent_m5_str']}

### THE TRUTH (Hindsight Information)
**REALITY CHECK:** Immediately after this M5 data, the price **{outcome_str} by {abs(outcome):.2f}%** in the next {horizon_mins} minutes.

### YOUR TASK (Reverse Engineering)
Analyze the data above and explain WHY this move happened.
1. Did price reject a D1/H4 Key Level?
2. Was there an M5 Volume anomaly or Pattern before the move?
3. Which timeframe gave the earliest warning signal?

Output valid JSON with your reasoning.
"""
        return prompt

    def run_mining(self, threshold=0.5):
        """
        主循环：挖掘高价值行情样本

        Args:
            threshold: 未来涨跌幅阈值 (%), 低于此值不生成样本

        两层过滤:
            1. [实时过滤] filtered=True 时，先检查当前 K 线波动率 + RSI
            2. [结果过滤] 检查未来 outcome 是否超过 threshold
        """
        df = self.aligner.df_m5
        dataset = []

        # 过滤统计
        stats = {
            "total_checked": 0, "filtered_candle": 0,
            "filtered_outcome": 0, "passed": 0
        }

        filter_mode = "FILTERED (volatility OR RSI extreme)" if self.filtered else "STANDARD (outcome only)"
        print(f"Mining mode: {filter_mode}", flush=True)
        print(f"Mining for future outcome > {threshold}% ...", flush=True)
        if self.filtered:
            print(f"  Volatility threshold: {self.vol_threshold*100:.2f}% (candle range/open)", flush=True)
            print(f"  RSI extreme: < {self.rsi_oversold} (oversold) or > {self.rsi_overbought} (overbought)", flush=True)
            print(f"  Rule: SKIP only when (low volatility AND RSI not extreme)", flush=True)

        for i in tqdm(range(200, len(df) - 13, 5)):
            stats["total_checked"] += 1

            # 🎯 Layer 1: 实时 K 线过滤 (filtered 模式)
            # 核心: 既没波动 AND RSI 也不极端 → 跳过
            if self.filtered:
                row = df.iloc[i]
                passed, reason = self.check_candle_filter(row)
                if not passed:
                    stats["filtered_candle"] += 1
                    continue

            # Layer 2: 未来结果过滤 (始终启用)
            outcome = self.calculate_future_outcome(df, i, horizon=12)

            if outcome and abs(outcome) >= threshold:
                curr_time = df.index[i]

                context = self.aligner.get_context_snapshot(curr_time)
                if not context:
                    continue

                prompt_text = self.generate_mining_prompt(context, outcome)

                dataset.append({
                    "timestamp": str(curr_time),
                    "input_prompt": prompt_text,
                    "future_outcome": outcome
                })
                stats["passed"] += 1
            else:
                stats["filtered_outcome"] += 1

        # 打印过滤统计
        total = max(stats['total_checked'], 1)
        print(f"\n{'='*50}", flush=True)
        print(f"Mining Statistics:", flush=True)
        print(f"  Total K-lines checked:     {stats['total_checked']:,}", flush=True)
        if self.filtered:
            print(f"  Filtered (low vol + neutral RSI): {stats['filtered_candle']:,}"
                  f" ({stats['filtered_candle']/total*100:.1f}%)", flush=True)
        print(f"  Filtered (low outcome):    {stats['filtered_outcome']:,}", flush=True)
        print(f"  Passed (high-quality):     {stats['passed']:,}"
              f" ({stats['passed']/total*100:.1f}%)", flush=True)
        print(f"{'='*50}", flush=True)

        print(f"Found {len(dataset)} high-quality setups.", flush=True)
        return dataset
