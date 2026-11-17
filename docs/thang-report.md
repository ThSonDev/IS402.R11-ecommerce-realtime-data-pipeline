# Xử lý luồng, ETL và tối ưu lưu trữ

## 2.1. Định dạng lưu trữ

Pipeline dùng JSON cho event gửi từ producer vào Event Hubs. JSON dễ kiểm tra và biểu diễn được các trường tùy chọn như `category_code`, `brand` và `voucher_code`. Đổi lại, dữ liệu số và thời gian cần được diễn giải theo contract khi đọc; tên thuộc tính lặp lại trên mỗi event.

CSV được dùng cho reference data nhỏ, gồm `price_list.csv` và `provinces.csv`. CSV tương thích rộng và gọn với bảng phẳng, nhưng không mang schema theo từng cột nên bên đọc phải biết trước thứ tự và kiểu dữ liệu.

Data lake lưu `raw_archive` dạng Parquet. Parquet là định dạng cột, phù hợp với truy vấn phân tích chỉ đọc một phần cột; Synapse serverless hỗ trợ đọc Parquet trực tiếp bằng `OPENROWSET`. ASA chia đường dẫn theo năm/tháng/ngày/giờ (`raw_archive/yyyy/MM/dd/HH`). View `silver.events_raw` đưa các phần của đường dẫn này thành cột để truy vấn có thể lọc theo phân vùng. Lợi ích đo được về dung lượng và tốc độ được trình bày ở mục 3.4.

## 2.2. Xử lý luồng

Producer phát event JSON có `event_time` là thời điểm nghiệp vụ sau khi replay và `sent_time` là thời điểm gửi. Query ASA dùng `TIMESTAMP BY event_time`; nếu không khai báo, ASA mặc định xử lý theo thời điểm event đến input. Vì vậy cửa sổ thời gian KPI dùng thời gian nghiệp vụ thay vì thời gian nhận ở Event Hubs.

KPI nhóm event theo `channel` và `province_code` trong tumbling window một phút. Tumbling window tạo các khoảng liền nhau, không chồng lấn; một event chỉ thuộc một window. Output được gắn `window_end` qua `System.Timestamp()`.

Event có thể đến trễ so với `event_time` hoặc không đúng thứ tự. Cấu hình được đề xuất trong PR #84 đặt late-arrival tolerance 60 giây và out-of-order tolerance 60 giây; policy out-of-order là `Adjust`. Hai ngưỡng cho ASA thời gian chờ event trễ/sai thứ tự trong giới hạn thử nghiệm. Static input của ASA Tools không kiểm chứng được policy cloud; cần thử với Event Hubs.

Cloud test trên baseline `c74ce16` ghi nhận 2,000 event trong bài late-arrival; producer đánh dấu 102 event đến trễ và chúng vẫn xuất hiện trong `raw_archive`. Baseline này dùng tolerance 5/0 giây trước PR #82, nên là kết quả lịch sử chứ không phải kết quả của cấu hình đề xuất trong PR #84. Sau khi #82 merge, Sơn báo cáo bài thử `--late-rate 0.05`: KPI khớp khi so với `raw_archive` theo payload `event_time`, và `DroppedOrAdjustedEvents = 0`. Đây là kết quả được báo cáo từ buổi chạy cloud; tài liệu này không ghi số lượng batch vì chưa có log xác nhận kèm theo. Phép đối chiếu này không tự xác minh việc ghi thành công vào SQL, Power BI hay output `pipeline_latency`; các sink đó cần log cloud riêng. Chỉ số `DroppedOrAdjustedEvents` gộp event bị bỏ và event được điều chỉnh, nên chỉ số 0 cho biết batch đó không có event nào thuộc hai nhóm này.

Đồ án dự kiến phát hiện spike/dip trên chuỗi số đơn theo phút bằng `AnomalyDetection_SpikeAndDip`. ASA yêu cầu chuỗi đầu vào lấy mẫu đều; vì vậy cần tổng hợp theo tumbling window trước khi áp dụng anomaly function. Ngưỡng và kết quả đánh giá từng luật sẽ được cập nhật cùng kết quả các issue #61, #62 và #68; không dùng `is_fraud` hoặc `scenario` làm đầu vào phát hiện vì đây là nhãn đánh giá.

## 3.2. Luồng ETL

1. **Extract:** producer đọc dữ liệu REES46 đã chuẩn bị, loại các bản ghi trùng theo quy trình trong `producer/`, làm giàu event theo `docs/event-schema.md` và gửi JSON đến Event Hubs `events`. Partition key là `user_id`.
2. **Transform thời gian thực:** ASA đọc input `events`, dùng `TIMESTAMP BY event_time`, reference data `price_list` và `provinces`, rồi tính KPI theo cửa sổ một phút. Query cũng chiếu metadata của Event Hubs/ASA dùng để truy vết và tính latency.
3. **Load dữ liệu thô và KPI:** ASA ghi `raw_archive` thành Parquet trong ADLS Gen2 theo đường dẫn ngày/giờ; KPI được cấu hình tới các output lake, Azure SQL và Power BI. `pipeline_latency` là output SQL riêng. Việc ghi SQL/Power BI cần các sink/identity được cấp quyền trước khi chạy job.
4. **Làm sạch và phục vụ lịch sử:** Synapse serverless đọc Parquet qua external data source `MegasaleLake`. `silver.events_raw` ép kiểu và giữ thông tin phân vùng; `silver.events` loại bản ghi thiếu khóa/thời gian hợp lệ và giữ bản nhận mới nhất cho mỗi `event_id`. Cloud test với run ngày 15/11/2026, 09:00 UTC, cho 108,735 dòng thô và 108,735 dòng silver; số này khớp log producer của run. Lớp gold star schema và triển khai SQL tự động thuộc issue #64.

