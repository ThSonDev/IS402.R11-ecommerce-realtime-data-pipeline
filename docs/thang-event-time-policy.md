# Kiểm chứng chính sách event-time của ASA (#37)

## Quyết định cấu hình

Cloud job dùng `TIMESTAMP BY event_time` với các giá trị trong `infra/stream_analytics.tf`:

- Late-arrival tolerance: **5 giây**. Giữ ngắn để output theo cửa sổ một phút sớm; late event ngoài ngưỡng được điều chỉnh theo chính sách mặc định của ASA (Adjust), không bị loại bỏ.
- Out-of-order tolerance: **0 giây**, policy **Adjust**. Không đệm để đợi sắp xếp lại; event nằm sau watermark được giữ nhưng thời gian ASA dùng cho window có thể đổi.

Với event được điều chỉnh, `System.Timestamp()` phản ánh thời gian ASA gán cho việc xử lý/window. Trường payload `event_time` vẫn giữ nguyên giá trị producer gửi. Vì vậy, dashboard KPI phản ánh event-time sau chính sách ASA; dữ liệu thô giữ lại giá trị gốc để truy vết.

## Kết quả chạy cloud

Đã chạy baseline `main` tại commit `c74ce16` trong một lượt test ngày 17/11/2026. Event Hubs là Standard 1 TU, ASA là 1/3 SU. Sau khi test, ASA được dừng và Event Hubs được destroy theo `infra/README.md`.

### Throughput / #30

Producer gửi bốn đợt riêng, mỗi đợt 10.000 event với cùng lát dữ liệu, ở các tốc độ yêu cầu sau:

| Tốc độ yêu cầu | Tốc độ đo trong tiến trình | Failed | Not delivered |
|---:|---:|---:|---:|
| 500 event/s | 493 event/s | 0 | 0 |
| 1.000 event/s | 979 event/s | 0 | 0 |
| 1.500 event/s | 1.451 event/s | 0 | 0 |
| 2.000 event/s | 1.922 event/s | 0 | 0 |

Đây là các đợt ngắn có giới hạn 10.000 event, không phải phép đo tải bền vững. Cùng một lát dữ liệu được replay lại ở mỗi đợt; các event ID trùng giữa các đợt là chủ ý của benchmark.

### Lake outputs / #36 baseline

Sau bốn đợt benchmark và đợt trễ bên dưới, kiểm tra các partition giờ 17 và 18 UTC cho thấy **42.000 Parquet rows** trong `raw_archive`, gồm **102 rows** có `is_late=true`. File `kpi_1min` có **413 JSON rows**; tổng các cột view/cart/purchase lần lượt là **40.311 / 768 / 921**, bằng 42.000 event. Tất cả JSON rows có cùng schema KPI.

Baseline `main` chỉ có `raw_archive` và `kpi_1min`; lượt chạy này không kiểm chứng `pipeline_latency`, SQL hay Power BI của #36. Các sink đó nằm trong PR #82.

### Late / out-of-order test / #37

Đợt kiểm tra cuối gửi **2.000 event**, đặt `--late-rate 0.05 --late-delay 60`; producer đánh dấu và giữ trễ **102 event** (5,1%), sau đó giao đủ cả 2.000 event, không lỗi và không còn event chưa giao. Lake giữ đủ 102 event với `is_late=true`.

ASA metrics trong lượt chạy ghi nhận `LateInputEvents=204` và `DroppedOrAdjustedEvents=16`; metric `Errors` và `DeserializationError` không có giá trị khác 0. Số `LateInputEvents` lớn hơn 102 event late trong lake; baseline `main` tham chiếu `[events]` trong hai câu `FROM` riêng nên hai nhánh có thể cùng góp vào metric. Chưa coi 204 là số event late duy nhất; cần đối chiếu lại khi chạy query một input sau khi PR #82 được triển khai.

`DroppedOrAdjustedEvents` là metric cho event sai thứ tự bị loại hoặc điều chỉnh; job cấu hình `Adjust`. Số liệu xác nhận chính sách đã có tác dụng trên cloud, nhưng muốn định lượng chính xác trên query một nhánh sau khi PR #82 merge thì cần chạy lại cùng batch với cấu hình đó.

## Giới hạn của phép đo

- Mẫu throughput ngắn, chỉ chứng minh producer giao được các đợt đã thử; không xác định giới hạn sustained của Event Hubs hoặc ASA.
- Cloud run dùng `main` theo yêu cầu. Không có SQL/Power BI/`pipeline_latency` sink trên baseline đó.
- Local ASA Tools và Terraform CLI không được cài trên máy tại lượt kiểm tra; project pytest 27/27 pass và script chuẩn bị local replay tạo được đủ 1.036 event, nhưng không chạy được ASA local simulator.
