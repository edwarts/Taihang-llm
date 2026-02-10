import sys
import os
import asyncio
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Tuple

# 路径黑魔法：确保能导入 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bridge import FinnhubBridge
from src.processor import DeepFeatureEngineer
from src.factory import LocalDataFactory

# 你的 Finnhub Key
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY") or "d5jsub1r01qjaedrkpigd5jsub1r01qjaedrkpj0"

# ==================== 1. 数据验证与质量指标 ====================
class DataQualityValidator:
    """数据质量验证和指标计算"""
    
    @staticmethod
    def calculate_quality_metrics(df_raw: pd.DataFrame, df_processed: pd.DataFrame, symbol: str) -> Dict:
        """
        计算数据质量指标
        
        Returns:
            dict: 包含多个质量指标的字典
        """
        metrics = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'raw_rows': len(df_raw),
            'processed_rows': len(df_processed),
            'data_retention_rate': (len(df_processed) / len(df_raw) * 100) if len(df_raw) > 0 else 0,
            'nan_distribution': {},
            'feature_completeness': 0,
            'price_validity': {},
            'volume_validity': {},
            'data_gaps': 0,
        }
        
        # NaN 分布分析
        nan_counts = df_processed.isna().sum()
        metrics['nan_distribution'] = {
            col: int(count) for col, count in nan_counts[nan_counts > 0].items()
        }
        
        # 特征完整性 (有效列数 / 总列数)
        metrics['feature_completeness'] = (len(df_processed.columns) / max(len(df_processed.columns), 1)) * 100
        
        # 价格有效性检查
        if 'close' in df_raw.columns:
            price_data = df_raw['close'].dropna()
            metrics['price_validity'] = {
                'mean': float(price_data.mean()),
                'std': float(price_data.std()),
                'min': float(price_data.min()),
                'max': float(price_data.max()),
                'valid_count': int(len(price_data)),
                'invalid_count': int(len(df_raw) - len(price_data)),
            }
        
        # 成交量有效性检查
        if 'volume' in df_raw.columns:
            volume_data = df_raw['volume'].dropna()
            metrics['volume_validity'] = {
                'mean': float(volume_data.mean()),
                'total': float(volume_data.sum()),
                'min': float(volume_data.min()),
                'max': float(volume_data.max()),
                'zero_volume_count': int((volume_data == 0).sum()),
            }
        
        # 时间序列间隙检测 (假设 1 分钟数据)
        if len(df_raw) > 1:
            time_diffs = df_raw.index.to_series().diff()
            expected_gap = pd.Timedelta(minutes=1)
            gaps = (time_diffs > expected_gap).sum()
            metrics['data_gaps'] = int(gaps)
        
        return metrics
    
    @staticmethod
    def print_quality_report(metrics: Dict):
        """打印数据质量报告"""
        print("\n" + "="*60)
        print("📊 数据质量报告")
        print("="*60)
        print(f"符号: {metrics['symbol']}")
        print(f"时间: {metrics['timestamp']}")
        print(f"\n原始数据行数: {metrics['raw_rows']}")
        print(f"处理后数据行数: {metrics['processed_rows']}")
        print(f"数据保留率: {metrics['data_retention_rate']:.2f}%")
        print(f"特征完整性: {metrics['feature_completeness']:.1f}%")
        
        if metrics['price_validity']:
            pv = metrics['price_validity']
            print(f"\n价格有效性:")
            print(f"  - 均价: ${pv['mean']:.2f}")
            print(f"  - 标准差: ${pv['std']:.4f}")
            print(f"  - 范围: ${pv['min']:.2f} - ${pv['max']:.2f}")
            print(f"  - 有效数据: {pv['valid_count']}/{pv['valid_count'] + pv['invalid_count']}")
        
        if metrics['volume_validity']:
            vv = metrics['volume_validity']
            print(f"\n成交量有效性:")
            print(f"  - 平均成交量: {vv['mean']:.0f}")
            print(f"  - 总成交量: {vv['total']:.0f}")
            print(f"  - 零成交量K线: {vv['zero_volume_count']}")
        
        if metrics['nan_distribution']:
            print(f"\nNaN值分布 (前5列):")
            for col, count in list(metrics['nan_distribution'].items())[:5]:
                pct = (count / metrics['raw_rows'] * 100) if metrics['raw_rows'] > 0 else 0
                print(f"  - {col}: {count} ({pct:.2f}%)")
        
        if metrics['data_gaps'] > 0:
            print(f"\n⚠️  检测到 {metrics['data_gaps']} 个时间间隙")
        
        print("="*60 + "\n")

