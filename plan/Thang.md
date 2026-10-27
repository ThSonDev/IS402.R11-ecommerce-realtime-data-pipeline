# Kế hoạch – Thắng

Vai trò: "bộ não" xử lý luồng. Viết query Stream Analytics để tính số liệu kinh doanh theo từng phút và chạy 4 luật phát hiện gian lận / sự cố. Sau đó tổ chức data lake và dựng star schema trên Synapse để Power BI làm báo cáo lịch sử.

Thư mục phụ trách: `stream/`, `warehouse/`.

## Kết quả cuối cùng cần có

| Hạng mục | Kết quả mong đợi |
|---|---|
| Query KPI | Mỗi phút có số view, cart, purchase, số đơn, GMV theo sàn × tỉnh |
| 4 luật | Mỗi luật có ngưỡng giải thích được bằng số liệu, cảnh báo ghi ra đúng format |
| Test | Query chạy được trên máy với file mẫu và ra đúng kết quả kỳ vọng |
| Data lake | Toàn bộ event lưu dạng Parquet, chia thư mục theo ngày/giờ |
| Synapse | Star schema dạng view trên serverless SQL, Power BI kết nối được |
| Tối ưu | Số liệu so sánh trước / sau khi tối ưu lưu trữ |

## Tuần 1 (27/10 – 02/11): làm quen và query đầu tiên

Phụ thuộc: Minh. File event mẫu và `provinces.csv`.

Việc cần làm:

- Đọc `docs/event-schema.md`, góp ý để chốt.
- Cài VS Code và extension Azure Stream Analytics. Extension này chạy thử query ngay trên máy với file input mẫu, không cần Azure.
- Học các khái niệm chính: `TIMESTAMP BY` (xử lý theo event time), các loại window (tumbling, hopping, sliding), chính sách xử lý event đến trễ.
- Viết query KPI 1 phút đầu tiên, chạy trên file mẫu của Minh.
- Tạo `stream/reference/price_list.csv`: giá niêm yết mỗi sản phẩm. Gợi ý dùng trung vị giá trong cả tháng, tính bằng DuckDB.

Kết quả mong đợi:

- Chạy query local, ra bảng số liệu theo phút đúng với file mẫu.

## Tuần 2 (03/11 – 09/11): chạy trên cloud

Phụ thuộc: Sơn. Stream Analytics job, storage, SQL DB, Synapse dựng bằng Terraform.

Phụ thuộc: Minh. Producer gửi được event lên Event Hubs.

Giao cho: Tuấn. Output real-time `kpi_1min` đẩy vào Power BI.

Việc cần làm:

- Chốt phần 3 (output) của data contract: tên cột, kiểu dữ liệu của từng output.
- Cấu hình các output (hạ tầng do Sơn dựng bằng Terraform, Thắng lo phần query):
  - `raw_archive` ra data lake, Parquet, đường dẫn chia theo ngày/giờ.
  - `kpi_1min` ra SQL DB và Power BI.
  - `pipeline_latency` ra SQL DB.
- Cấu hình chính sách event trễ và sai thứ tự, ghi lại lý do chọn tham số.

Kết quả mong đợi:

- Pipeline end-to-end đầu tiên: dữ liệu xuất hiện trong data lake, SQL DB và Power BI.

## Tuần 3 (10/11 – 16/11): 4 luật và Synapse

Phụ thuộc: Minh. Các kịch bản gian lận và sự cố.

Giao cho: Minh. Format output `alerts` để viết Function.

Giao cho: Tuấn. Star schema trên Synapse.

Việc cần làm. Viết 4 luật, mỗi luật ghi ra output `alerts`:

