# Xử lý luồng, ETL và tối ưu lưu trữ

## 2.1. Định dạng lưu trữ

Pipeline dùng JSON cho event gửi từ producer vào Event Hubs. JSON dễ kiểm tra và biểu diễn được các trường tùy chọn như `category_code`, `brand` và `voucher_code`. Đổi lại, dữ liệu số và thời gian cần được diễn giải theo contract khi đọc; tên thuộc tính lặp lại trên mỗi event.

CSV được dùng cho reference data nhỏ, gồm `price_list.csv` và `provinces.csv`. CSV tương thích rộng và gọn với bảng phẳng, nhưng không mang schema theo từng cột nên bên đọc phải biết trước thứ tự và kiểu dữ liệu.

Data lake lưu `raw_archive` dạng Parquet. Parquet là định dạng cột, phù hợp với truy vấn phân tích chỉ đọc một phần cột; Synapse serverless hỗ trợ đọc Parquet trực tiếp bằng `OPENROWSET`. ASA chia đường dẫn theo năm/tháng/ngày/giờ (`raw_archive/yyyy/MM/dd/HH`). View `silver.events_raw` đưa các phần của đường dẫn này thành cột để truy vấn có thể lọc theo phân vùng. Lợi ích đo được về dung lượng và tốc độ được trình bày ở mục 3.4.

## 2.2. Xử lý luồng

Producer phát event JSON có `event_time` là thời điểm nghiệp vụ sau khi replay và `sent_time` là thời điểm gửi. Query ASA dùng `TIMESTAMP BY event_time`; nếu không khai báo, ASA mặc định xử lý theo thời điểm event đến input. Vì vậy cửa sổ thời gian KPI dùng thời gian nghiệp vụ thay vì thời gian nhận ở Event Hubs.

KPI nhóm event theo `channel` và `province_code` trong tumbling window một phút. Tumbling window tạo các khoảng liền nhau, không chồng lấn; một event chỉ thuộc một window. Output được gắn `window_end` qua `System.Timestamp()`.

Event có thể đến trễ so với `event_time` hoặc không đúng thứ tự. Cấu hình cloud đã áp dụng là late-arrival tolerance 60 giây và out-of-order tolerance 60 giây; policy out-of-order là `Adjust`. Hai ngưỡng cho ASA thời gian xử lý các event trễ/sai thứ tự trong giới hạn đã thử. Static input của ASA Tools không kiểm chứng được policy cloud; kết quả dưới đây đến từ Event Hubs.

Cloud test trên baseline `c74ce16` ghi nhận 2,000 event trong bài late-arrival; producer đánh dấu 102 event đến trễ và chúng vẫn xuất hiện trong `raw_archive`. Baseline này dùng tolerance 5/0 giây trước PR #82, nên là kết quả lịch sử. Bài cloud sau #82 dùng cấu hình 60/60 giây và producer `--speed 4 --late-rate 0.05 --late-delay 50`: gửi 76,790 event, trong đó 3,803 event trễ, không lỗi. `raw_archive` có 76,790 dòng với 76,790 ID duy nhất và 3,803 dòng `is_late=true`. KPI SQL so với raw gom theo payload `event_time` khớp tuyệt đối ở 16/16 phút về view, cart, purchase và GMV; tổng GMV hai bên là 13,943,590,057 VND. ASA metrics `DroppedOrAdjustedEvents`, `LateInputEvents` và `ConversionErrors` đều bằng 0. Phép đối chiếu này xác minh KPI và lake cho batch đó, không tự xác minh sink Power BI.

Luật sự cố dùng `AnomalyDetection_SpikeAndDip` trên số đơn phân biệt theo tumbling window một phút. Mỗi phút có traffic được giữ lại trong chuỗi, kể cả phút không có purchase nhưng còn view/cart; phút đó được biểu diễn bằng `order_count = 0`, nhờ vậy đoạn mất đơn không biến mất khỏi chuỗi đầu vào. Cấu hình cloud đã kiểm tra dùng confidence 80 và `historySize=10`; `LAG` chặn cảnh báo trong 10 phút đầu để mô hình có đủ lịch sử. `threshold=90` trong output chỉ là mốc tham khảo để hiển thị, điều kiện phát cảnh báo là `IsAnomaly=1`. Trong replay cloud 22/11, cấu hình này bắt được sự cố thật khi số đơn về 0 nhưng bỏ sót sự cố giả lập giảm khoảng 40%; chi tiết và đề xuất cho #72 ở mục dưới. Không dùng `is_fraud` hoặc `scenario` làm đầu vào phát hiện vì đây là nhãn đánh giá.

## 3.2. Luồng ETL