# ==================== 2. 多符号/多周期测试框架 ====================
class MultiSymbolTester:
    """支持多个符号和时间范围的测试框架"""
    
    def __init__(self, api_key: str):
        self.bridge = FinnhubBridge(api_key)
        self.engineer = DeepFeatureEngineer(tar_path=None)
        self.validator = DataQualityValidator()
        self.results = []
    
    async def test_symbol(self, symbol: str, days: int = 30) -> Tuple[Dict, pd.DataFrame]:
        """
        测试单个符号
        
        Args:
            symbol: 股票符号 (e.g., 'NVDA')
            days: 天数范围
        
        Returns:
            tuple: (质量指标字典, 处理后的数据帧)
        """
        print(f"\n🔍 处理 {symbol} (days={days})...")
        
        # 获取原始数据
        df_raw = self.bridge.fetch_recent_data(symbol, days=days)
        
        if df_raw is None or df_raw.empty:
            print(f"  ❌ 获取失败")
            return None, pd.DataFrame()
        
        print(f"  ✅ 获取 {len(df_raw)} 条数据")
        
        # 处理数据
        df_processed = self.engineer.process_dataframe(df_raw)
        print(f"  ✅ 处理完成，有效样本: {len(df_processed)}")
        
        # 计算质量指标
        metrics = self.validator.calculate_quality_metrics(df_raw, df_processed, symbol)
        
        return metrics, df_processed
    
    async def run_batch_tests(self, test_configs: List[Dict]) -> List[Dict]:
        """
        批量运行多个测试配置
        
        Args:
            test_configs: 配置列表，每个包含 {'symbol': str, 'days': int}
        
        Returns:
            list: 所有测试的质量指标
        """
        all_metrics = []
        
        for config in test_configs:
            symbol = config.get('symbol', 'NVDA')
            days = config.get('days', 30)
            
            metrics, df = await self.test_symbol(symbol, days)
            
            if metrics is not None:
                all_metrics.append(metrics)
                self.validator.print_quality_report(metrics)
        
        return all_metrics

