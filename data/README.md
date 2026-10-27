# data/

Dữ liệu không commit lên Git (quá lớn). Mỗi người tự tải về máy.

| Thư mục | Nội dung |
|---|---|
| `raw/` | File gốc `2019-Nov.csv.gz` (2.89 GB) |
| `processed/` | `2019-Nov.parquet` (1.19 GB, zstd) – producer và EDA đọc file này |

## Nguồn

REES46 – *eCommerce behavior data from multi category store*: log hành vi thật (view / cart / purchase) của một cửa hàng online đa ngành, thu thập bởi [Open CDP](https://rees46.com/en/open-cdp). Đồ án dùng tháng **11/2019**.

- Kaggle: https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store
- Link tải trực tiếp: https://data.rees46.com/datasets/marketplace/2019-Nov.csv.gz
- Dùng miễn phí, **bắt buộc ghi nguồn** (link Kaggle + [REES46](https://rees46.com)).

## Cách lấy dữ liệu

Yêu cầu Python 3.12.8 trở lên (`python --version`). Chạy từ thư mục gốc của repo:

```powershell
python -m venv .venv
# Linux: python3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# Linux: .venv/bin/python -m pip install -r requirements.txt
.venv\Scripts\python scripts\prepare_data.py
# Linux: .venv/bin/python scripts/prepare_data.py
```

Script tự tải file vào `raw/` (bỏ qua nếu đã có), rồi chuyển sang Parquet vào `processed/` (~1 phút). Cần ~5 GB ổ trống.

Kiểm tra nhanh:

```powershell
.venv\Scripts\python analysis\eda.py
# Linux: .venv/bin/python analysis/eda.py
```
