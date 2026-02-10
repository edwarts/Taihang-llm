# Output File Consolidation Feature

## Overview
Enhanced `src/pipeline_main_cta_structure.py` with automatic output file consolidation. Now generates both individual symbol files AND a consolidated training dataset.

## How It Works

### Before (Individual Files Only)
When processing multiple symbols, pipeline created separate output files:
```
deepseek_r1_input_prompts_AAPL_5m_10y.jsonl     (5,000 records)
deepseek_r1_input_prompts_MSFT_5m_10y.jsonl    (4,200 records)
deepseek_r1_input_prompts_NVDA_5m_10y.jsonl    (6,300 records)
```

### Now (Individual + Consolidated)
Pipeline creates all individual files PLUS a consolidated master file:
```
deepseek_r1_input_prompts_AAPL_5m_10y.jsonl        (5,000 records)
deepseek_r1_input_prompts_MSFT_5m_10y.jsonl       (4,200 records)
deepseek_r1_input_prompts_NVDA_5m_10y.jsonl       (6,300 records)

deepseek_r1_input_prompts_CONSOLIDATED_3symbols_5m_10y.jsonl  (15,500 records)
```

## File Naming Convention

### Single Symbol Processing
```
deepseek_r1_input_prompts_CONSOLIDATED_AAPL_5m_15y.jsonl
```

### Multi-Symbol Processing
```
deepseek_r1_input_prompts_CONSOLIDATED_5symbols_5m_10y.jsonl
```

Where:
- `CONSOLIDATED`: Marks this as a merged file
- `5symbols`: Number of successfully processed symbols (or symbol name if single)
- `5m`: Timeframe window
- `10y`: Years of historical data used

## Implementation Details

### Data Structure
Each consolidated record maintains the same structure as individual records:
```json
{
  "custom_id": "AAPL_timestamp",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "deepseek-reasoner",
    "messages": [
      {"role": "system", "content": "You are a specialized trading AI."},
      {"role": "user", "content": "prompt_content"}
    ]
  }
}
```

### Processing Flow
1. Process each symbol individually
   - Generate feature engineering
   - Mine training samples
   - Save individual JSONL file
   - Store records in memory

2. After all symbols processed successfully
   - Collect all records from successful symbols
   - Merge into single consolidated file
   - Write to disk with timestamp

3. Output summary showing:
   - Individual file names and record counts
   - Consolidated file name and total record count
   - Success/failure breakdown

## Usage Examples

### Process All Symbols (Auto-Consolidate)
```powershell
python src/pipeline_main_cta_structure.py
# Output:
# deepseek_r1_input_prompts_AAPL_5m_10y.jsonl
# deepseek_r1_input_prompts_MSFT_5m_10y.jsonl
# ...
# deepseek_r1_input_prompts_CONSOLIDATED_33symbols_5m_10y.jsonl
```

### Process Specific Symbols
```powershell
python src/pipeline_main_cta_structure.py --symbol AAPL --symbol MSFT --symbol NVDA
# Output:
# deepseek_r1_input_prompts_AAPL_5m_10y.jsonl
# deepseek_r1_input_prompts_MSFT_5m_10y.jsonl
# deepseek_r1_input_prompts_NVDA_5m_10y.jsonl
# deepseek_r1_input_prompts_CONSOLIDATED_3symbols_5m_10y.jsonl
```

### Process Single Symbol (Still Creates Consolidated)
```powershell
python src/pipeline_main_cta_structure.py --symbol AAPL --years 15 --window 5m
# Output:
# deepseek_r1_input_prompts_AAPL_5m_15y.jsonl
# deepseek_r1_input_prompts_CONSOLIDATED_AAPL_5m_15y.jsonl
```

## Benefits

1. **Flexibility**: Keep individual files for targeted analysis while having complete dataset
2. **Training Efficiency**: Use consolidated file for batch training without manual merging
3. **Auditability**: Track which symbols contributed to consolidated file via filename
4. **Simplicity**: No additional steps needed - automatic consolidation after processing
5. **Scalability**: Works seamlessly with 1, 10, or 33 symbols

## Technical Changes

### Modified Function: `main_pipeline()`
- **Before**: Appended symbol string to `successful` list
- **After**: Appends tuple `(symbol, filename, records)` to track both metadata and data
- Automatically consolidates after loop completes
- Generates appropriately named consolidated file

### New Consolidation Block
```python
if successful:
    consolidated_records = []
    for symbol, output_filename, output_records in successful:
        consolidated_records.extend(output_records)
    
    # Write consolidated file
    consolidated_filename = f"deepseek_r1_input_prompts_CONSOLIDATED_{len(successful)}symbols_{window}_{years}y.jsonl"
    with open(consolidated_filename, 'w', encoding='utf-8') as f:
        for record in consolidated_records:
            f.write(json.dumps(record) + "\n")
```

## File Size Considerations

Consolidated file size = sum of all individual file sizes

Example (33 symbols with 5m, 10y data):
- Individual files: ~200-500 MB total
- Consolidated file: ~200-500 MB additional (deduplicated references only)

## Backward Compatibility

✅ Fully backward compatible
- Individual files generated exactly as before
- No changes to record structure or format
- Consolidation happens automatically after successful processing
- Failures don't prevent individual file generation

## Error Handling

- If any symbol fails: Only successful symbols are included in consolidated file
- Summary report clearly shows which symbols contributed
- Individual failed symbol files are not included in consolidation
- Consolidated file is only created if at least one symbol succeeds

## Next Steps

After consolidation completes, you can:
1. **For Model Training**: Use consolidated file with batch API
2. **For Debugging**: Compare individual vs consolidated counts
3. **For Archiving**: Store consolidated file while keeping selectively important individual files