# ==================== 3. 优化的特征计算 ====================
class OptimizedFeatureCalculator:
    """带性能监控的特征计算"""
    
    @staticmethod
    def calculate_with_profiling(engineer: DeepFeatureEngineer, df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        计算特征并记录性能指标
        
        Returns:
            tuple: (处理后的数据帧, 性能指标字典)
        """
        import time
        
        performance = {
            'total_time': 0,
            'stages': {},
            'optimization_notes': []
        }
        
        start = time.time()
        
        # 阶段 1: 基础处理
        stage_start = time.time()
        df = df_raw.copy()
        if len(df) < 30:
            performance['optimization_notes'].append("数据过少 (<30行)")
            return pd.DataFrame(), performance
        performance['stages']['data_validation'] = time.time() - stage_start
        
        # 阶段 2: 技术指标 (使用 pandas_ta 优化)
        stage_start = time.time()
        try:
            df.ta.rsi(length=14, append=True)
            df.ta.atr(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.supertrend(length=7, multiplier=3.0, append=True)
            df.ta.vwap(append=True)
            df.ta.cmf(length=20, append=True)
            performance['stages']['technical_indicators'] = time.time() - stage_start
        except Exception as e:
            performance['optimization_notes'].append(f"技术指标计算失败: {str(e)}")
            return pd.DataFrame(), performance
        
        # 阶段 3: 高级指标
        stage_start = time.time()
        try:
            df = engineer._calc_volatility_metrics_safe(df)
            df = engineer._calc_market_structure(df, window=5)
            df = engineer._calc_order_flow_metrics(df)
            df = engineer._calc_statistical_features(df, window=5)
            performance['stages']['advanced_metrics'] = time.time() - stage_start
        except Exception as e:
            performance['optimization_notes'].append(f"高级指标计算失败: {str(e)}")
            return pd.DataFrame(), performance
        
        # 阶段 4: 智能 NaN 处理
        stage_start = time.time()
        df_clean = df.dropna()
        if len(df_clean) == 0:
            df_clean = df.dropna(thresh=len(df.columns) * 0.7)
        if len(df_clean) == 0:
            df_clean = df.dropna(thresh=len(df.columns) * 0.5)
        performance['stages']['nan_handling'] = time.time() - stage_start
        
        performance['total_time'] = time.time() - start
        performance['optimization_notes'].append(
            f"NaN处理: strict->70%->50%阈值策略，最终保留 {len(df_clean)}/{len(df)} 行"
        )
        
        return df_clean, performance
    
    @staticmethod
    def print_performance_report(metrics: Dict, symbol: str):
        """打印性能分析报告"""
        print("\n" + "="*60)
        print(f"⚡ 性能分析报告 ({symbol})")
        print("="*60)
        print(f"总耗时: {metrics['total_time']*1000:.2f}ms\n")
        
        print("分阶段耗时:")
        for stage, duration in metrics['stages'].items():
            pct = (duration / metrics['total_time'] * 100) if metrics['total_time'] > 0 else 0
            print(f"  {stage:.<30} {duration*1000:>7.2f}ms ({pct:>5.1f}%)")
        
        if metrics['optimization_notes']:
            print("\n优化说明:")
            for note in metrics['optimization_notes']:
                print(f"  • {note}")
        
        print("="*60 + "\n")

# ==================== 4. LLM Description 生成测试 ====================
class LLMDescriptionTester:
    """测试 LLM Description 生成功能"""
    
    @staticmethod
    def generate_and_display_descriptions(engineer: DeepFeatureEngineer, df_processed: pd.DataFrame, symbol: str, num_samples: int = 3) -> List[str]:
        """
        生成并显示 LLM 描述
        
        Args:
            engineer: DeepFeatureEngineer 实例
            df_processed: 处理后的数据框
            symbol: 股票符号
            num_samples: 要生成的样本数量
        
        Returns:
            list: 生成的 LLM 描述列表
        """
        descriptions = []
        
        if df_processed.empty or len(df_processed) == 0:
            print(f"  ❌ 数据为空，无法生成 LLM 描述")
            return descriptions
        
        # 选择样本行：首行、中间行、末行
        sample_indices = []
        if len(df_processed) >= num_samples:
            step = len(df_processed) // num_samples
            sample_indices = [i * step for i in range(num_samples)]
        else:
            sample_indices = list(range(len(df_processed)))
        
        print(f"\n  📝 生成 {len(sample_indices)} 个 LLM 描述样本...")
        
        for idx, sample_idx in enumerate(sample_indices):
            try:
                row = df_processed.iloc[sample_idx]
                description = engineer.generate_llm_description(symbol, row)
                descriptions.append(description)
                print(f"  ✅ 样本 {idx+1}/{len(sample_indices)} 生成成功")
            except Exception as e:
                print(f"  ❌ 样本 {idx+1} 生成失败: {str(e)}")
        
        return descriptions
    
    @staticmethod
    def print_llm_descriptions(descriptions: List[str], symbol: str):
        """打印生成的 LLM 描述"""
        print("\n" + "="*80)
        print(f"🤖 LLM Description 生成结果 ({symbol})")
        print("="*80)
        
        for idx, desc in enumerate(descriptions, 1):
            print(f"\n{'='*80}")
            print(f"📌 样本 {idx}/{len(descriptions)}")
            print(f"{'='*80}")
            print(desc)
        
        print("\n" + "="*80 + "\n")
    
    @staticmethod
    def save_llm_descriptions_to_report(descriptions: List[str], symbol: str, output_file: str = 'data/llm_descriptions.json'):
        """保存 LLM 描述到 JSON 文件"""
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'num_samples': len(descriptions),
            'descriptions': descriptions
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"  ✅ LLM 描述已保存至 {output_file}")
        except Exception as e:
            print(f"  ❌ 保存失败: {str(e)}")

# ==================== 主测试函数 ====================
async def run_comprehensive_test():
    """运行全面的测试套件"""
    
    print(f"🚀 启动全面 Finnhub 测试流程")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试配置：支持多个符号和时间范围
    test_configs = [
        {'symbol': 'NVDA', 'days': 7},
        {'symbol': 'NVDA', 'days': 14},
        {'symbol': 'AAPL', 'days': 7},
        {'symbol': 'TSLA', 'days': 7},
    ]
    
    # 1. 运行多符号批量测试
    print("\n" + "="*60)
    print("PART 1: 多符号/多周期批量测试")
    print("="*60)
    
    tester = MultiSymbolTester(FINNHUB_KEY)
    all_metrics = await tester.run_batch_tests(test_configs)
    
    # 2. 性能优化测试 (使用 NVDA 数据)
    print("\n" + "="*60)
    print("PART 2: 特征计算性能优化")
    print("="*60)
    
    bridge = FinnhubBridge(FINNHUB_KEY)
    engineer = DeepFeatureEngineer(tar_path=None)
    
    df_raw = bridge.fetch_recent_data('NVDA', days=7)
    if df_raw is not None and not df_raw.empty:
        df_processed, perf_metrics = OptimizedFeatureCalculator.calculate_with_profiling(engineer, df_raw)
        OptimizedFeatureCalculator.print_performance_report(perf_metrics, 'NVDA')
        
        # 3. LLM Description 生成测试
        print("\n" + "="*60)
        print("PART 3: LLM Description 生成测试")
        print("="*60)
        
        llm_descriptions = LLMDescriptionTester.generate_and_display_descriptions(engineer, df_processed, 'NVDA', num_samples=3)
        
        if llm_descriptions:
            LLMDescriptionTester.print_llm_descriptions(llm_descriptions, 'NVDA')
            LLMDescriptionTester.save_llm_descriptions_to_report(llm_descriptions, 'NVDA')
        
        # 4. 生成综合报告
        print("\n" + "="*60)
        print("PART 4: 综合测试总结")
        print("="*60)
        
        summary = {
            'test_timestamp': datetime.now().isoformat(),
            'total_symbols_tested': len(all_metrics),
            'quality_metrics': all_metrics,
            'performance_metrics': perf_metrics,
            'success_rate': (len([m for m in all_metrics if m['processed_rows'] > 0]) / len(all_metrics) * 100) if all_metrics else 0,
            'llm_description_samples': len(llm_descriptions),
        }
        
        print(f"\n✅ 测试完成")
        print(f"   - 测试符号数: {summary['total_symbols_tested']}")
        print(f"   - 成功率: {summary['success_rate']:.1f}%")
        print(f"   - 总耗时: {perf_metrics['total_time']:.2f}s")
        print(f"   - LLM 描述生成: {summary['llm_description_samples']} 个样本")
        
        # 保存综合报告
        os.makedirs('data', exist_ok=True)
        with open('data/comprehensive_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n📁 完整报告已保存至 data/comprehensive_test_report.json")
    else:
        print("❌ 无法获取数据，测试中止")

if __name__ == "__main__":
    if not FINNHUB_KEY:
        print("WARNING: FINNHUB_API_KEY environment variable not set.")
    else:
        asyncio.run(run_comprehensive_test())