| Luật | Ý tưởng | Gợi ý ngưỡng ban đầu |
|---|---|---|
| Bot gom hàng | Đếm đơn theo user trong cửa sổ 1 phút | 99.7% user-phút chỉ có 1 đơn, tối đa thật là 7. Bắt đầu thử từ khoảng 5 |
| Săn voucher | Đếm số tài khoản mới khác nhau trên cùng một thiết bị trong cửa sổ | Thử từ 3–5 tài khoản trong 10 phút |
| Sai giá | Join với `price_list.csv`, so giá bán với giá niêm yết | Giá thật dao động tới 1.67 lần (p99), nên ngưỡng phải rộng hơn, ví dụ lệch trên 50% |
| Sự cố | Hàm `AnomalyDetection_SpikeAndDip` trên số đơn mỗi phút | Chỉnh độ nhạy sao cho đoạn mất purchase thật ngày 14–17/11/2019 bị bắt |

Synapse serverless:

- Tạo nguồn dữ liệu ngoài trỏ vào data lake.
- Viết view lớp silver: ép kiểu, bỏ trùng, chuẩn hóa thời gian.
- Viết view lớp gold: star schema theo phần 4 của data contract.
- Viết `scripts/deploy_sql.py` chạy lần lượt các file SQL trong `warehouse/`.

Kết quả mong đợi:

- Bật từng kịch bản của Minh, đúng luật tương ứng có cảnh báo.
- Tuấn kết nối Power BI vào Synapse được.

## Tuần 4 (17/11 – 23/11): tối ưu và tinh chỉnh

Phụ thuộc: Minh. Kết quả precision / recall.

Giao cho: Minh. Danh sách cảnh báo của 4 luật để chấm điểm.

Việc cần làm. Thí nghiệm tối ưu lưu trữ cho rubric 3.4:

- So dung lượng và thời gian truy vấn giữa CSV, JSON và Parquet. Đã có số đầu tiên: CSV.gz 2.76 GB, 59.7 s so với Parquet 1.19 GB, 0.96 s.
- Hiệu quả của chia thư mục theo ngày: truy vấn một ngày có và không có điều kiện lọc thư mục, so lượng dữ liệu Synapse phải quét. Lượng quét chính là tiền.
- Vấn đề nhiều file nhỏ do Stream Analytics ghi ra, và cách gộp file (CETAS trên serverless; Spark chỉ khi còn budget).

Chỉnh ngưỡng 4 luật theo kết quả precision / recall của Minh.

Kết quả mong đợi:

- Bảng trước / sau cho từng biện pháp tối ưu.
- Ngưỡng cuối cùng có lý do.

## Tuần 5 (24/11 – 01/12): báo cáo

Giao cho: Sơn. Phần báo cáo của mình.

Giao cho: Tuấn. Slide phần xử lý luồng.

- Viết các phần báo cáo được giao (dưới đây).
- Chuẩn bị slide phần xử lý luồng, gửi Tuấn ghép.
- Trong demo, giải thích cách 4 luật hoạt động.

## Gợi ý và lưu ý

- Mọi query đều phải `TIMESTAMP BY event_time`. Nếu quên, hệ thống tính theo lúc nhận được, và kịch bản event trễ sẽ cho kết quả sai.
- Luật không được đọc `is_fraud` hay `scenario`. Hai trường đó chỉ để chấm điểm.
- Không đẩy từng event thô lên Power BI. Chỉ đẩy số liệu đã gom theo cửa sổ vài giây trở lên, vì Power BI streaming giới hạn tốc độ nhận.
- Stream Analytics tính tiền theo giờ khi job đang chạy. Phát triển chủ yếu bằng chạy thử local, chỉ start job trên cloud khi cần thử thật, xong là stop.
- Synapse serverless tính tiền theo lượng dữ liệu quét (6 USD/TB). Với cỡ GB thì rất rẻ, nhưng vẫn nên lọc theo thư mục ngày khi truy vấn.
- Không dùng dbt. Adapter chính thức không hỗ trợ serverless pool.

## Phần báo cáo phải viết

- 2.1: định dạng lưu trữ (CSV, JSON, Parquet) và lý do chọn Parquet.
- 2.2: lý thuyết xử lý luồng: window, event time, dữ liệu trễ, phát hiện bất thường.
- 3.2: luồng ETL tự động từ lúc nhận event đến star schema.
- 3.4: tối ưu lưu trữ và tốc độ đọc/ghi.
