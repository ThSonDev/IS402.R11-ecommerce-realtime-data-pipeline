# Stream Analytics reference data

## `price_list.csv`

`price_list.csv` contains one reference price per product, calculated from deduplicated events in REES46's November 2019 dataset, matching the producer's deduplication fields. For each `product_id`, it stores the median of positive prices after converting each observed USD price to VND at the fixed `25,850 VND/USD` rate used by the producer. Both conversion and final median use ties-to-even rounding. Zero prices are excluded; they occur only on views and carts and are not useful as reference prices.

This is a data-derived baseline for the price anomaly rule, not an official seller catalog price. Source and license information for REES46 are documented in [data/README.md](../../data/README.md).

Prepare `data/processed/2019-Nov.parquet` using [data/README.md](../../data/README.md), then run from the repository root:

```powershell
.venv\Scripts\python scripts\create_price_list.py
```

The script accepts `--input` and `--output` overrides. The CSV has `product_id` and `list_price_vnd` columns and is sorted by `product_id`.
