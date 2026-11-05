# Reference data cho Stream Analytics

Git là nguồn gốc; Terraform upload lên container `reference` của data lake (`infra/storage.tf`).

## `price_list.csv`

Giá tham chiếu cho luật 3 (sai giá), mỗi sản phẩm một dòng. Cột `product_id`, `ref_price_vnd`, sắp theo `product_id`.

Cách tính: từ dữ liệu REES46 tháng 11/2019, bỏ dòng trùng (cùng các trường producer dùng để dedup) và bỏ giá 0 (chỉ có ở view, cart). Mỗi giá USD đổi sang VND theo tỷ giá cố định `25,850` VND/USD như producer, rồi lấy trung vị theo `product_id`. Cả hai bước làm tròn kiểu ties-to-even, giống `round()` trong `producer/enrich.py`.

Đây là **giá tham chiếu ước tính từ dữ liệu**, không phải giá niêm yết chính thức của người bán. Nguồn và license REES46: [data/README.md](../../data/README.md).

Tạo lại file (cần `data/processed/2019-Nov.parquet`, xem [data/README.md](../../data/README.md)), chạy từ thư mục gốc repo:

```powershell
.venv\Scripts\python scripts\create_price_list.py
# Linux: .venv/bin/python scripts/create_price_list.py
```

Tùy chọn `--input`, `--output` để đổi đường dẫn.

## `provinces.csv`

34 tỉnh/thành, dùng khi làm giàu dữ liệu, cho bản đồ và RLS theo miền. Nguồn dân số: xem `producer/README.md`.
