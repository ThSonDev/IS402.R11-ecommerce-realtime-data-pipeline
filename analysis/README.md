# analysis/ – EDA và đánh giá

Phụ trách: Minh, Thắng

- `eda.py`: EDA cơ bản trên một tháng dữ liệu.
- `evaluate_rules.py`: precision / recall của 4 luật, so `alerts` của ASA (xuất từ `dbo.alerts` ra CSV / JSON / Parquet) với ground truth producer ghi khi chạy `--scenarios`. Luật 1–3 tính theo đối tượng (user, thiết bị, sản phẩm); luật 4 tính theo cảnh báo và theo khoảng sự cố (`--incident` thêm khoảng sự cố thật, ví dụ đoạn mất purchase 14–17/11/2019 khi replay đoạn đó).

```powershell
.venv\Scripts\python analysis\eda.py
# Linux: .venv/bin/python analysis/eda.py
```

```powershell
.venv\Scripts\python analysis\evaluate_rules.py --alerts alerts.csv --scenario-log data\scenario_logs\<run>.json
# Linux: .venv/bin/python analysis/evaluate_rules.py --alerts alerts.csv --scenario-log data/scenario_logs/<run>.json
```
