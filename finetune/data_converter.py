"""
数据转换脚本：将 reasoning JSONL 格式转换为 LlamaFactory 所需格式
支持 Qwen3 思考模式 (<think>...</think>)

运行环境: WSL2
项目挂载点: /mnt/c/code-base/Taihang-llm/
"""
import json
import os
import re
import argparse
from pathlib import Path

# ====================================================================
# WSL2 路径映射
# ====================================================================
# Windows: C:\code-base\Taihang-llm\
# WSL2:    /mnt/c/code-base/Taihang-llm/
PROJECT_ROOT = "/mnt/c/code-base/Taihang-llm"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
FINETUNE_DIR = os.path.join(PROJECT_ROOT, "finetune")
FINETUNE_DATA_DIR = os.path.join(DATA_DIR, "finetune")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")


def extract_think_and_answer(reasoning_text):
    """
    从 reasoning 文本中分离 <think> 思考过程和最终 JSON 答案。
    
    DeepSeek R1 的 reasoning 格式通常是：
      思考过程文本...
      </think>
      ```json
      { ... }
      ```
    
    转换为 Qwen3 格式：
      <think>
      思考过程...
      </think>
      ```json
      { ... }
      ```
    """
    if not reasoning_text:
        return reasoning_text
    
    # 检查是否已有 <think> 标签
    if '<think>' in reasoning_text:
        return reasoning_text
    
    # 查找 </think> 标签位置
    think_end = reasoning_text.find('</think>')
    
    if think_end != -1:
        # 已有 </think>，提取思考部分并包装
        thinking_part = reasoning_text[:think_end].strip()
        answer_part = reasoning_text[think_end + len('</think>'):].strip()
        return f"<think>\n{thinking_part}\n</think>\n\n{answer_part}"
    
    # 没有任何 think 标签：尝试分离思考和 JSON 答案
    # 查找最后一个 ```json 代码块作为答案
    json_pattern = r'```json\s*\n(.*?)```'
    json_matches = list(re.finditer(json_pattern, reasoning_text, re.DOTALL))
    
    if json_matches:
        last_json_match = json_matches[-1]
        thinking_part = reasoning_text[:last_json_match.start()].strip()
        answer_part = reasoning_text[last_json_match.start():].strip()
        return f"<think>\n{thinking_part}\n</think>\n\n{answer_part}"
    
    # 无法分离：将全部内容作为思考过程
    return f"<think>\n{reasoning_text}\n</think>"


