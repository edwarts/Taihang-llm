# -*- coding: utf-8 -*-
import json
import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 轻量级导入 (秒级)
from src.config import TARGET_SYMBOLS

# 重型模块延迟导入 (pandas_ta 等加载需要 60s+)
# AdvancedFeatureEngineer, TimeframeAligner, TrainingDataMiner
# 在 main_pipeline() 内部按需导入，避免启动时卡顿


def parse_year_args(year_args):
    """
    解析年份参数，支持单个年份和范围格式
    
    Examples:
        ['2018', '2019', '2020']  -> [2018, 2019, 2020]
        ['2018-2022']             -> [2018, 2019, 2020, 2021, 2022]
        ['2018-2020', '2023']     -> [2018, 2019, 2020, 2023]
    """
    years_set = set()
    for arg in year_args:
        if '-' in arg and not arg.startswith('-'):
            parts = arg.split('-')
            if len(parts) == 2:
                try:
                    start, end = int(parts[0]), int(parts[1])
                    years_set.update(range(start, end + 1))
                except ValueError:
                    print(f"[WARNING] Invalid year range: {arg}, skipping", flush=True)
        else:
            try:
                years_set.add(int(arg))
            except ValueError:
                print(f"[WARNING] Invalid year: {arg}, skipping", flush=True)
    return sorted(years_set)


def format_year_tag(year_list):
    """
    将年份列表转为文件名标签，每个年份显式列出
    
    Examples:
        [2020, 2021, 2022]              -> '_y2020_2021_2022'
        [2008, 2017, 2020, 2021, 2022]  -> '_y2008_2017_2020_2021_2022'
        [2021]                          -> '_y2021'
        None 或 []                      -> ''  (不加标签)
    """
    if not year_list:
        return ""
    years = sorted(year_list)
    return "_y" + "_".join(str(y) for y in years)


def load_history_file(symbol, window, years, history_dir="data/premium_history"):
    """
    Load historical data from CSV file with fallback strategy.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        window: Timeframe (e.g., '5m', '1m', '15m')
        years: Target years (e.g., 10)
        history_dir: Directory containing historical CSV files
        
    Returns:
        DataFrame with loaded data, or None if no data found
        
    Strategy:
        1. Try exact file: {symbol}_{window}_{years}y_history.csv
        2. If not found, try to fallback to fewer years: {symbol}_{window}_{years-1}y_history.csv, etc.
        3. If all fail, return None
    """
    import pandas as pd
    
    # Try from target years down to 1 year
    fallback_years = list(range(years, 0, -1))
    
    for attempt_years in fallback_years:
        filename = f"{symbol}_{window}_{attempt_years}y_history.csv"
        filepath = os.path.join(history_dir, filename)
        
        if os.path.exists(filepath):
            print(f"[INFO] Loading {symbol} ({attempt_years}y): {filepath}", flush=True)
            try:
                df = pd.read_csv(filepath)
                
                # Ensure timestamp column exists
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.sort_values('timestamp').reset_index(drop=True)
                
                print(f"[SUCCESS] Loaded {len(df)} records from {symbol} ({attempt_years}y)", flush=True)
                return df, attempt_years
            except Exception as e:
                print(f"[WARNING] Error loading {filepath}: {e}", flush=True)
                continue
    
    print(f"[WARNING] No data found for {symbol} with window {window} and {years} years", flush=True)
    return None, 0


