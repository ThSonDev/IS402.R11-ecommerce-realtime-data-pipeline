# Kiểm chứng chính sách event-time của ASA (#37)

## Quyết định cấu hình

Cloud job dùng `TIMESTAMP BY event_time` với các giá trị trong `infra/stream_analytics.tf`:

- Late-arrival tolerance: **60 giây**.
- Out-of-order tolerance: **60 giây**, policy **Adjust**.

Hai ngưỡng 60 giây cho ASA thời gian nhận các event trễ/sai thứ tự đã dùng trong bài thử. Theo kết quả Sơn kiểm tra sau khi #82 merge, bài chạy với `--late-rate 0.05` cho KPI khớp khi đối chiếu với `raw_archive` theo `event_time`, và `DroppedOrAdjustedEvents = 0`. Vì vậy phép thử không ghi nhận event bị drop hoặc timestamp bị điều chỉnh trong batch đó. Trường payload `event_time` vẫn được giữ trong raw để đối chiếu.

## Kết quả chạy cloud

Đã chạy baseline `main` tại commit `c74ce16` trong một lượt test ngày 17/11/2026. Event Hubs là Standard 1 TU, ASA là 1/3 SU. Sau khi test, ASA được dừng và Event Hubs được destroy theo `infra/README.md`.

### Throughput / #30

Producer gửi bốn đợt riêng, mỗi đợt 10,000 event với cùng lát dữ liệu, ở các tốc độ yêu cầu sau:

| Tốc độ yêu cầu | Tốc độ đo trong tiến trình | Failed | Not delivered |
|---:|---:|---:|---:|
| 500 event/s | 493 event/s | 0 | 0 |
| 1,000 event/s | 979 event/s | 0 | 0 |
| 1,500 event/s | 1,451 event/s | 0 | 0 |
| 2,000 event/s | 1,922 event/s | 0 | 0 |

Đây là các đợt ngắn có giới hạn 10,000 event, không phải phép đo tải bền vững. Cùng một lát dữ liệu được replay lại ở mỗi đợt; các event ID trùng giữa các đợt là chủ ý của benchmark.

### Lake outputs / #36 baseline

Sau bốn đợt benchmark và đợt trễ bên dưới, kiểm tra các partition giờ 17 và 18 UTC cho thấy **42,000 Parquet rows** trong `raw_archive`, gồm **102 rows** có `is_late=true`. File `kpi_1min` có **413 JSON rows**; tổng các cột view/cart/purchase lần lượt là **40,311 / 768 / 921**, bằng 42,000 event. Tất cả JSON rows có cùng schema KPI.

Baseline `main` chỉ có `raw_archive` và `kpi_1min`; lượt chạy này không kiểm chứng `pipeline_latency`, SQL hay Power BI của #36. Các sink đó nằm trong PR #82.

### Late / out-of-order test / #37

Đợt kiểm tra baseline gửi **2,000 event**, đặt `--late-rate 0.05 --late-delay 60`; producer đánh dấu và giữ trễ **102 event** (5.1%), sau đó giao đủ cả 2,000 event, không lỗi và không còn event chưa giao. Lake giữ đủ 102 event với `is_late=true`.

Lượt baseline này dùng query trước #82, với late-arrival tolerance 5 giây và out-of-order tolerance 0 giây. Metrics ghi nhận `LateInputEvents=204` và `DroppedOrAdjustedEvents=16`; `Errors` và `DeserializationError` không khác 0. Do query baseline đọc `[events]` ở hai nhánh, không xem 204 là số event late duy nhất. Đây là số liệu lịch sử của cấu hình cũ, không phải kết quả của cấu hình 60/60 hiện tại.

`DroppedOrAdjustedEvents` gộp event bị loại và event được điều chỉnh nên không cho biết riêng từng loại. Bài chạy sau #82 nêu ở phần quyết định cấu hình đã ghi nhận chỉ số này bằng 0.

## Kiểm chứng local

Ngày 17/11/2026, chạy `stream/query.asaql` trong VS Code ASA Tools bằng **Local input and local output** với file replay do `prepare_local_events.ps1` tạo. Job dừng bình thường sau 40 giây và tạo đủ output.

- `verify_local_kpi.ps1`: **1,036 input events**, **580/580 nhóm phút × sàn × tỉnh**, **0 mismatch**; 995 view, 16 cart, 25 purchase, GMV `177,062,417` VND.
- Ba output `kpi_1min`, `kpi_1min_sql`, `kpi_1min_powerbi` đều có 580 dòng giống hệt nhau; `gmv_vnd` được serialize dưới dạng integer.
- `raw_archive`: 1,036 dòng. `pipeline_latency`: 31 window, tổng `event_count` là 1,036.
- ASA Tools cảnh báo time policy không được hỗ trợ với static input. Do input local không có Event Hubs metadata, các trường enqueued/processed time và latency tương ứng là null; phần này chỉ được xác minh bằng cloud run.

Terraform CLI **1.17.2**: `terraform fmt -check`, `terraform init -backend=false` và `terraform validate` đều thành công. Python test: **27 passed**; Ruff: **All checks passed**.

## Giới hạn của phép đo

- Mẫu throughput ngắn, chỉ chứng minh producer giao được các đợt đã thử; không xác định giới hạn sustained của Event Hubs hoặc ASA.
- Các số throughput và lake output cloud ở trên lấy từ baseline `main`; baseline đó không có SQL/Power BI/`pipeline_latency` sink. Bài kiểm tra event-time sau #82 dùng query đã cập nhật.
- Local run kiểm tra kết quả query và hình dạng dữ liệu, không kiểm chứng việc ghi thật vào SQL hoặc Power BI.
- `LateInputEvents=204` và `DroppedOrAdjustedEvents=16` là số liệu lịch sử từ baseline trước #82, không dùng để đánh giá cấu hình 60/60. Bài chạy sau #82 được Sơn báo cáo có `DroppedOrAdjustedEvents = 0`; log batch chi tiết chưa được lưu cùng tài liệu này.
