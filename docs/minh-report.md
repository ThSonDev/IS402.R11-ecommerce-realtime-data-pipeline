# Phần báo cáo của Minh

Các mục theo PLAN.md mục 6 (issue #70): giới thiệu bài toán và dữ liệu (1.1–1.3), tốc độ đọc/ghi (3.1), mô tả dữ liệu và kịch bản giả lập, đánh giá 4 luật. Các mục đánh dấu **(chờ)** cần số liệu từ buổi chạy cloud.

## 1.1 Loại bài toán

Xử lý dữ liệu luồng (stream processing) thời gian thực trên cloud, gồm hai việc:

- **Giám sát kinh doanh:** tổng hợp liên tục theo cửa sổ thời gian (GMV, số đơn mỗi phút, phễu view → cart → purchase, theo sàn và tỉnh).
- **Phát hiện gian lận và sự cố:** 4 luật trên luồng event, gồm 3 luật theo ngưỡng (bot gom hàng, nhiều tài khoản mới trên một thiết bị, sai giá) và 1 luật phát hiện bất thường theo chuỗi thời gian (số đơn mỗi phút tăng / giảm đột ngột).

Dữ liệu được phát lại (replay) từ log thật, không có nguồn đơn hàng thật. Vì vậy các ca gian lận được tạo có chủ đích và gắn nhãn, để đo được độ chính xác của luật.

## 1.2 Loại dữ liệu

- **Nguồn:** REES46 – *eCommerce behavior data from multi category store*, tháng 11/2019 ([Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store), [REES46](https://rees46.com)). Log hành vi thật của một cửa hàng online đa ngành.
- **Dạng:** log sự kiện (event log) bán cấu trúc, mỗi dòng một hành động `view`, `cart` hoặc `purchase`, 9 cột: `event_time`, `event_type`, `product_id`, `category_id`, `category_code`, `brand`, `price` (USD), `user_id`, `user_session`.
- **Trên đường ống:** producer làm giàu mỗi dòng thành event JSON 22 trường (bối cảnh Việt Nam, nhãn kịch bản, thời gian replay) theo [event-schema.md](event-schema.md). Event đi qua Event Hubs dạng JSON và được lưu lâu dài dạng Parquet trong data lake.

## 1.3 Kích thước dữ liệu và tốc độ xử lý trên máy thường so với cloud

| Đại lượng | Giá trị |
|---|---|
| Số dòng | 67,501,979 (67,401,460 sau khi bỏ 100,519 dòng trùng hoàn toàn) |
| User / session / sản phẩm / brand khác nhau | 3,696,117 / 13,776,050 / 190,662 / 4,201 |
| File gốc CSV gzip | 2,855,284,937 byte (khoảng 2.86 GB) |
| Parquet (Zstandard) dùng trong dự án | 1,191,810,334 byte (khoảng 1.19 GB) |
| Event JSON sau làm giàu | Khoảng 637 byte / event, tức khoảng 43 GB nếu phát lại cả tháng |
| Tốc độ phát gốc | Trung bình 26.5 event/giây, đỉnh 243 event/giây |

**Xử lý theo lô cả tháng.** Cùng một phép tổng hợp (theo ngày × loại event: số event, số user khác nhau, doanh thu) trên toàn bộ file Parquet, bằng `scripts/bench_batch.py` (laptop) và `scripts/sql/bench_monthly_aggregate.sql` (Synapse serverless). Kết quả hai phía phải trùng: 89 dòng, 67,501,979 event, doanh thu 275,194,890.50 USD.

| Nơi chạy | Cấu hình | Thời gian (trung vị 3 lần, sau 1 lần warm-up) |
|---|---|---|
| Laptop (AMD Ryzen 9 7945HX, WSL2 7.6 GiB RAM, DuckDB 2.0.0) | 32 luồng | 0.56 giây |
| Laptop | 4 luồng | 1.66 giây |
| Laptop | 1 luồng | 7.11 giây |
| Synapse serverless (`japaneast`) | Tự co giãn | **(chờ)**: cần upload file lên `lake/benchmark/rees46/` rồi chạy truy vấn |

Lần đầu trên laptop (file chưa nằm trong cache của hệ điều hành) mất 3.85 giây với 32 luồng. Đo ngày 19/11/2026.

Nhận xét sơ bộ: với khoảng 1 GB Parquet, một laptop mạnh xử lý cả tháng trong dưới 1 giây. Lợi thế của cloud ở bài toán này không nằm ở tốc độ tổng hợp một lần, mà ở chỗ chạy **liên tục**, nhận dữ liệu từ nhiều nguồn, lưu trữ lâu dài và chia sẻ kết quả cho nhiều người. Kết luận cuối cùng chờ số đo Synapse.

## 3.1 Tốc độ đọc / ghi, throughput

Chi tiết: [producer-throughput.md](producer-throughput.md).

| Phép đo | Kết quả |
|---|---|
| Ghi: producer → Kafka local (mức trần của producer) | Khoảng 37,500 event/giây |
| Ghi: producer → Event Hubs Standard 1 TU, ổn định | Khoảng 1,500 event/giây (khoảng 0.9–1 MB/giây) |
| Ghi: Event Hubs, vượt ngắn hạn sau lúc rảnh | Tới khoảng 2,266 event/giây trong khoảng 1 phút |
| Ghi: Event Hubs, mức nhận kịp hoàn toàn (không trễ lịch) | 1,000 event/giây |
| Đọc: một consumer ← Kafka local, ổn định | Khoảng 700,000 event/giây (khoảng 430 MB/giây) |
| Đọc: một consumer ← Kafka local, dữ liệu vừa ghi còn trong cache | 1.0–2.1 triệu event/giây |
| Đọc: consumer ← Event Hubs | **(chờ)**: cần key `asa-listen` (xem `scripts/README.md`) |

Đo đọc (`scripts/bench_consumer.py`, ngày 20/11/2026): mỗi lần đọc 2,000,000 event (1,234 MB) từ topic `events` local, một consumer, tính từ message đầu tiên, chỉ đọc chứ không phân tích JSON; 2 loạt × 3 lần. Kết quả: 2.06, 1.02, 0.69, 1.06, 0.70, 0.70 triệu event/giây. Các lần đầu nhanh hơn vì dữ liệu vừa ghi còn trong bộ nhớ đệm; khi bộ nhớ đệm của WSL (khoảng 2.5 GiB) không còn chứa hết, tốc độ ổn định quanh 700,000 event/giây. Đọc nhanh hơn ghi hàng chục lần vì consumer lấy message theo lô lớn và không phải chờ broker xác nhận.

Với 1 TU, giới hạn có tác dụng là dung lượng (1 MB/giây) chứ không phải 1,000 event/giây, vì event của nhóm khoảng 637 byte. Khi demo nên giữ dưới khoảng 1,000 event/giây (`--speed` ≤ 4 ở giờ cao điểm).

## Mô tả dữ liệu

**Phân bố và chất lượng** (`analysis/eda.py`):

| Đại lượng | Giá trị |
|---|---|
| `view` / `cart` / `purchase` | 63,556,110 (94.15%) / 3,028,930 (4.49%) / 916,939 (1.36%) |
| Thiếu `category_code` / `brand` | 32.44% / 13.66% |
| Giá ≤ 0 | 0.279% (188,088 dòng, chỉ ở `view` và `cart`) |
| Tỷ lệ chuyển đổi theo session (có purchase / có view) | 5.62% |
| Giờ cao điểm | 08–10 UTC |
| User có nhiều loại event trong cùng một giây | 41,287 trường hợp (dataset chỉ chính xác đến giây) |
| Mốc cho luật | User thật tối đa 7 đơn / phút; giá một sản phẩm dao động tới 1.67 lần (p99) |
| Sự cố thật | 14–17/11/2019 không có purchase dù lượt xem vẫn tăng; giữ nguyên làm ca kiểm thử cho luật 4 |

**Xử lý và làm giàu** (chi tiết và mọi giả định: [producer/README.md](../producer/README.md)):

- Bỏ 100,519 dòng trùng; sắp theo thời gian, các event cùng giây theo thứ tự phễu view → cart → purchase.
- Gắn bối cảnh Việt Nam bằng hash SHA-256 có seed (chạy lại ra y hệt): sàn (shopee 60%, lazada 30%, tiki 10%), tỉnh theo trọng số dân số 34 tỉnh/thành sau sắp xếp 2025, thiết bị, tài khoản mới (3%), phương thức thanh toán (cod 40%, momo 30%, zalopay 20%, card 10%), voucher (20% đơn).
- Giá VND = giá USD × 25,850 (Wise mid-market, 23/10/2026).
- Thời gian: phát lại theo `--speed` (giữ tỷ lệ khoảng cách) hoặc `--rate` (đều); `event_time` là thời điểm hiện tại khi chạy live; một phần event có thể cố ý gửi trễ (`is_late`).

**Kịch bản giả lập** (`producer/scenarios.py`):

| Kịch bản | Mô phỏng | Mức độ so với dữ liệu thật |
|---|---|---|
| `bot` | 3 user giả, mỗi user 20 đơn trong 1 phút | User thật tối đa 7 đơn / phút |
| `multi_account` | 2 thiết bị, mỗi thiết bị 6 tài khoản mới cùng dùng voucher `NEWMEMBER` trong 5 phút | Mỗi user thật có thiết bị riêng |
| `price_glitch` | 3 sản phẩm giá ≥ 5 triệu VND, mỗi sản phẩm 5 đơn ở 10–30% giá tham chiếu | Giá thật lệch tối đa 1.67 lần (p99) |
| `payment_outage` | Mọi purchase trả bằng `cod` biến mất trong 10 phút | Số đơn / phút giảm khoảng 40% |

Trên đoạn 2019-11-01 09:00–10:30 (`--speed 4`, 113,928 event), dữ liệu thật không có user nào ≥ 5 đơn / phút, không thiết bị nào ≥ 3 tài khoản mới, không đơn nào thấp hơn 50% giá tham chiếu. Trong 10 phút sự cố, số purchase / phút giảm từ khoảng 105–130 xuống khoảng 57–71 (416 purchase bị loại).

## Đánh giá 4 luật

**(chờ)** luật của Thắng (#61, #62), output `alerts` (#85) và buổi chạy đủ kịch bản (#86).

**Phương pháp** (`analysis/evaluate_rules.py`): so `alerts` (xuất từ `dbo.alerts`) với file ground truth producer ghi trong lần chạy.

- Luật 1–3 tính theo **đối tượng**: precision = số đối tượng bị báo mà đúng là của kịch bản / số đối tượng bị báo; recall = số đối tượng của kịch bản bị báo / số đối tượng của kịch bản. Đối tượng là user (luật 1), thiết bị (luật 2), sản phẩm (luật 3).
- Luật 4 tính theo **thời gian**: precision = số cảnh báo rơi vào khoảng sự cố (cho phép trễ 2 phút) / tổng cảnh báo; recall = số khoảng sự cố có ít nhất một cảnh báo / số khoảng sự cố. Khoảng sự cố gồm `payment_outage` và, khi replay đoạn 14–17/11/2019, cả sự cố thật (`--incident`).

Công cụ đã được kiểm tra bằng 4 luật giả lập bằng DuckDB theo ngưỡng gợi ý trong plan/Thang.md, trên file 09:00–10:30 ở trên. Kết quả này **chỉ để kiểm tra công cụ**, không phải kết quả của các luật ASA: luật 1–3 bắt đủ và không báo nhầm; luật 4 bắt được sự cố nhưng có 1 báo nhầm ở phút cuối của dữ liệu (phút chỉ có một phần nên số đơn thấp). Đây là loại báo nhầm cần lưu ý khi đánh giá luật thật.
