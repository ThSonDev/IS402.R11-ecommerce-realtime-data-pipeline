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
| Laptop 1 (AMD Ryzen 9 7945HX, WSL2 7.6 GiB RAM, DuckDB 2.0.0) | 32 luồng | 0.56 giây |
| Laptop 1 | 4 luồng | 1.66 giây |
| Laptop 1 | 1 luồng | 7.11 giây |
| Laptop 2 (Intel Core i7-11800H, Windows 11, 31.7 GB RAM, DuckDB 2.0.0) | 16 luồng | 2.37 giây |
| Synapse serverless (`japaneast`) | Tự co giãn, không chọn cấu hình | 86.6 giây (lần warm-up 102.3 giây) |

Lần đầu trên laptop 1 (file chưa nằm trong cache của hệ điều hành) mất 3.85 giây với 32 luồng. Đo laptop 1 ngày 19/11/2026; laptop 2 và Synapse đo rạng sáng 24/11/2026 (giờ Việt Nam) trên cùng một file (1,191,757,930 byte; laptop 1 dùng bản xử lý riêng 1,191,810,334 byte, cùng kết quả tổng hợp).

Chi tiết phía Synapse: file upload lên `lake/benchmark/rees46/2019-Nov.parquet` (59 giây), chạy `scripts/sql/bench_monthly_aggregate.sql` bằng `sqlcmd` 4 lần liền nhau; thời gian lấy phía server từ `sys.dm_exec_requests_history` (`total_elapsed_time_ms`: 102,273 / 87,063 / 86,610 / 86,630 ms). Mỗi lần quét 330 MB (chỉ đọc 4 cột cần dùng của Parquet), di chuyển dữ liệu giữa các node 1,488 MB, tính tiền theo 1,818 MB xử lý, tức khoảng 0.011 USD mỗi lần ở giá 6 USD/TB (4 lần khoảng 0.04 USD). Kết quả trùng với laptop: 89 dòng, 67,501,979 event, doanh thu 275,194,890.50 USD.

Nhận xét: với khoảng 1.2 GB Parquet, laptop nhanh hơn Synapse serverless khoảng 36 lần (2.37 so với 86.6 giây). Khả năng là do `COUNT(DISTINCT user_id)` buộc Synapse chia lại dữ liệu giữa các node (1,488 MB di chuyển, gấp 4.5 lần dữ liệu quét) và chi phí khởi động truy vấn phân tán; nguyên nhân chưa kiểm chứng bằng truy vấn không có `DISTINCT`. Ở kích thước này, máy chủ truyền thống (một máy mạnh) thắng về tốc độ một lần chạy. Lợi thế của cloud trong đồ án nằm ở chỗ khác: không phải mua và giữ máy (mỗi lần tổng hợp cả tháng khoảng 0.011 USD), chạy **liên tục** và nhận luồng dữ liệu từ nhiều nguồn, lưu trữ lâu dài trên data lake, và nhiều người (Power BI, 4 thành viên) cùng đọc mà không phụ thuộc máy ai đang bật. Khi dữ liệu vượt RAM và ổ đĩa của một máy (phát lại cả tháng đã khoảng 43 GB JSON), Synapse vẫn chạy cùng truy vấn mà không đổi gì.

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
| Mốc cho luật | Một user thật có tối đa 7 dòng purchase nhưng chỉ tối đa 3 đơn khác nhau trong một phút (cả tháng); giá một sản phẩm dao động tới 1.67 lần (p99) |
| Sự cố thật | Không có purchase nào trong hai đoạn 2019-11-14 18:09 → 2019-11-16 08:32 UTC (khoảng 38 giờ) và 2019-11-16 15:34 → 2019-11-17 03:43 UTC (khoảng 12 giờ), dù lượt xem vẫn 150,000–340,000 / giờ; giữ nguyên làm ca kiểm thử cho luật 4 |

**Xử lý và làm giàu** (chi tiết và mọi giả định: [producer/README.md](../producer/README.md)):

- Bỏ 100,519 dòng trùng; sắp theo thời gian, các event cùng giây theo thứ tự phễu view → cart → purchase.
- Gắn bối cảnh Việt Nam bằng hash SHA-256 có seed (chạy lại ra y hệt): sàn (shopee 60%, lazada 30%, tiki 10%), tỉnh theo trọng số dân số 34 tỉnh/thành sau sắp xếp 2025, thiết bị, tài khoản mới (3%), phương thức thanh toán (cod 40%, momo 30%, zalopay 20%, card 10%), voucher (20% đơn).
- Giá VND = giá USD × 25,850 (Wise mid-market, 23/10/2026).
- Thời gian: phát lại theo `--speed` (giữ tỷ lệ khoảng cách) hoặc `--rate` (đều); `event_time` là thời điểm hiện tại khi chạy live; một phần event có thể cố ý gửi trễ (`is_late`).