1. **Extract:** producer đọc dữ liệu REES46 đã chuẩn bị, loại các bản ghi trùng theo quy trình trong `producer/`, làm giàu event theo `docs/event-schema.md` và gửi JSON đến Event Hubs `events`. Partition key là `user_id`.
2. **Transform thời gian thực:** ASA đọc input `events` một lần trong CTE `ev`, dùng `TIMESTAMP BY event_time`, đồng thời chiếu metadata Event Hubs. Từ luồng dùng chung, query tính KPI theo tumbling window một phút, chạy các luật cảnh báo và tổng hợp độ trễ; reference data `price_list` được join trong luật sai giá.
3. **Load dữ liệu thô, KPI và cảnh báo:** ASA ghi `raw_archive` thành Parquet trong ADLS Gen2 theo đường dẫn năm/tháng/ngày/giờ. Cùng một phép tổng hợp KPI được ghi ra lake (`kpi_1min`), Azure SQL (`kpi_1min_sql`) và Power BI (`kpi_1min_powerbi`). `pipeline_latency` và `alerts_sql` đi vào Azure SQL; `alerts_function` gửi cảnh báo đến Azure Function. SQL và Power BI cần output, identity và quyền đích được cấu hình trước khi start job.
4. **Làm sạch và phục vụ lịch sử:** Synapse serverless đọc Parquet qua external data source `MegasaleLake`. `silver.events_raw` ép kiểu và giữ thông tin phân vùng; `silver.events` loại bản ghi thiếu khóa/thời gian hợp lệ và giữ bản nhận mới nhất cho mỗi `event_id`. Cloud test với run ngày 15/11/2026, 09:00 UTC, cho 108,735 dòng thô và 108,735 dòng silver; số này khớp log producer của run. Lớp Gold hiện có sáu view: `dim_date`, `dim_product`, `dim_channel`, `dim_province`, `dim_payment` và `fact_events`, được tạo bằng `scripts/deploy_sql.py` trên Synapse serverless. `fact_alerts` chưa có vì cảnh báo hiện được ghi vào Azure SQL, chưa có nguồn cảnh báo trong lake; không nên mô tả star schema như đã chứa fact cảnh báo.

Luồng truy vấn và lệnh kết nối được ghi trong `stream/README.md`, `infra/README.md`, `warehouse/README.md` và `scripts/README.md`. ASA job được giữ ở trạng thái Stopped khi không đo để tránh tính phí theo giờ.

### Đo độ trễ pipeline trên cloud

Trong một đợt chạy sạch kéo dài 5 phút với 24,991 event, độ trễ trung bình theo event là khoảng 320 ms từ producer đến Event Hubs, 140 ms từ Event Hubs đến ASA và 476 ms từ lúc gửi đến khi ASA xử lý. KPI được xuất hiện sau khoảng 1–3 phút do tumbling window một phút kết hợp ngưỡng chờ 60/60 giây; đây là thời gian chờ output theo window, khác với độ trễ xử lý trung bình theo từng event.

### Kết quả cloud và đề xuất ngưỡng (#72)

Buổi chạy E2E ngày 22/11/2026 gồm lượt A2 sau khi sửa định nghĩa luật (113,928 event, 5,704 event trễ) và lượt B có sự cố thật (498,298 event). Producer không báo lỗi gửi. Bảng dưới là kết quả tính từ alert trong Azure SQL và ground truth của producer bằng `analysis/evaluate_rules.py`; phương pháp và ca sai được trình bày chi tiết trong [`docs/minh-report.md`](minh-report.md) và [`docs/e2e-run.md`](e2e-run.md).

| Luật | A2: precision / recall | B: precision / recall | Nhận xét |
|---|---|---|---|
| Bot | 100% / 100% (3/3 user) | Không có kịch bản bot | Bot 20 đơn/phút được bắt, nhưng cửa sổ tumbling có thể chia đơn qua ranh giới phút. |
| Nhiều tài khoản | 100% / 100% (2/2 thiết bị) | 100% / 100% (2/2 thiết bị) | Hopping 10 phút, bước 1 phút bắt đủ; kết quả không kiểm chứng báo nhầm trên thiết bị dùng chung thật vì producer giả định mỗi user có thiết bị riêng. |
| Sai giá | 100% / 100% (3/3 sản phẩm) | 100% / 100% (3/3 sản phẩm) | Chỉ báo giá thấp hơn tham chiếu quá 50%; kết quả cả tháng ước tính vẫn có 231 đơn thật bị đánh dấu (0.025%, trung vị 4 đơn/ngày). |
| Sự cố | 0 cảnh báo, recall 0% với mức giảm khoảng 40% | 100% / 100% (1 cảnh báo) khi đơn về 0 | Confidence 80 bắt được sự cố thật sau 1 phút 41 giây nhưng chỉ báo một lần trong khoảng sự cố ~18 phút. |