def convert_reasoning_to_llamafactory(input_file, output_file, use_think_mode=True, max_samples=None):
    """
    转换 reasoning 数据为 LlamaFactory Alpaca 格式
    
    输入格式（DeepSeek R1 reasoning JSONL）：
    {
        "symbol": "AAPL",
        "custom_id": "AAPL_2017-01-06 14:45:00",
        "prompt": "...",           # 市场数据 + 分析任务
        "reasoning": "...",        # 思考过程 + JSON 答案
        "window": "5m",
        "years": 15
    }
    
    输出格式（LlamaFactory Alpaca JSON）：
    {
        "instruction": "...",      # 系统级任务描述
        "input": "...",            # 市场数据
        "output": "...",           # 思考过程 + JSON (Qwen3 格式)
        "system": "..."            # system prompt
    }
    
    Args:
        max_samples: 最大样本数限制，None 表示不限制
    """
    converted_data = []
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'with_think': 0,
        'without_think': 0
    }
    
    if max_samples:
        print(f"  [LIMIT] 最大样本数: {max_samples}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # 检查样本数限制
            if max_samples and stats['success'] >= max_samples:
                print(f"  [LIMIT] 已达到 {max_samples} 条上限，停止读取")
                break
            
            stats['total'] += 1
            try:
                data = json.loads(line.strip())
                
                # 构造 instruction
                instruction = (
                    "You are a master Quant Trader analyzing market data to identify causality "
                    "behind price movements. Analyze the provided market context and explain "
                    "WHY the price moved. Think step by step, then provide your analysis as JSON."
                )
                
                # input 是市场数据
                market_data = data['prompt']
                
                # output: 处理 reasoning，转换为 Qwen3 think 格式
                raw_reasoning = data['reasoning']
                
                if use_think_mode:
                    formatted_output = extract_think_and_answer(raw_reasoning)
                    if '<think>' in formatted_output:
                        stats['with_think'] += 1
                    else:
                        stats['without_think'] += 1
                else:
                    formatted_output = raw_reasoning
                
                # 构造 LlamaFactory 格式
                converted_item = {
                    "instruction": instruction,
                    "input": market_data,
                    "output": formatted_output,
                    "system": (
                        "You are a specialized trading AI with deep understanding of "
                        "market microstructure, order flow dynamics, and multi-timeframe analysis. "
                        "Always reason through your analysis step by step before giving conclusions."
                    )
                }
                
                converted_data.append(converted_item)
                stats['success'] += 1
                
            except Exception as e:
                stats['failed'] += 1
                if stats['failed'] <= 5:
                    print(f"  [WARNING] Line {line_num}: {e}")
                continue
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # 保存转换后的数据
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] 转换完成！")
    print(f"  输入: {input_file}")
    print(f"  输出: {output_file}")
    print(f"  总行数: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    if use_think_mode:
        print(f"  带 <think> 标签: {stats['with_think']}")
        print(f"  无 <think> 标签: {stats['without_think']}")
    
    return len(converted_data)


def merge_multiple_files(input_files, output_file, use_think_mode=True, max_samples=None):
    """
    合并多个 reasoning 文件为一个训练集
    
    Args:
        max_samples: 总样本数限制，达到后停止读取
    """
    all_data = []
    file_stats = {}
    
    if max_samples:
        print(f"  [LIMIT] 总样本数限制: {max_samples}")
    
    for input_file in input_files:
        if max_samples and len(all_data) >= max_samples:
            print(f"  [LIMIT] 已达到 {max_samples} 条上限，跳过剩余文件")
            break
        
        if not os.path.exists(input_file):
            print(f"  [WARNING] 文件不存在: {input_file}")
            continue
        
        count = 0
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if max_samples and len(all_data) >= max_samples:
                    break
                try:
                    data = json.loads(line.strip())
                    
                    instruction = (
                        "You are a master Quant Trader analyzing market data to identify causality "
                        "behind price movements. Analyze the provided market context and explain "
                        "WHY the price moved. Think step by step, then provide your analysis as JSON."
                    )
                    
                    raw_reasoning = data['reasoning']
                    if use_think_mode:
                        formatted_output = extract_think_and_answer(raw_reasoning)
                    else:
                        formatted_output = raw_reasoning
                    
                    converted_item = {
                        "instruction": instruction,
                        "input": data['prompt'],
                        "output": formatted_output,
                        "system": (
                            "You are a specialized trading AI with deep understanding of "
                            "market microstructure, order flow dynamics, and multi-timeframe analysis. "
                            "Always reason through your analysis step by step before giving conclusions."
                        )
                    }
                    
                    all_data.append(converted_item)
                    count += 1
                    
                except Exception:
                    continue
        
        file_stats[os.path.basename(input_file)] = count
        print(f"  [{os.path.basename(input_file)}] {count} 条样本")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # 保存合并后的数据
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] 合并完成！")
    print(f"  输入文件数: {len(file_stats)}")
    print(f"  输出: {output_file}")
    print(f"  总样本数: {len(all_data)}")
    
    return len(all_data)


