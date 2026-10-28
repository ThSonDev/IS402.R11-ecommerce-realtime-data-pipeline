# Kế hoạch – Minh

Vai trò: tạo ra dòng dữ liệu cho cả hệ thống. Producer đọc dataset thật, phát lại như đang diễn ra, gắn bối cảnh Việt Nam, chèn gian lận có nhãn, gửi vào Kafka / Event Hubs. Ngoài ra viết Azure Function gửi cảnh báo, đo tốc độ, và chấm điểm 4 luật.

Thư mục phụ trách: `producer/`, `tests/`, `functions/`, `analysis/` (phần đánh giá), `docker-compose.yaml` (phần Kafka).

## Kết quả cuối cùng cần có

| Hạng mục | Kết quả mong đợi |
|---|---|
| Producer | Một lệnh chạy được, chọn được tốc độ replay, khoảng thời gian, bật / tắt từng kịch bản. Chạy lại cùng tham số ra cùng dữ liệu |
| Dev local | `docker compose up` có Kafka để cả nhóm thử mà không tốn tiền Azure |
| Kịch bản | 4 kịch bản gian lận / sự cố và event trễ, đều có nhãn đúng theo data contract |
| Function | Nhận cảnh báo từ Stream Analytics, gửi tin nhắn Discord/Telegram dễ đọc, không spam |
| Đánh giá | Bảng precision / recall cho từng luật |
| Benchmark | Số đo tốc độ ghi/đọc và so sánh xử lý trên máy thường với cloud |

## Tuần 1 (27/10 – 02/11): producer chạy local

Giao cho: Thắng. File event mẫu và `provinces.csv`.

Giao cho: Tuấn. File dữ liệu mẫu nhỏ (khoảng 1 ngày).

Việc cần làm:

- Đọc kỹ `docs/event-schema.md`, góp ý để chốt trước cuối tuần.
- Viết `docker-compose.yaml` với một Kafka đơn node (chế độ KRaft, không cần Zookeeper).
- Producer bản đầu:
  - Đọc `data/processed/2019-Nov.parquet`, bỏ dòng trùng, sắp theo thời gian.
  - Gửi event JSON vào topic `events` theo tốc độ chọn được.
- Gắn các trường bối cảnh Việt Nam: sàn, tỉnh, phương thức thanh toán, thiết bị, tài khoản mới, voucher, giá VND.
- Tạo file `stream/reference/provinces.csv` gồm 34 tỉnh/thành mới, miền và dân số. Dân số lấy từ nguồn chính thức, ghi nguồn trong PR.
- **Ưu tiên cao:** xuất một file mẫu khoảng 1,000 event JSON đúng contract để Thắng test query local. File nhỏ, được commit vào `stream/test/`.
- Xuất một file dữ liệu mẫu khoảng 1 ngày (Parquet hoặc CSV) để Tuấn dựng thử Power BI. File này gửi trực tiếp, không commit.

Kết quả mong đợi:

- Chạy producer và thấy event chảy vào Kafka local.
- Thắng có file mẫu trong 2–3 ngày đầu tuần.

## Tuần 2 (03/11 – 09/11): lên cloud

Phụ thuộc: Sơn. Event Hubs và thông tin kết nối.

Việc cần làm:

- Thêm cấu hình gửi vào Event Hubs qua Kafka endpoint. Chỉ đổi thông tin kết nối trong `.env`, code giữ nguyên.
- Dịch thời gian: đổi `event_time` về thời điểm hiện tại, giữ `original_time`, thêm `sent_time`.
- Dịch múi giờ để giờ cao điểm rơi vào buổi tối giờ Việt Nam. Giờ cao điểm gốc là 08–10 UTC.
- Thêm event trễ: một tỷ lệ nhỏ event gửi chậm hơn thời gian thật, gắn `is_late = true`.
- Viết test `pytest` cho phần làm giàu dữ liệu:
  - Cùng seed thì ra cùng kết quả.
  - Đủ trường bắt buộc.
  - Giá trị nằm trong danh sách cho phép.
- Đo tốc độ gửi tối đa của producer lên Event Hubs.

Kết quả mong đợi:

- Pipeline end-to-end đầu tiên chạy cùng Sơn và Thắng.
- Có số event/giây tối đa gửi được.