Lượt A dùng query cũ và cần đọc thận trọng: luật 2 chỉ đạt recall 50% do cửa sổ tumbling 10 phút cắt 6 tài khoản thành hai nhóm 3; luật 3 đạt precision 60% do query cũ báo cả giá cao; luật 4 dùng `spikesanddips`, các cảnh báo sau sự cố bị tính đúng một phần do công cụ chấm cho phép trễ 2 phút, dù thực tế không phát hiện dip trong khoảng sự cố. Vì vậy không dùng A làm bằng chứng cho chất lượng của định nghĩa luật hiện tại.

**Đề xuất để chốt #72 (chưa áp dụng vào query):**

- **Bot:** ưu tiên thử `HOPPINGWINDOW(second, 60, 10)` với ngưỡng `> 10` để giảm khả năng bỏ lọt do ranh giới tumbling; đánh đổi là có thể có nhiều dòng cảnh báo trùng. Phương án ít thay đổi hơn là hạ ngưỡng xuống `> 5`: dữ liệu tháng có tối đa 3 đơn khác nhau/user/phút và không có user-phút nào từ 5 đơn trở lên, nhưng cần chạy kịch bản bot yếu 8–12 đơn/phút ở nhiều vị trí ranh giới trước khi chọn.
- **Nhiều tài khoản:** giữ `> 3` tài khoản mới trên cùng thiết bị trong 10 phút và hopping bước 1 phút. Ghi rõ precision/recall 100% trên bộ kịch bản không chứng minh được precision với thiết bị gia đình/máy công cộng.
- **Sai giá:** giữ điều kiện một chiều giá bán thấp hơn giá tham chiếu trên 50% (`deviation > 0.5`) cho bộ kịch bản hiện tại. Công bố riêng ước tính 231 đơn thật/tháng bị gắn cờ; dữ liệu hiện có chưa đo precision/recall của các ngưỡng thay thế.
- **Sự cố:** giữ `dips`, `historySize=10`; đề xuất thử confidence 70 so với 80 trên cùng baseline, ca giảm 40% và ca về 0. Chưa có lượt chạy confidence 70 nên đây là mức thử đề xuất, không phải ngưỡng đã xác minh. Giữ cấu hình cloud hiện tại ở 80 cho tới khi có kết quả so sánh; không sửa query chỉ dựa trên suy đoán.

Số độ trễ của cùng buổi chạy cũng có giới hạn: `pipeline_latency` chỉ đo Event Hubs → ASA bằng thời gian Azure, median các giá trị trung bình theo phút là 136 ms ở A2 và 128 ms ở B; A2 có đỉnh 6,775 ms ngay sau lúc start job, chưa xác minh nguyên nhân. Độ trễ end-to-end 250–260 ms trong `e2e-run.md` là phép cộng hai phép đo riêng, không phải đo trực tiếp. `InputEvents` của ASA lớn hơn số producer gửi và có 8,000 payload lỗi từ lần đo region; chưa giải thích được phần chênh còn lại. Không lấy các số này làm kết quả độ trễ end-to-end chính xác.

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

Phân vùng 09:00 UTC gồm 57 file Parquet, tổng 30,865,512 byte (29.44 MiB), trung bình khoảng 0.54 MiB/file. CETAS serverless xuất thử cùng partition vào `lake/benchmark/`: kết quả có 16 file Parquet, tổng 11,054,823 byte (10.54 MiB), giảm 64.2% dung lượng và 71.9% số file. `COUNT_BIG`, distinct event ID, view/cart/purchase và GMV đều khớp nguồn; truy vấn đếm riêng quét 4 MB ở nguồn và 2 MB ở CETAS. Lệnh CETAS đọc 35 MB và ghi 12 MB. CETAS tạo nhiều file song song nên không gộp thành một file duy nhất. Đã xóa đúng prefix benchmark và external table/file format tạm sau khi đo; xác nhận 57 file nguồn trong `raw_archive` vẫn còn.

### Nguồn tham khảo

- [REES46 – bộ dữ liệu eCommerce tháng 11/2019](https://data.rees46.com/datasets/marketplace/2019-Nov.csv.gz)
- [Azure Stream Analytics: event ordering](https://learn.microsoft.com/en-us/azure/stream-analytics/event-ordering)
- [Azure Stream Analytics: tumbling và các window](https://learn.microsoft.com/en-us/azure/stream-analytics/stream-analytics-window-functions)
- [Azure Stream Analytics: anomaly detection](https://learn.microsoft.com/en-us/azure/stream-analytics/stream-analytics-machine-learning-anomaly-detection)
- [Synapse serverless SQL: đọc Parquet bằng OPENROWSET](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/develop-openrowset)
- [Synapse serverless SQL: filepath và lọc file theo phân vùng](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/query-specific-files)
- [Synapse serverless SQL: khuyến nghị lọc file và định dạng](https://learn.microsoft.com/en-us/azure/synapse-analytics/sql/best-practices-serverless-sql-pool)
