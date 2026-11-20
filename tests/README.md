# tests/ – pytest

Phụ trách: Minh

Test cho `producer/` (làm giàu dữ liệu, kịch bản, replay ra file), `functions/fraud_alert/` (định dạng, gộp, chặn lặp, HTTP) và `analysis/evaluate_rules.py`. Không cần Kafka, Azure hay file Parquet, nên chạy được trên CI. `conftest.py` thêm các thư mục đó vào đường dẫn import.

```powershell
.venv\Scripts\python -m pytest
# Linux: .venv/bin/python -m pytest
```