## Tuần 3 (10/11 – 16/11): kịch bản và cảnh báo

Phụ thuộc: Sơn. Function App dựng bằng Terraform.

Phụ thuộc: Thắng. Format output `alerts`.

Việc cần làm. Chèn 4 kịch bản, mỗi kịch bản bật / tắt được và gắn `is_fraud`, `scenario` đúng:

- `bot`: vài user ảo đặt dồn dập nhiều đơn trong thời gian ngắn.
- `multi_account`: một thiết bị gắn với nhiều tài khoản mới cùng dùng một voucher.
- `price_glitch`: một vài sản phẩm bị bán với giá thấp bất thường.
- `payment_outage`: purchase qua một phương thức thanh toán biến mất trong khoảng 10 phút.

Song song, viết Azure Function `fraud_alert`:

- Nhận cảnh báo do Stream Analytics gửi sang.
- Định dạng thành tin nhắn ngắn: luật nào, đối tượng nào, giá trị bao nhiêu.
- Gửi về Discord hoặc Telegram qua webhook.
- Gộp các cảnh báo trùng nhau để không spam.
- Hạ tầng Function do Sơn dựng.

Kết quả mong đợi:

- Bật một kịch bản, sau vài giây có tin nhắn cảnh báo.

## Tuần 4 (17/11 – 23/11): đo và chấm điểm

Phụ thuộc: Thắng. Danh sách cảnh báo của 4 luật đã chạy trên dữ liệu có kịch bản.

Giao cho: Thắng. Kết quả precision / recall để chỉnh ngưỡng.

Việc cần làm:

- Đánh giá 4 luật:
  - So danh sách cảnh báo (trong SQL DB hoặc data lake) với nhãn ground truth.
  - Tính precision (báo đúng bao nhiêu phần) và recall (bắt được bao nhiêu phần).
  - Gửi kết quả cho Thắng chỉnh ngưỡng.
- Benchmark cho rubric 1.3 và 3.1:
  - Cùng một khối lượng xử lý (ví dụ tổng hợp cả tháng 11), chạy trên laptop và trên cloud (Synapse serverless), so thời gian.
  - Đo tốc độ ghi vào Event Hubs và tốc độ đọc ra ở các mức tải khác nhau.

Kết quả mong đợi:

- Bảng precision / recall có giải thích vì sao luật nào báo nhầm hoặc bỏ sót.
- Bảng benchmark có điều kiện đo rõ ràng (máy gì, dữ liệu bao nhiêu, lặp mấy lần).

## Tuần 5 (24/11 – 01/12): báo cáo

Giao cho: Sơn. Phần báo cáo của mình.

Giao cho: Tuấn. Slide phần của mình.

- Viết các phần báo cáo được giao (dưới đây).
- Chuẩn bị slide cho phần của mình, gửi Tuấn ghép.
- Trong demo, phụ trách bật producer và các kịch bản.

## Gợi ý và lưu ý

- Kafka client gợi ý: `confluent-kafka`. Event Hubs nhận được qua Kafka endpoint, chỉ cần cấu hình SASL.
- Gán sàn / tỉnh / thiết bị theo hash của `user_id` thay vì random mỗi lần, để chạy lại ra kết quả giống nhau.
- Đọc Parquet theo từng khúc, không nạp cả 67.5 triệu dòng vào RAM.
- 1 TU Event Hubs nhận tối đa 1,000 event/giây. Tốc độ gốc của dataset đỉnh 243 event/giây, nên replay nhanh hơn khoảng 4 lần là chạm trần.
- Đoạn 14–17/11/2019 không có purchase nào dù lượt xem vẫn tăng. Đây là dữ liệu thật, giữ nguyên để luật 4 có ca kiểm thử thật. Không "sửa" đoạn này.
- Tỷ giá USD → VND là một hằng số. Ghi rõ nguồn và ngày lấy.

## Phần báo cáo phải viết

- 1.1–1.3: loại bài toán, loại dữ liệu, kích thước dữ liệu, so sánh tốc độ xử lý trên máy thường và trên cloud.
- 3.1: tốc độ đọc/ghi, throughput.
- Mô tả dữ liệu: nguồn, EDA, cách làm giàu, các kịch bản giả lập.
- Kết quả đánh giá 4 luật.
