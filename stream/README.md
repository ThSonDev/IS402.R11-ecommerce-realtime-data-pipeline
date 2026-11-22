# stream/ – Azure Stream Analytics

Phụ trách: Thắng

- `query.asaql`: KPI theo window và 4 luật phát hiện gian lận/sự cố.
- `reference/`: reference data đẩy lên Blob (giá tham chiếu, danh sách tỉnh).
- `test/`: input mẫu và output kỳ vọng để test query ở local (VS Code ASA extension).

## Chạy và kiểm chứng KPI 1 phút trên file mẫu

Yêu cầu: VS Code có extension **Azure Stream Analytics (ASA Tools)** và .NET runtime.

1. Mở thư mục gốc repo trong VS Code.
2. Trong PowerShell, chạy `./stream/test/prepare_local_events.ps1`. Script tạo bản replay tạm tại `stream/LocalRunOutputs/events_sample_local.json`, dịch tất cả `event_time` cùng một số phút nguyên để giữ nguyên từng bucket phút. File gốc không bị sửa.
3. Mở `stream/query.asaql` và chọn **Run locally** → **Local input and local output**.
4. Kết quả JSON được ghi trong `stream/LocalRunOutputs/<run>/`. Chạy `./stream/test/verify_local_kpi.ps1` để so từng dòng output với phép tính kỳ vọng từ bản replay.

Input alias `events` đọc bản replay của `test/events_sample.json`. Query dùng `TIMESTAMP BY event_time`, tumbling window 1 phút, nhóm theo `channel` và `province_code`; output gồm `view_count`, `cart_count`, `purchase_count`, `order_count` (distinct `order_id` trong từng nhóm phút) và `gmv_vnd`.

Đối chiếu mẫu 1,036 event: 995 view, 16 cart, 25 purchase, GMV 177,062,417 VND. Script kiểm chứng so sánh toàn bộ 580 nhóm phút × sàn × tỉnh, bao gồm distinct orders và GMV; kết quả local đã khớp toàn bộ.

`JobConfig.json` đặt late-arrival tolerance 1,800 giây để chạy lại file dài 30 phút như dữ liệu quá khứ; đây là cấu hình cho local replay, cần được rà soát riêng trước khi cấu hình job cloud. ASA local cảnh báo time policy không được hỗ trợ với static input. Script dịch mốc thời gian về gần giờ chạy để tránh toàn bộ event bị phân loại early như file mẫu cố định ban đầu; query vẫn tính theo `event_time`, không đổi sang processing time. Thư mục `LocalRunOutputs/` bị loại khỏi Git.

## Chạy trên cloud

Job `asa-megasale-dev` dựng bằng Terraform (`infra/stream_analytics.tf`), đọc thẳng `query.asaql`. Alias trên cloud: input `events`, reference `price_list`, `provinces`; outputs `raw_archive` (Parquet) và `kpi_1min` (JSON) vào container `lake` theo `<output>/yyyy/MM/dd/HH`, `kpi_1min_sql`, `pipeline_latency` và `alerts_sql` vào Azure SQL DB, `alerts_function` gọi Function `fraud_alert`, cùng `kpi_1min_powerbi` vào workspace Power BI. Các output KPI dùng chung hợp đồng cột trong `docs/event-schema.md`. Đổi tên alias trong query thì phải đổi cả trong Terraform. Cách tạo bảng/quyền và bật/tắt job xem `infra/README.md`.

### Chính sách event-time trên cloud (#37)

Query cloud dùng `TIMESTAMP BY event_time`; cấu hình đã áp dụng trong Terraform là late-arrival tolerance **60 giây**, out-of-order tolerance **60 giây**, policy **Adjust**. Bài kiểm tra sau #82 dùng `--speed 4 --late-rate 0.05 --late-delay 50`: producer gửi 76,790 event, gồm 3,803 event trễ, không lỗi. `raw_archive` có đủ 76,790 dòng và ID duy nhất; 3,803 dòng mang `is_late=true`. KPI SQL so với raw gom theo `event_time` khớp ở 16/16 phút; GMV hai phía đều 13,943,590,057 VND. ASA metrics `DroppedOrAdjustedEvents`, `LateInputEvents` và `ConversionErrors` đều bằng 0. Payload `event_time` được giữ trong raw để truy vết.