**Kịch bản giả lập** (`producer/scenarios.py`):

| Kịch bản | Mô phỏng | Mức độ so với dữ liệu thật |
|---|---|---|
| `bot` | 3 user giả, mỗi user 20 đơn trong 1 phút | User thật tối đa 3 đơn (7 dòng purchase) / phút |
| `multi_account` | 2 thiết bị, mỗi thiết bị 6 tài khoản mới cùng dùng voucher `NEWMEMBER` trong 5 phút | Mỗi user thật có thiết bị riêng |
| `price_glitch` | 3 sản phẩm giá ≥ 5 triệu VND, mỗi sản phẩm 5 đơn ở 10–30% giá tham chiếu | Giá thật lệch tối đa 1.67 lần (p99) |
| `payment_outage` | Mọi purchase trả bằng `cod` biến mất trong 10 phút | Số đơn / phút giảm khoảng 40% |

Trên đoạn 2019-11-01 09:00–10:30 (`--speed 4`, 113,928 event), dữ liệu thật không có user nào ≥ 5 đơn / phút, không thiết bị nào ≥ 3 tài khoản mới, không đơn nào thấp hơn 50% giá tham chiếu. Trong 10 phút sự cố, số purchase / phút giảm từ khoảng 105–130 xuống khoảng 57–71 (416 purchase bị loại).

## Đánh giá 4 luật