def preview_sample(input_file, index=0, use_think_mode=True):
    """
    预览转换后的样本
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == index:
                data = json.loads(line.strip())
                raw = data['reasoning']
                converted = extract_think_and_answer(raw) if use_think_mode else raw
                
                print("=" * 70)
                print(f"[PREVIEW] Sample #{index} - {data.get('custom_id', 'N/A')}")
                print("=" * 70)
                print(f"\n[INPUT] (前200字):")
                print(data['prompt'][:200] + "...")
                print(f"\n[OUTPUT] (前500字):")
                print(converted[:500] + "...")
                print("=" * 70)
                return
    
    print(f"[ERROR] 索引 {index} 超出文件范围")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="转换 reasoning 数据为 LlamaFactory 格式（支持 Qwen3 思考模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 默认转换 AAPL 文件
  python data_converter.py
  
  # 指定输入输出
  python data_converter.py -i ../data/deepseek_r1_reasoning_AAPL_*.jsonl -o ../data/finetune/aapl.json
  
  # 合并多个文件
  python data_converter.py --merge ../data/deepseek_r1_reasoning_*.jsonl -o ../data/finetune/merged.json
  
  # 限制样本数 (快速验证)
  python data_converter.py --max-samples 50
  
  # 不使用 think 模式
  python data_converter.py --no-think
  
  # 预览转换效果
  python data_converter.py --preview ../data/deepseek_r1_reasoning_AAPL_5m_15y_y2008_2017_2020_2021_2022.jsonl
        """
    )
    parser.add_argument('-i', '--input', type=str, help='输入 reasoning JSONL 文件路径')
    parser.add_argument('-o', '--output', type=str, help='输出 JSON 文件路径')
    parser.add_argument('--merge', nargs='+', help='合并多个文件（提供多个输入路径）')
    parser.add_argument('--max-samples', type=int, default=None,
                        help='最大样本数限制 (如 50, 100, 500)，用于快速测试')
    parser.add_argument('--no-think', action='store_true', help='不使用 Qwen3 think 模式')
    parser.add_argument('--preview', type=str, help='预览某个文件的第一条转换效果')
    
    args = parser.parse_args()
    use_think = not args.no_think
    max_samples = args.max_samples
    
    # 打印路径映射信息
    print(f"[PATH] PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"[PATH] DATA_DIR     = {DATA_DIR}")
    print(f"[PATH] OUTPUT_DIR   = {FINETUNE_DATA_DIR}")
    print()
    
    if args.preview:
        preview_sample(args.preview, use_think_mode=use_think)
    elif args.merge:
        output = args.output or os.path.join(FINETUNE_DATA_DIR, 'trading_reasoning_merged.json')
        print(f"[MODE] 合并模式 | think={use_think} | max_samples={max_samples or '无限制'}")
        merge_multiple_files(args.merge, output, use_think_mode=use_think, max_samples=max_samples)
    elif args.input:
        output = args.output or os.path.join(FINETUNE_DATA_DIR, 'trading_reasoning.json')
        print(f"[MODE] 单文件转换 | think={use_think} | max_samples={max_samples or '无限制'}")
        convert_reasoning_to_llamafactory(args.input, output, use_think_mode=use_think, max_samples=max_samples)
    else:
        # 默认：转换当前 AAPL 文件 (使用 WSL2 绝对路径)
        input_file = os.path.join(DATA_DIR, 'deepseek_r1_reasoning_AAPL_5m_15y_y2008_2017_2020_2021_2022.jsonl')
        output_file = os.path.join(FINETUNE_DATA_DIR, 'trading_reasoning_aapl.json')
        
        print(f"[MODE] 默认模式 | think={use_think} | max_samples={max_samples or '无限制'}")
        print(f"[INFO] Qwen3 思考模式: {'启用 (<think>...</think>)' if use_think else '禁用'}")
        print(f"[INFO] 输入: {input_file}")
        print(f"[INFO] 输出: {output_file}")
        
        os.makedirs(FINETUNE_DATA_DIR, exist_ok=True)
        
        if not os.path.exists(input_file):
            print(f"[ERROR] 文件不存在: {input_file}")
            print(f"[HINT] 请确认 WSL2 挂载路径正确，或使用 -i 指定输入文件路径")
            exit(1)
        
        convert_reasoning_to_llamafactory(input_file, output_file, use_think_mode=use_think, max_samples=max_samples)
        
        # 预览第一条
        print("\n" + "=" * 70)
        preview_sample(input_file, use_think_mode=use_think)