Luồng truy vấn và lệnh kết nối được ghi trong `stream/README.md`, `infra/README.md`, `warehouse/README.md` và `scripts/README.md`. ASA job được giữ ở trạng thái Stopped khi không đo để tránh tính phí theo giờ.

## 3.4. Tối ưu lưu trữ và tốc độ đọc

### So sánh định dạng

Phép đo dùng cùng dữ liệu tháng 11/2019 sau khi `scripts/prepare_data.py` chuyển sang Parquet. `scripts/benchmark_storage.py` tạo CSV.gz, JSON.gz và Parquet Zstandard từ cùng Parquet nguồn, xác nhận số dòng và các tổng hợp khớp nhau, rồi đo median thời gian đọc sau một lượt warm-up bằng DuckDB. Máy đo: Windows, Intel Core i3-1220P, RAM 15.7 GiB, Python 3.12.10, DuckDB 2.0.0, 4 thread; mỗi định dạng được đọc 3 lần.

| Định dạng | Kích thước | Median truy vấn tổng hợp | Ghi chú |
|---|---:|---:|---|
| CSV.gz | 2.86 GB (2.66 GiB) | 60.49 giây | Nén gzip |
| JSON.gz (newline-delimited) | 3.30 GB (3.07 GiB) | 58.57 giây | Nén gzip |
| Parquet Zstandard | 1.19 GB (1.11 GiB) | 31.63 giây | Một file sau chuyển đổi |
| Parquet nguồn | 1.19 GB (1.11 GiB) | 11.83 giây | File `data/processed/2019-Nov.parquet` |

Truy vấn so sánh gồm tổng số dòng, số `user_session` khác nhau, số purchase và tổng `price` của purchase. Cả bốn định dạng cho cùng kết quả: 67,501,979 dòng, 13,776,050 session, 916,939 purchase, tổng `price` purchase 275,194,890.50. `price` trong REES46 là giá gốc của dataset, không phải VND. Parquet Zstandard chuyển đổi nhỏ hơn CSV.gz khoảng 58% và truy vấn tổng hợp median nhanh hơn khoảng 1.9 lần trong lần đo này. Kết quả chỉ đại diện cấu hình DuckDB và máy đo nêu trên; không xem là thời gian truy vấn của Synapse. Thời gian hai file Parquet khác nhau dù gần bằng dung lượng, cho thấy layout/cache của file cũng ảnh hưởng; không quy toàn bộ chênh lệch cho tên định dạng.

### Phân vùng ngày/giờ và file nhỏ

Trên lake cloud, truy vấn toàn bộ Parquet `raw_archive` quét 47 MB. Một truy vấn lọc đúng phân vùng `2026/11/15/09` trên `silver.events_raw` trả 108,735 event và quét 16 MB. Đây là so sánh giữa truy vấn cùng một lake; thời gian SQLCMD bao gồm thời gian kết nối nên báo cáo lượng scan do Synapse trả về, không dùng wall-clock SQLCMD làm latency của engine.

Phân vùng 09:00 UTC gồm 57 file Parquet, tổng 30,865,512 byte (29.44 MiB), trung bình khoảng 0.54 MiB/file. CETAS có thể ghi kết quả vào một vùng mới để so sánh số file, dung lượng và scan trước/sau. Chưa chạy bước ghi CETAS: tài khoản hiện chỉ có Storage Blob Data Reader; cần quyền ghi vào vùng benchmark của container `lake`. Không ghi đè dữ liệu `raw_archive`.

### Nguồn tham khảo

- [REES46 – bộ dữ liệu eCommerce tháng 11/2019](https://data.rees46.com/datasets/marketplace/2019-Nov.csv.gz)
- [Azure Stream Analytics: event ordering](https://learn.microsoft.com/en-us/azure/stream-analytics/event-ordering)
- [Azure Stream Analytics: tumbling và các window](https://learn.microsoft.com/en-us/azure/stream-analytics/stream-analytics-window-functions)
- [Azure Stream Analytics: anomaly detection](https://learn.microsoft.com/en-us/azure/stream-analytics/stream-analytics-machine-learning-anomaly-detection)
- [Synapse serverless SQL: đọc Parquet bằng OPENROWSET](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/develop-openrowset)
- [Synapse serverless SQL: filepath và lọc file theo phân vùng](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/query-specific-files)
- [Synapse serverless SQL: khuyến nghị lọc file và định dạng](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/best-practices-serverless-sql-pool)