def main_pipeline(symbol=None, years=15, window="5m", history_dir="data/premium_history",
                  filtered=False, vol_threshold=None,
                  rsi_oversold=None, rsi_overbought=None, output_dir=None,
                  select_years=None):
    """
    Process single or multiple symbols for CTA pipeline.
    
    Args:
        symbol: Single symbol to process (e.g., 'AAPL'), or None to process all from TARGET_SYMBOLS
        years: Historical data years (fallback supported, default: 15)
        window: Timeframe (e.g., '5m', '1m', default: 5m)
        history_dir: Directory containing premium history CSV files
        filtered: 是否启用智能过滤模式 (波动率 + RSI)
        vol_threshold: 波动率阈值 (默认 0.003 = 0.3%)
        rsi_oversold: RSI 超卖阈值 (默认 30, RSI < 30 视为极端超卖)
        rsi_overbought: RSI 超买阈值 (默认 70, RSI > 70 视为极端超买)
        output_dir: 自定义输出目录 (默认: filtered -> data/filtered_q/, standard -> data/)
        select_years: 指定年份列表 (e.g., [2020, 2021, 2022]), 只处理这些年份的数据
    """
    # 延迟导入重型模块 — 逐步加载并打印进度
    import time as _time
    _t0 = _time.time()
    
    print("[INIT] 1/5 Loading pandas...", flush=True)
    import pandas as pd
    print(f"[INIT] 1/5 pandas OK ({_time.time()-_t0:.1f}s)", flush=True)
    
    print("[INIT] 2/5 Loading numpy...", flush=True)
    import numpy as np
    print(f"[INIT] 2/5 numpy OK ({_time.time()-_t0:.1f}s)", flush=True)
    
    print("[INIT] 3/5 Loading tqdm...", flush=True)
    from tqdm import tqdm
    print(f"[INIT] 3/5 tqdm OK ({_time.time()-_t0:.1f}s)", flush=True)
    
    print("[INIT] 4/5 Loading AdvancedFeatureEngineer (includes pandas_ta)...", flush=True)
    from src.advanced_feature_engineer import AdvancedFeatureEngineer
    print(f"[INIT] 4/5 AdvancedFeatureEngineer OK ({_time.time()-_t0:.1f}s)", flush=True)
    
    print("[INIT] 5/5 Loading TimeframeAligner, TrainingDataMiner...", flush=True)
    from src.timeframe_aligner import TimeframeAligner, TrainingDataMiner
    print(f"[INIT] 5/5 All modules loaded! (total: {_time.time()-_t0:.1f}s)", flush=True)

    # Determine which symbols to process
    symbols_to_process = [symbol] if symbol else TARGET_SYMBOLS

    # 确定输出目录
    if output_dir:
        out_dir = output_dir
    elif filtered:
        out_dir = os.path.join("data", "filtered_q")
    else:
        out_dir = "data"

    # 确保输出目录存在
    os.makedirs(out_dir, exist_ok=True)

    mode_label = "FILTERED (volatility+RSI)" if filtered else "STANDARD"
    print(f"[INFO] Processing {len(symbols_to_process)} symbol(s)", flush=True)
    print(f"[INFO] Mode: {mode_label}", flush=True)
    print(f"[INFO] Configuration: window={window}, years={years}", flush=True)
    if select_years:
        print(f"[INFO] Year filter: {select_years}", flush=True)
    print(f"[INFO] Output directory: {out_dir}", flush=True)
    if filtered:
        vt = vol_threshold if vol_threshold is not None else TrainingDataMiner.DEFAULT_VOLATILITY_THRESHOLD
        ros = rsi_oversold if rsi_oversold is not None else TrainingDataMiner.DEFAULT_RSI_OVERSOLD
        rob = rsi_overbought if rsi_overbought is not None else TrainingDataMiner.DEFAULT_RSI_OVERBOUGHT
        print(f"[INFO] Filter params: vol_threshold={vt*100:.2f}%, RSI extreme: <{ros} or >{rob}", flush=True)
        print(f"[INFO] Rule: SKIP only when (low volatility AND RSI not extreme)", flush=True)
    print("=" * 70, flush=True)
    
    successful = []
    failed = []
    
    for sym_idx, current_symbol in enumerate(symbols_to_process, 1):
        try:
            print(f"\n[{sym_idx}/{len(symbols_to_process)}] Processing {current_symbol}...", flush=True)
            
            # Load historical data
            df_raw, actual_years = load_history_file(current_symbol, window, years, history_dir)
            
            if df_raw is None or df_raw.empty:
                print(f"[ERROR] Could not load any data for {current_symbol}", flush=True)
                failed.append(current_symbol)
                continue
            
            # 按年份筛选数据
            if select_years and 'timestamp' in df_raw.columns:
                original_count = len(df_raw)
                df_raw = df_raw[df_raw['timestamp'].dt.year.isin(select_years)]
                df_raw = df_raw.reset_index(drop=True)
                print(f"[YEAR-FILTER] {current_symbol}: {len(df_raw):,}/{original_count:,} rows "
                      f"(years: {select_years})", flush=True)
                if df_raw.empty:
                    print(f"[WARNING] No data for {current_symbol} in years {select_years}", flush=True)
                    failed.append(current_symbol)
                    continue
            
            # Feature Engineering (M5 level)
            print(f"[INFO] Running Advanced Feature Engineering for {current_symbol}...", flush=True)
            engineer = AdvancedFeatureEngineer() 
            df_processed = engineer.process(df_raw)
            
            if df_processed.empty:
                print(f"[ERROR] Feature engineering produced empty dataframe for {current_symbol}", flush=True)
                failed.append(current_symbol)
                continue
            
            # Initialize multi-timeframe aligner
            print(f"[INFO] Aligning Timeframes for {current_symbol}...", flush=True)
            aligner = TimeframeAligner(df_processed)
            
            # Mining high-value training samples
            print(f"[INFO] Mining High-Volatility Setups for {current_symbol}...", flush=True)
            miner = TrainingDataMiner(
                aligner,
                filtered=filtered,
                vol_threshold=vol_threshold,
                rsi_oversold=rsi_oversold,
                rsi_overbought=rsi_overbought
            )
            mined_data = miner.run_mining(threshold=0.4)
            
            # Save inference-ready file
            tag = "filtered_" if filtered else ""
            year_tag = format_year_tag(select_years)
            output_filename = f"deepseek_r1_input_prompts_{tag}{current_symbol}_{window}_{actual_years}y{year_tag}.jsonl"
            output_filepath = os.path.join(out_dir, output_filename)
            output_records = []
            with open(output_filepath, 'w', encoding='utf-8') as f:
                for item in mined_data:
                    record = {
                        "custom_id": f"{current_symbol}_{item['timestamp']}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": "deepseek-reasoner",
                            "messages": [
                                {"role": "system", "content": "You are a specialized trading AI."},
                                {"role": "user", "content": item['input_prompt']}
                            ]
                        }
                    }
                    output_records.append(record)
                    f.write(json.dumps(record) + "\n")
            
            print(f"[SUCCESS] {current_symbol} finished!", flush=True)
            print(f"[INFO] Generated {len(mined_data)} prompts -> {output_filepath}", flush=True)
            successful.append((current_symbol, output_filename, output_records))
            
        except Exception as e:
            print(f"[ERROR] {current_symbol} failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            failed.append(current_symbol)
            continue
    
    # Merge all successful outputs into a consolidated file
    if successful:
        print("\n[INFO] Merging output files into consolidated training dataset...", flush=True)
        consolidated_records = []
        total_records = 0
        
        for symbol_name, output_filename, output_records in successful:
            consolidated_records.extend(output_records)
            total_records += len(output_records)
        
        # Create consolidated filename
        tag = "filtered_" if filtered else ""
        year_tag = format_year_tag(select_years)
        if len(successful) == 1:
            consolidated_filename = f"deepseek_r1_input_prompts_{tag}CONSOLIDATED_{successful[0][0]}_{window}_{years}y{year_tag}.jsonl"
        else:
            consolidated_filename = f"deepseek_r1_input_prompts_{tag}CONSOLIDATED_{len(successful)}symbols_{window}_{years}y{year_tag}.jsonl"
        
        consolidated_filepath = os.path.join(out_dir, consolidated_filename)
        
        # Write consolidated file
        with open(consolidated_filepath, 'w', encoding='utf-8') as f:
            for record in consolidated_records:
                f.write(json.dumps(record) + "\n")
        
        print(f"[SUCCESS] Consolidated file created: {consolidated_filepath}", flush=True)
        print(f"[INFO] Total records in consolidated file: {total_records}", flush=True)
    
    # Summary
    print("\n" + "=" * 70, flush=True)
    print("[SUMMARY] CTA Pipeline Execution Report", flush=True)
    print("=" * 70, flush=True)
    print(f"[RESULT] Mode: {mode_label}", flush=True)
    print(f"[RESULT] Output: {out_dir}", flush=True)
    print(f"[RESULT] Successful: {len(successful)}/{len(symbols_to_process)}", flush=True)
    print(f"[RESULT] Failed: {len(failed)}/{len(symbols_to_process)}", flush=True)
    
    if successful:
        success_symbols = [s[0] for s in successful]
        print(f"\n[SUCCESS] Processed symbols: {', '.join(success_symbols)}", flush=True)
    if failed:
        print(f"\n[FAILED] Failed symbols: {', '.join(failed)}", flush=True)
    
    print("=" * 70, flush=True)

if __name__ == "__main__":
    # Force UTF-8 output for Windows compatibility
    # 关键: line_buffering=True 防止 Windows 下 reconfigure 后输出被全缓冲
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except (AttributeError, OSError):
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    # 立即可见的启动提示
    print("[BOOT] CTA Pipeline starting...", flush=True)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="CTA Pipeline - Process stock data and generate DeepSeek prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all symbols with default settings (15 years, 5m window)
  python pipeline_main_cta_structure.py
  
  # Process single symbol AAPL
  python pipeline_main_cta_structure.py --symbol AAPL
  
  # Process all symbols with 2 years of data, 1m window
  python pipeline_main_cta_structure.py --years 2 --window 1m
  
  # Process TSLA with 15 years, 5m window
  python pipeline_main_cta_structure.py --symbol TSLA --years 15 --window 5m
  
  # === 精简模式: 只生成高波动+RSI极值的 prompts ===
  # 生成精简版 (输出到 data/filtered_q/)
  python pipeline_main_cta_structure.py --symbol AAPL --filtered
  
  # 自定义波动率阈值 (0.5%)
  python pipeline_main_cta_structure.py --symbol AAPL --filtered --vol-threshold 0.005
  
  # 自定义 RSI 极值阈值 (默认 30/70)
  python pipeline_main_cta_structure.py --symbol AAPL --filtered --rsi-oversold 25 --rsi-overbought 75
  
  # === 指定年份 ===
  # 精简版 + 连续年份 + 全部 symbols → _y2020-2024
  python pipeline_main_cta_structure.py --filtered --run-years 2020-2024
  
  # 精简版 + 非连续年份 + 全部 symbols → _y2008_2017_2021-2022
  python pipeline_main_cta_structure.py --filtered --run-years 2008 2017 2021 2022
  
  # 单个 symbol + 非连续年份
  python pipeline_main_cta_structure.py -s AAPL --filtered --run-years 2008 2017 2021 2022
  
  # 混合范围 + 精简版 → _y2018-2020_2023-2024
  python pipeline_main_cta_structure.py --filtered --run-years 2018-2020 2023 2024
        """
    )
    
    parser.add_argument(
        '-s', '--symbol',
        type=str,
        default=None,
        help='Single symbol to process (e.g., AAPL). If not specified, process all symbols from config.py'
    )
    
    parser.add_argument(
        '-y', '--years',
        type=int,
        default=15,
        help='Historical data years (default: 15). Supports fallback to fewer years if data unavailable'
    )
    
    parser.add_argument(
        '-w', '--window',
        type=str,
        default='5m',
        choices=['1m', '5m', '15m', '30m', '60m', 'D'],
        help='Timeframe window (default: 5m). Must match filename pattern'
    )
    
    parser.add_argument(
        '--history-dir',
        type=str,
        default='data/premium_history',
        help='Directory containing premium history CSV files (default: data/premium_history)'
    )

    # ===== 智能过滤参数 =====
    parser.add_argument(
        '--filtered',
        action='store_true',
        default=False,
        help='启用智能过滤模式: 波动率 + RSI 极值过滤, 输出到 data/filtered_q/'
    )

    parser.add_argument(
        '--vol-threshold',
        type=float,
        default=None,
        help='波动率阈值 (默认 0.003 = 0.3%%). 单根 K 线 (high-low)/open 低于此值被过滤'
    )

    parser.add_argument(
        '--rsi-oversold',
        type=float,
        default=None,
        help='RSI 超卖阈值 (默认 30). RSI < 此值视为极端超卖, 保留该 K 线'
    )

    parser.add_argument(
        '--rsi-overbought',
        type=float,
        default=None,
        help='RSI 超买阈值 (默认 70). RSI > 此值视为极端超买, 保留该 K 线'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='自定义输出目录 (默认: filtered -> data/filtered_q/, standard -> data/)'
    )

    parser.add_argument(
        '--run-years',
        nargs='+',
        type=str,
        default=None,
        help='指定年份生成全部 config.py symbols 的 prompts (支持范围: --run-years 2020-2024 或 2018 2020 2023)'
    )
    
    args = parser.parse_args()
    
    # --run-years: 解析年份, 可配合 -s 指定 symbol 或省略 -s 跑全部
    run_symbol = args.symbol
    run_select_years = None

    if args.run_years:
        parsed_years = parse_year_args(args.run_years)
        if not parsed_years:
            print("[ERROR] --run-years 未解析到有效年份, 请检查格式 (如: 2020-2024 或 2008 2017 2021 2022)", flush=True)
            sys.exit(1)

        run_select_years = parsed_years

        if args.symbol:
            # 指定 symbol + 指定年份
            run_symbol = args.symbol
            print(f"[RUN-YEARS] Symbol: {run_symbol}", flush=True)
        else:
            # 未指定 symbol → 全部 symbols
            run_symbol = None
            print(f"[RUN-YEARS] 处理全部 {len(TARGET_SYMBOLS)} 个 symbols: {', '.join(TARGET_SYMBOLS)}", flush=True)

        print(f"[RUN-YEARS] 指定年份: {parsed_years}", flush=True)
        print(f"[RUN-YEARS] 文件标签: {format_year_tag(parsed_years)}", flush=True)

    try:
        print("=" * 70, flush=True)
        print("[START] CTA Pipeline - Main Structure", flush=True)
        print("=" * 70, flush=True)
        print(f"[CONFIG] Symbol: {run_symbol if run_symbol else f'All {len(TARGET_SYMBOLS)} from config.py'}", flush=True)
        print(f"[CONFIG] Years: {args.years} (with fallback support)", flush=True)
        if run_select_years:
            print(f"[CONFIG] Year filter: {run_select_years}", flush=True)
        print(f"[CONFIG] Window: {args.window}", flush=True)
        print(f"[CONFIG] History Dir: {args.history_dir}", flush=True)
        print(f"[CONFIG] Filtered Mode: {args.filtered}", flush=True)
        if args.filtered:
            print(f"[CONFIG] Vol Threshold: {args.vol_threshold or 'default (0.003)'}", flush=True)
            print(f"[CONFIG] RSI Oversold: {args.rsi_oversold or 'default (30)'}", flush=True)
            print(f"[CONFIG] RSI Overbought: {args.rsi_overbought or 'default (70)'}", flush=True)
            print(f"[CONFIG] Rule: SKIP when (low vol AND RSI not extreme)", flush=True)
        print("=" * 70, flush=True)
        
        # Run pipeline
        main_pipeline(
            symbol=run_symbol,
            years=args.years,
            window=args.window,
            history_dir=args.history_dir,
            filtered=args.filtered,
            vol_threshold=args.vol_threshold,
            rsi_oversold=args.rsi_oversold,
            rsi_overbought=args.rsi_overbought,
            output_dir=args.output_dir,
            select_years=run_select_years
        )
        
        print("\n[SUCCESS] All processing complete!", flush=True)
        
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
