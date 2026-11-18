# scripts/ – Script tiện ích

Phụ trách: Minh, Sơn

Script chạy một lần hoặc chạy tay.

| Script | Làm gì |
|---|---|
| `prepare_data.py` | Tải dữ liệu REES46, chuyển sang Parquet (xem `data/README.md`) |
| `fill_env.py` | Điền thông tin kết nối Event Hubs vào `.env` bằng quyền `az login` của chính bạn |
| `benchmark_storage.py` | So sánh dung lượng và thời gian truy vấn DuckDB trên cùng event set ở CSV.gz, JSON.gz và Parquet |

## benchmark_storage.py

Chạy từ thư mục gốc repo sau khi đã tải và xử lý dữ liệu tháng 11:

```powershell
.venv\Scripts\python scripts/benchmark_storage.py --input data/processed/2019-Nov.parquet --output data/benchmark/2019-Nov --runs 5 --threads 4
# Linux: .venv/bin/python scripts/benchmark_storage.py --input data/processed/2019-Nov.parquet --output data/benchmark/2019-Nov --runs 5 --threads 4
```

Script tạo các bản CSV.gz, JSON.gz và Parquet Zstandard trong `data/benchmark/`; dữ liệu và kết quả không commit lên Git. Script kiểm tra các số tổng hợp tương ứng phải giống nhau ở cả định dạng. Kết quả JSON ghi kích thước file và median thời gian đọc sau một lượt warm-up. Nếu đã tạo đủ ba file so sánh, thêm `--reuse` để chỉ chạy lại phép đo mà không tạo lại chúng.

## fill_env.py

Cần: Azure CLI, đã `az login` bằng mail trường, hạ tầng đã `apply`.

```powershell
.venv\Scripts\python scripts\fill_env.py           # producer gửi lên Event Hubs
.venv\Scripts\python scripts\fill_env.py --local   # quay về Kafka local
# Linux: .venv/bin/python scripts/fill_env.py
```

- Chỉ sửa các dòng cần thiết trong `.env`, giữ nguyên phần còn lại. Chưa có `.env` thì tạo từ `.env.example`.
- Lấy connection string của policy `producer-send` (chỉ có quyền gửi). Không gửi secret qua chat.
- Sau mỗi lần `destroy` / `apply` Event Hubs, key đổi: chạy lại script.