Dữ liệu: buổi chạy cloud ngày 22/11/2026 (#86, chi tiết cấu hình và độ trễ trong [e2e-run.md](e2e-run.md)). Số dưới đây được tính lại từ `lake/eval/2026-11-22/` (alert xuất từ `dbo.alerts` và file ground truth của producer) bằng `analysis/evaluate_rules.py`, khớp với số trong e2e-run.md.

| Lượt | Dữ liệu (`--speed 4`) | Kịch bản | Query |
|---|---|---|---|
| A | 2019-11-01 09:00–10:30, 113,928 event, 5% trễ | cả 4 | Bản cũ |
| A2 | Như A | cả 4 | Bản đã sửa theo định nghĩa luật (#101, e2e-run.md mục 1) |
| B | 2019-11-14 17:20–19:20, 498,298 event | `multi_account`, `price_glitch` + sự cố thật (purchase về 0 từ 10:39:19) | Bản đã sửa |

Luật như đang chạy trong `stream/query.asaql` (bản sửa; khác biệt của lượt A ghi trong ngoặc):

| Luật | Điều kiện báo | Cửa sổ |
|---|---|---|
| 1. Bot | > 10 đơn khác nhau / user | Tumbling 1 phút |
| 2. Nhiều tài khoản | > 3 tài khoản mới / thiết bị | Hopping 10 phút, bước 1 phút (A: tumbling 10 phút) |
| 3. Sai giá | Giá bán thấp hơn giá tham chiếu quá 50% (A: lệch cả hai chiều) | Tumbling 1 phút / sản phẩm |
| 4. Sự cố | `AnomalyDetection_SpikeAndDip(số đơn / phút, 80, 10, 'dips')` (A: `'spikesanddips'`) | 1 phút |

### Kết quả

| Luật (đơn vị chấm) | A: precision / recall | A2: precision / recall | B: precision / recall |
|---|---|---|---|
| 1. Bot (user) | 100% / 100% (3 / 3) | 100% / 100% (3 / 3) | không có kịch bản |
| 2. Nhiều tài khoản (thiết bị) | 100% / **50%** (1 / 2) | 100% / 100% (2 / 2) | 100% / 100% (2 / 2) |
| 3. Sai giá (sản phẩm) | **60%** / 100% (3 đúng / 5) | 100% / 100% (3 / 3) | 100% / 100% (3 / 3) |
| 4. Sự cố (khoảng thời gian) | **40%** / 100% (2 / 5 cảnh báo) | – / **0%** (0 cảnh báo) | 100% / 100% (1 cảnh báo) |

Thời gian từ khi gian lận đủ điều kiện đến cảnh báo đầu tiên (lượt A2 và B; `alert_time` là thời điểm đóng cửa sổ trên trục `event_time`, chưa tính độ trễ pipeline khoảng 130 ms):

| Luật | Bắt đầu | Cảnh báo đầu tiên | Độ trễ phát hiện |
|---|---|---|---|
| 1. Bot (A2) | Đơn đầu 10:01:14 | 10:02:00 | 46 giây |
| 2. Nhiều tài khoản (A2) | Tài khoản thứ 4 của `dev_2ec235002de4` lúc 10:04:29 | 10:05:00 | 31 giây |
| 2. Nhiều tài khoản (A, tumbling) | Tài khoản thứ 4 của `dev_0d39e1dce23a` lúc 09:32:49 | 09:40:00 | khoảng 7 phút |
| 3. Sai giá (A2) | Đơn giá thấp đầu tiên 10:05:14 | 10:06:00 | 46 giây |
| 4. Sự cố thật (B) | Purchase về 0 lúc 10:39:19 | 10:41:00 | 1 phút 41 giây |

### Phân tích báo nhầm và bỏ sót

**Luật 1 (bot).** Bắt đủ 3 bot ở cả hai lượt, không báo nhầm.

- Không có báo nhầm trên dữ liệu thật là có cơ sở: tính trên cả tháng 11, một user thật có **tối đa 3 đơn khác nhau trong một phút**, không user-phút nào ≥ 5 đơn. Ngưỡng > 10 cách xa hành vi thật.
- **Rủi ro bỏ sót do cắt cửa sổ.** Giá trị đo của bot là 19 (A) và 16 (A2), không phải 20, vì 20 đơn trải trong 60 giây rơi vào hai cửa sổ tumbling 1 phút (A: 19 + 1, A2: 16 + 4). Hai lượt này vẫn vượt 10, nhưng nếu bot bắt đầu đúng giữa phút thì bị cắt 10 + 10 và **lọt hoàn toàn** vì điều kiện là > 10. Đây là cùng loại lỗi đã làm luật 2 bỏ sót ở lượt A.
- Đề xuất cho #72: dùng cửa sổ hopping (ví dụ 60 giây, bước 10 giây) như đã làm với luật 2, hoặc hạ ngưỡng. Vì người thật tối đa 3 đơn / phút, ngưỡng > 5 vẫn không báo nhầm trên cả tháng mà giảm hẳn rủi ro cắt cửa sổ.

**Luật 2 (nhiều tài khoản mới trên một thiết bị).**

- **Bỏ sót ở lượt A** (`dev_2ec235002de4`): 6 tài khoản tạo lúc 09:29:04–09:31:09, cửa sổ tumbling 10 phút cắt ở 09:30 thành 3 + 3. Điều kiện > 3 cần 4 tài khoản trong cùng cửa sổ nên không báo. Thiết bị còn lại (6 tài khoản trong 09:31:34–09:33:39) nằm gọn trong một cửa sổ nên bị bắt, nhưng chỉ khi cửa sổ đóng (09:40), khoảng 7 phút sau tài khoản thứ 4.
- **Sau khi đổi sang hopping (A2, B):** bắt đủ 2 thiết bị, cảnh báo ngay khi có tài khoản thứ 4 (31 giây và 1 giây sau). Đổi lại mỗi thiết bị sinh khoảng 10 dòng cảnh báo (một dòng mỗi bước 1 phút còn đủ 4 tài khoản): 20 dòng cho 2 thiết bị ở A2. Chấm theo thiết bị nên precision không đổi, và Function `fraud_alert` chặn lặp 10 phút nên mỗi thiết bị chỉ ra **một** tin Telegram (dòng đầu và cuối của một thiết bị cách nhau 9 phút).
- **Không báo nhầm, nhưng phần lớn do giả định mô phỏng:** producer gán mỗi user thật một thiết bị riêng, nên dữ liệu thật không thể có nhiều tài khoản trên một thiết bị. Precision 100% của luật 2 vì vậy chưa nói lên khả năng tránh báo nhầm với thiết bị dùng chung thật (gia đình, máy công cộng).

**Luật 3 (sai giá).**

- **Báo nhầm ở lượt A:** 2 sản phẩm thật bị báo vì giá **cao** hơn giá tham chiếu (`12704397` bán khoảng 1.98 lần, `2500566` khoảng 1.50 lần với tỷ lệ lệch 0.5003, sát ngưỡng 0.5). Luật cũ lấy độ lệch tuyệt đối nên coi giá cao cũng là sai giá. Bỏ `ABS` (chỉ báo giá thấp) loại được cả hai; A2 và B không còn báo nhầm.
- **Ước tính báo nhầm trên cả tháng** (dữ liệu thật, giá tham chiếu = trung vị giá dương của tháng): luật mới sẽ báo **231 đơn thật (66 sản phẩm)**, tức 0.025% trong 916,930 đơn; mỗi ngày trung vị 4 đơn (0–35). Luật cũ hai chiều sẽ báo 1,140 đơn (291 sản phẩm), gấp khoảng 5 lần. Các đơn này là giảm giá sâu thật hoặc sản phẩm có giá dao động mạnh; theo nhãn của nhóm chúng là báo nhầm, dù một phần có thể đáng kiểm tra. Đoạn dữ liệu của lượt A2 và B tình cờ không có đơn nào như vậy.
- **Không bỏ sót:** đơn của kịch bản bán ở 10–30% giá tham chiếu, tức lệch 0.70–0.90, xa ngưỡng 0.5. Mỗi sản phẩm ra 1–2 dòng cảnh báo vì 5 đơn của nó trải qua 2 phút (A2: 5 dòng cho 3 sản phẩm).

**Luật 4 (sự cố số đơn).**

- **Lượt A (`'spikesanddips'`):** cả 5 cảnh báo đều nằm **sau** sự cố giả lập (09:33:04–09:43:04). Bốn cảnh báo 09:44–09:47 (89–101 đơn / phút) là đỉnh khi số đơn hồi phục, không phải phát hiện sự cố; 2 trong số đó được tính là đúng chỉ vì nằm trong 2 phút dung sai của công cụ chấm. Cảnh báo 09:49 (57 đơn / phút) là phút cuối của lượt chạy (kết thúc 09:49:24), phút chỉ có một phần nên số đơn thấp, đúng loại báo nhầm đã thấy khi kiểm tra công cụ. Thực chất lượt A **không bắt được** sự cố giả lập.
- **Lượt A2 (`'dips'`, độ tin cậy 80):** 0 cảnh báo. Sự cố giả lập chỉ làm số đơn giảm khoảng 40% (từ khoảng 100–120 xuống khoảng 65 đơn / phút), mô hình không coi là bất thường ở mức tin cậy 80. **Bỏ sót.**
- **Lượt B (sự cố thật, số đơn về 0):** 1 cảnh báo lúc 10:41 (0 đơn / phút), 1 phút 41 giây sau khi purchase biến mất, không báo nhầm. Nhưng chỉ có **một** cảnh báo cho khoảng 18 phút sự cố: sau điểm bất thường đầu, mô hình (lịch sử 10 phút) dần coi 0 là bình thường.
- Kết luận: `AnomalyDetection_SpikeAndDip` bắt được sụp đổ đột ngột về 0 nhưng bỏ qua sụt giảm một phần (một phương thức thanh toán mất), và không báo lại khi sự cố kéo dài. Đề xuất cho #72: (1) hạ độ tin cậy và chạy lại A2 để xem đánh đổi với báo nhầm; (2) thêm luật đơn giản bổ trợ, ví dụ số đơn / phút dưới một tỷ lệ so với trung bình trượt trong N phút liên tục, để bắt sụt giảm một phần và báo trong suốt sự cố; (3) với sự cố cổng thanh toán, đếm đơn theo `payment_method`: một phương thức về 0 trong khi các phương thức khác vẫn có đơn là dấu hiệu trực tiếp nhất.

### Kiểm tra công cụ trước buổi chạy

Trước khi có luật ASA, công cụ đã được kiểm tra bằng 4 luật giả lập bằng DuckDB theo ngưỡng gợi ý trong plan/Thang.md, trên file 09:00–10:30: luật 1–3 bắt đủ và không báo nhầm; luật 4 có 1 báo nhầm ở phút cuối của dữ liệu. Buổi chạy thật lặp lại đúng hiện tượng phút cuối này (cảnh báo 09:49 ở lượt A).

### Hạn chế

- Gian lận do nhóm tự tạo theo đúng 4 kiểu đã định nghĩa, và khá "mạnh" (bot 20 đơn / phút so với tối đa 3 đơn của người thật). Precision / recall cao chỉ cho thấy luật bắt được đúng các kiểu này, không chứng minh luật hiệu quả với gian lận thật, vốn đa dạng hơn và thường cố tình né ngưỡng. Nên chạy thêm kịch bản yếu hơn khi chỉnh ngưỡng (#72), ví dụ giảm `BOT_ORDERS` trong `producer/scenarios.py` xuống 8–12.
- Mỗi cấu hình chỉ chạy một lần; vị trí kịch bản so với ranh giới cửa sổ (yếu tố quyết định ở luật 1 và luật 2 bản tumbling) chỉ được thử ở vài điểm.
- Ground truth luật 1–3 là đối tượng do kịch bản tạo; người thật có hành vi giống gian lận bị tính là báo nhầm dù có thể đáng nghi. Luật 2 không thể báo nhầm trên dữ liệu thật vì giả định một user một thiết bị.
- Alert được xuất theo khoảng giờ của từng lượt, nên đuôi cảnh báo của lượt trước có thể lẫn vào lượt sau (e2e-run.md mục 5). Lượt B có 17 dòng `multi_account` trong file CSV nhưng 16 trong SQL; chấm theo thiết bị nên không đổi kết quả.
- Dung sai 2 phút của luật 4 có thể tính nhầm đỉnh hồi phục ngay sau sự cố là phát hiện đúng (lượt A). Với luật chỉ báo `'dips'` thì không còn ảnh hưởng.
