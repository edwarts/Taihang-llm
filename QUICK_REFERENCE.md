# Quick Reference: Output File Consolidation

## In One Sentence
**Pipeline now generates BOTH individual symbol files AND automatically merges them into one consolidated training file.**

## Typical Output

```
Input:  python src/pipeline_main_cta_structure.py
Output:
  ✓ deepseek_r1_input_prompts_AAPL_5m_10y.jsonl         (5,200 records)
  ✓ deepseek_r1_input_prompts_MSFT_5m_10y.jsonl        (4,800 records)
  ✓ deepseek_r1_input_prompts_NVDA_5m_10y.jsonl        (5,100 records)
  ✓ deepseek_r1_input_prompts_CONSOLIDATED_33symbols_5m_10y.jsonl  (150,000+ records)
```

## Common Commands

| Task | Command |
|------|---------|
| Process all 33 symbols | `python src/pipeline_main_cta_structure.py` |
| Single symbol | `python src/pipeline_main_cta_structure.py -s AAPL` |
| Specific symbols | `python src/pipeline_main_cta_structure.py -s AAPL -s MSFT -s NVDA` |
| Different timeframe | `python src/pipeline_main_cta_structure.py -w 1m` |
| More history | `python src/pipeline_main_cta_structure.py -y 15` |
| Custom location | `python src/pipeline_main_cta_structure.py --history-dir /custom/path` |

## Consolidated File Naming

| Scenario | Filename Pattern |
|----------|------------------|
| 1 symbol | `_CONSOLIDATED_AAPL_5m_10y.jsonl` |
| 3 symbols | `_CONSOLIDATED_3symbols_5m_10y.jsonl` |
| 33 symbols | `_CONSOLIDATED_33symbols_5m_10y.jsonl` |

## What You Get

**Individual Files:**
- 1 per symbol processed
- Contains only that symbol's patterns
- Good for targeted analysis

**Consolidated File:**
- Combines ALL successful symbols
- Ready for batch API upload
- Enables efficient training

## Key Benefits

✅ **No Manual Work** - Consolidation is automatic
✅ **Both Outputs** - Choose individual or consolidated as needed
✅ **Smart Naming** - Filename tells you what's inside
✅ **Error Resilient** - Failed symbols don't stop consolidation
✅ **Scalable** - Works with any number of symbols

## File Merging Logic

```
Process Symbol 1 → [Individual File] + [In Memory]
Process Symbol 2 → [Individual File] + [In Memory]
Process Symbol 3 → [Individual File] + [In Memory]
                        ↓
                  [Merge in Memory]
                        ↓
                  [Write Consolidated File]
```

## Next Steps

1. **Run pipeline:** `python src/pipeline_main_cta_structure.py`
2. **Check output:** Look for both individual and consolidated files
3. **Upload consolidated:** Use for batch training with DeepSeek API
4. **Analyze individual:** Compare patterns across symbols

## Example Output (Partial)

```
======================================================================
[START] CTA Pipeline - Main Structure
======================================================================
[1/3] Processing AAPL...
[SUCCESS] Generated 5,200 prompts -> deepseek_r1_input_prompts_AAPL_5m_10y.jsonl

[2/3] Processing MSFT...
[SUCCESS] Generated 4,800 prompts -> deepseek_r1_input_prompts_MSFT_5m_10y.jsonl

[3/3] Processing NVDA...
[SUCCESS] Generated 5,100 prompts -> deepseek_r1_input_prompts_NVDA_5m_10y.jsonl

[INFO] Merging output files into consolidated training dataset...
[SUCCESS] Consolidated file created: deepseek_r1_input_prompts_CONSOLIDATED_3symbols_5m_10y.jsonl
[INFO] Total records in consolidated file: 15,100

======================================================================
[SUMMARY] CTA Pipeline Execution Report
======================================================================
[RESULT] Successful: 3/3
[RESULT] Failed: 0/3
[SUCCESS] Processed symbols: AAPL, MSFT, NVDA
======================================================================
```

## Why This Matters

**Before:** Manual consolidation step
```
AAPL.jsonl → consolidate → merged.jsonl
MSFT.jsonl → (user action) ↓
NVDA.jsonl →
```

**Now:** Automatic consolidation
```
AAPL.jsonl → \
MSFT.jsonl → → consolidated.jsonl
NVDA.jsonl → /  (automatic)
```

## FAQ

**Q: Do I get both individual and consolidated files?**
A: Yes! Individual files for each symbol, plus one consolidated file with all records.

**Q: Can I process just a few symbols?**
A: Absolutely. Use `-s SYMBOL` or `--symbol SYMBOL` parameter.

**Q: What if one symbol fails?**
A: Other symbols still generate individual files. Consolidated file includes only successful symbols.

**Q: How large is the consolidated file?**
A: Approximately sum of all individual files (33 symbols ≈ 800 MB).

**Q: Do I need to manually merge files?**
A: No! It's automatic. Just run the pipeline and get both outputs.

## Files Modified

- ✅ `src/pipeline_main_cta_structure.py` (Added consolidation logic)

## Documentation Created

- 📄 `CONSOLIDATION_FEATURE.md` (Detailed feature description)
- 📄 `USAGE_GUIDE.md` (Complete user guide)
- 📄 `IMPLEMENTATION_SUMMARY.md` (Technical details)
- 📄 `QUICK_REFERENCE.md` (This file)

## Status

✅ **Complete & Ready to Use**

The pipeline automatically consolidates output files. No configuration needed.
Simply run the pipeline and get both individual symbol files and a consolidated training dataset.
