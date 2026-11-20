# scripts/ – Script tiện ích

Phụ trách: Minh, Sơn

Script chạy một lần hoặc chạy tay.

| Script | Làm gì |
|---|---|
| `prepare_data.py` | Tải dữ liệu REES46, chuyển sang Parquet (xem `data/README.md`) |
| `fill_env.py` | Điền thông tin kết nối Event Hubs vào `.env` bằng quyền `az login` của chính bạn |
| `benchmark_storage.py` | So sánh dung lượng và thời gian truy vấn DuckDB trên cùng event set ở CSV.gz, JSON.gz và Parquet |
| `bench_producer.py` | Đo tốc độ ghi của producer ở nhiều mức `--rate` (Kafka local hoặc Event Hubs), in bảng. Kết quả: `docs/producer-throughput.md` |
| `bench_consumer.py` | Đo tốc độ đọc của một consumer trên topic `events` |
| `bench_batch.py` | Phía laptop của phép so laptop / cloud: tổng hợp cả tháng 11 bằng DuckDB. Phía cloud: `sql/bench_monthly_aggregate.sql` trên Synapse serverless |

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

## bench_producer.py, bench_consumer.py

Đích lấy từ `.env` giống producer (`fill_env.py` / `fill_env.py --local`). Chỉ chạy được trên Linux / WSL (dừng từng lần chạy bằng SIGINT).

```powershell
.venv\Scripts\python scripts\bench_producer.py                          # 500, 1,000, 1,500, 2,000, tối đa; 60 s x 3 lần
.venv\Scripts\python scripts\bench_consumer.py --limit 300000 --repeat 3 # đọc lại những gì đang có trong topic
# Linux: .venv/bin/python scripts/bench_producer.py ; .venv/bin/python scripts/bench_consumer.py
```

Trên Event Hubs, key của producer chỉ có quyền gửi. Để đo đọc, đặt `EVENTHUBS_LISTEN_CONNECTION_STRING` trong `.env` bằng key `asa-listen`, không commit:

```powershell
az eventhubs eventhub authorization-rule keys list -g rg-megasale-dev --namespace-name evhns-megasale-dev --eventhub-name events --name asa-listen --query primaryConnectionString -o tsv
```

## bench_batch.py

Cùng một phép tổng hợp (theo ngày × loại event: số event, số user khác nhau, doanh thu) trên `data/processed/2019-Nov.parquet`, một lượt warm-up rồi đo `--repeat` lượt:

```powershell
.venv\Scripts\python scripts\bench_batch.py --threads 4
# Linux: .venv/bin/python scripts/bench_batch.py --threads 4
```

Phía cloud: upload đúng file đó lên `lake/benchmark/rees46/2019-Nov.parquet`, chạy `sql/bench_monthly_aggregate.sql` trong database serverless có data source `MegasaleLake`, đọc thời gian và dung lượng quét trong Synapse Studio (Monitor → SQL requests). Kết quả hai phía phải giống nhau: 89 dòng, 67,501,979 event, doanh thu 275,194,890.50 USD.
