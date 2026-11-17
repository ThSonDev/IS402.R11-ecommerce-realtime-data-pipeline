# Thí nghiệm tối ưu lưu trữ

## So sánh CSV, JSON và Parquet

Phép đo dùng toàn bộ dữ liệu REES46 tháng 11/2019 (`data/processed/2019-Nov.parquet`, 67,501,979 dòng). `scripts/benchmark_storage.py` tạo các định dạng khác từ đúng Parquet nguồn, kiểm tra số dòng, session, purchase và tổng giá purchase trước khi tính thời gian đọc. Mỗi query tổng hợp được chạy một lượt warm-up và ba lượt đo bằng DuckDB 2.0.0, 4 thread, trên Windows / Intel Core i3-1220P / RAM 15.7 GiB / Python 3.12.10.

| File được đọc | Dung lượng byte | Dung lượng GB | Dung lượng GiB | Median thời gian query |
|---|---:|---:|---:|---:|
| Parquet nguồn (`data/processed/2019-Nov.parquet`) | 1,191,810,334 | 1.192 | 1.110 | 11.83 giây |
| CSV gzip | 2,855,284,937 | 2.855 | 2.660 | 60.49 giây |
| JSON Lines gzip | 3,299,104,279 | 3.299 | 3.072 | 58.57 giây |
| Parquet Zstandard chuyển đổi | 1,191,758,944 | 1.192 | 1.110 | 31.63 giây |

Cả bốn bản cho kết quả giống nhau: 67,501,979 dòng, 13,776,050 `user_session` khác nhau, 916,939 purchase và tổng `price` của purchase 275,194,890.50. Cột `price` giữ đơn vị và độ chính xác của REES46, không quy đổi sang VND.

Parquet Zstandard chuyển đổi chiếm khoảng 58% ít dung lượng hơn CSV.gz và query tổng hợp nhanh hơn khoảng 1.9 lần trong phép đo này. Query đọc Parquet nguồn nhanh hơn file Parquet chuyển đổi dù dung lượng gần như bằng nhau; vì vậy thời gian chịu ảnh hưởng của bố cục file, row group và cache hệ điều hành. Không xem đây là thời gian Synapse hay kết luận chỉ do codec.

## Lọc theo phân vùng trên Synapse

Trên lake hiện có 169,736 bản ghi thô từ nhiều lượt chạy/test. Truy vấn đếm toàn bộ `raw_archive` quét 47 MB. Lọc đúng đường dẫn năm/tháng/ngày/giờ `2026/11/15/09` trên `silver.events_raw` trả 108,735 dòng và quét 16 MB. Đây là lượt producer có log gửi 108,735 event; 108,735 `event_id` khác nhau, nên số dòng của view `silver.events` trong phân vùng đó cũng là 108,735.

Sau khi tạo database-scoped data source `MegasaleLake` bằng file `warehouse/10_external.sql` (issue #63), truy vấn phân vùng tương ứng là:

```sql
SELECT COUNT_BIG(*) AS raw_event_count
FROM OPENROWSET(
    BULK 'raw_archive/*/*/*/*/*.parquet',
    DATA_SOURCE = 'MegasaleLake',
    FORMAT = 'PARQUET'
) AS raw
WHERE TRY_CONVERT(int, raw.filepath(1)) = 2026
  AND TRY_CONVERT(int, raw.filepath(2)) = 11
  AND TRY_CONVERT(int, raw.filepath(3)) = 15
  AND TRY_CONVERT(int, raw.filepath(4)) = 9;
```

Phân vùng giờ đó có 57 file Parquet, tổng 30,865,512 byte (29.44 MiB), trung bình khoảng 0.54 MiB/file. Query lọc phân vùng quét ít hơn query toàn lake trong lần đo này; lọc theo `partition_year`, `partition_month`, `partition_day` và `partition_hour` giúp giới hạn số file mở.

## Gộp file nhỏ bằng CETAS

Ngày 18/11/2026, dùng Synapse serverless CETAS để xuất partition `2026/11/15/09` từ `silver.events_raw` sang một prefix tạm riêng trong `lake/benchmark/`. Nguồn có 57 file Parquet, tổng 30,865,512 byte. Kết quả CETAS:

| Đo lường | Partition nguồn | CETAS tạm |
|---|---:|---:|
| Số file Parquet | 57 | 16 |
| Tổng dung lượng file | 30,865,512 byte | 11,054,823 byte |
| `COUNT_BIG(*)` | 108,735 | 108,735 |
| `COUNT(DISTINCT event_id)` | 108,735 | 108,735 |
| View / cart / purchase | 104,532 / 1,899 / 2,304 | 104,532 / 1,899 / 2,304 |
| GMV purchase | 19,812,462,885 VND | 19,812,462,885 VND |
| Data scanned khi chạy riêng truy vấn đếm | 4 MB | 2 MB |

Trong lần chạy này CETAS giảm dung lượng 64.2% và số file Parquet 71.9%. CETAS vẫn sinh 16 file do xuất song song, không tạo một file duy nhất. Lệnh CETAS đọc 35 MB và ghi 12 MB theo thống kê Synapse; các truy vấn đếm nguồn/đích được chạy riêng để so lượng scan. Phép đo cho thấy lợi ích trên partition này, không đảm bảo mọi partition sẽ có cùng tỉ lệ.

Mẫu lệnh (mỗi lần chạy phải dùng tên bảng và `LOCATION` mới, rỗng):

```sql
CREATE EXTERNAL FILE FORMAT [ParquetBenchmark]
WITH (FORMAT_TYPE = PARQUET);

CREATE EXTERNAL TABLE [dbo].[EventsCompacted]
WITH (
    LOCATION = 'benchmark/<unique-run>/',
    DATA_SOURCE = [MegasaleLake],
    FILE_FORMAT = [ParquetBenchmark]
)
AS
SELECT *
FROM [silver].[events_raw]
WHERE partition_year = 2026
  AND partition_month = 11
  AND partition_day = 15
  AND partition_hour = 9;
```

Sau khi kiểm tra row count/aggregates và đo dung lượng/scan, xóa external table/file format tạm rồi xóa đúng prefix đã tạo. Lượt thử này đã được dọn: prefix CETAS còn 0 object, còn 57 file nguồn trong `raw_archive`. Không ghi vào hay xóa dữ liệu `raw_archive`.

## Cách lặp lại phép đo local

Theo hướng dẫn trong `data/README.md`, tải và chuẩn bị dữ liệu REES46; sau đó chạy:

```powershell
.venv\Scripts\python scripts/benchmark_storage.py --input data/processed/2019-Nov.parquet --output data/benchmark/2019-Nov --runs 5 --threads 4
```

Kết quả và bản chuyển đổi nằm dưới `data/` (Git ignored), không đưa dữ liệu vào commit.
