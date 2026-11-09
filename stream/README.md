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

Job `asa-megasale-dev` dựng bằng Terraform (`infra/stream_analytics.tf`), đọc thẳng `query.asaql`. Alias trên cloud: input `events`, reference `price_list`, `provinces`; output `raw_archive` (Parquet) và `kpi_1min` (JSON tạm, chuyển sang SQL sau #35), cả hai vào container `lake` theo `<output>/yyyy/MM/dd/HH`. Đổi tên alias trong query thì phải đổi cả trong Terraform. Cách bật/tắt job xem `infra/README.md`.