`stream/JobConfig.json` có late-arrival tolerance 1,800 giây cho replay tĩnh local; đó là cấu hình riêng cho file quá khứ và không phải cấu hình cloud.

Kết quả chạy cloud và cách đọc metric được ghi tại [docs/event-time-policy.md](../docs/event-time-policy.md). Lượt baseline trước PR #82 dùng tolerance 5/0 giây và query còn hai câu `FROM [events]`; số `LateInputEvents` trong lượt đó không phải số event late duy nhất. Query sau PR #82 dùng chung một CTE từ input `events`.

### Luật cảnh báo 2–4 (#61/#62)

`multi_account` phát cảnh báo khi có hơn 3 tài khoản mới khác nhau dùng cùng thiết bị và voucher trong một cửa sổ trượt 10 phút, bước 1 phút (`HOPPINGWINDOW(minute,10,1)`, một thiết bị có thể ra tối đa 10 dòng alert; Function chặn lặp 10 phút). `price_glitch` chỉ báo giá thấp: giá mua trung bình thấp hơn giá trong `price_list` quá 50% trong một cửa sổ 1 phút (bán lỗ). Cả hai luật ghi cùng contract 8 cột với luật bot; `event_id` là `NULL` vì ASA không hỗ trợ `MIN`/`MAX` trên chuỗi để chọn một ID đại diện. CTE `alerts` hợp nhất luật rồi ghi ra cả `alerts_sql` và `alerts_function`.

`payment_outage` đếm distinct `order_id` mỗi phút trên toàn bộ event, không lọc bỏ các phút không có purchase. Khi view/cart vẫn đến, phút không có purchase tạo điểm `0` cho chuỗi đều theo phút. ASA chạy `AnomalyDetection_SpikeAndDip` ở mode `dips` (chỉ báo đơn giảm, spike lúc phục hồi không phải sự cố), confidence ban đầu 80, `historySize=10`, `LIMIT DURATION(minute,10)`. `LAG` yêu cầu đủ 10 mẫu phút trước khi cho phép phát cảnh báo, tránh báo giả trong lúc mô hình mới khởi động. Output `threshold=90` là mốc đơn/phút tham khảo để hiển thị; điều kiện phát cảnh báo thật là `IsAnomaly=1`, không phải phép so sánh tĩnh với 90.

Đã chạy query bằng ASA Tools LocalRunService với scenario mẫu và dữ liệu giá tham chiếu: hai output alert giống nhau, contract có đủ 8 cột; lượt đó phát 2 cảnh báo `multi_account` và 5 `price_glitch` (ngoài 3 cảnh báo bot). Kiểm thử riêng luật 4 bằng chuỗi tổng hợp gồm 10 phút baseline 90 đơn/phút, sau đó 5 phút không có đơn nhưng còn view: local run không báo `payment_outage` trong baseline và phát cảnh báo ở các phút có count 0. Đây là kiểm chứng logic bằng dữ liệu tổng hợp local, chưa xác nhận khả năng bắt sự cố thật trên cloud.

Để kiểm tra luật 2–4 cùng lượt trên cloud, dùng full dataset để phát lại khoảng sự cố thật. Bắt đầu từ `2019-11-14T17:20` đến `2019-11-14T19:20` với tốc độ `4x`: khoảng 12 phút đầu làm baseline, purchase thật dừng khoảng phút 12.25; đẩy scenario nhiều tài khoản và sai giá sau phút 20 để không làm nhiễu baseline. Lệnh producer mẫu và cách tính thời điểm nằm trong [producer/README.md](../producer/README.md). Sau khi xác minh output, dừng ASA rồi chạy workflow `destroy-eventhubs` theo hướng dẫn của Sơn.
