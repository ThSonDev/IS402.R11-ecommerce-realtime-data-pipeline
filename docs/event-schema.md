# Hợp đồng dữ liệu (data contract)

Phiên bản: v0 (bản nháp, chốt ở cuối tuần 1)

Tài liệu này mô tả hình dạng dữ liệu đi qua từng chặng của pipeline. Đây là "hợp đồng" giữa các thành viên: producer (Minh) sinh ra đúng format này, Stream Analytics (Thắng) đọc vào và ghi ra đúng format output, dashboard (Tuấn, Sơn) đọc output.

Muốn đổi bất kỳ trường nào thì mở PR sửa file này trước, báo cả nhóm, rồi mới sửa code. Mỗi lần đổi có ảnh hưởng thì tăng `schema_version`.

## 1. Event đầu vào (producer → Kafka / Event Hubs)

Mỗi message là một event JSON, mã hóa UTF-8. Một event tương ứng với một dòng của dataset REES46 sau khi làm giàu, hoặc một event giả lập do kịch bản chèn vào.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `schema_version` | int | có | Hiện tại là `1` |
| `event_id` | string (UUID) | có | Định danh duy nhất, dùng để dedup |
| `event_type` | string | có | `view`, `cart`, `purchase` |
| `event_time` | string (ISO 8601, UTC, có mili giây) | có | Thời điểm sự kiện xảy ra sau khi replay. Stream Analytics xử lý theo trường này (event time). Khi chạy live: tính từ giờ máy lúc bắt đầu replay, nên luôn là thời điểm hiện tại. Khi xuất file với mốc cố định (file mẫu): dịch +4h để cao điểm của dataset (08–10 UTC) rơi vào 19–21h giờ Việt Nam |
| `original_time` | string (ISO 8601, UTC) | có | Thời điểm gốc trong dataset, để truy vết |
| `sent_time` | string (ISO 8601, UTC, có mili giây) | có | Lúc producer gửi đi, dùng để đo độ trễ end-to-end |
| `user_id` | int64 | có | Từ dataset, hoặc ID giả cho bot / tài khoản ảo |
| `session_id` | string | có | Từ `user_session` của dataset |
| `order_id` | string | chỉ với `purchase` | Các purchase cùng session là một đơn, nên `order_id` sinh từ `session_id` |
| `device_id` | string | có | Giả lập, gắn theo user: `dev_` + 12 ký tự hex. Dùng 12 ký tự để 3.6 triệu user không bị trùng thiết bị (trùng thì luật 2 báo nhầm). Luật 2 dựa vào trường này |
| `is_new_account` | bool | có | Giả lập. Luật 2 dựa vào trường này |
| `product_id` | int64 | có | Từ dataset |
| `category_code` | string hoặc null | không | Từ dataset, thiếu khoảng 32% |
| `brand` | string hoặc null | không | Từ dataset, thiếu khoảng 14% |
| `price_vnd` | int64 | có | Giá dataset (USD) nhân tỷ giá cố định |
| `channel` | string | có | `tiki`, `shopee`, `lazada` |
| `province_code` | string | có | Mã 2–3 chữ cái tự đặt (`HCM`, `HN`, `DNG`...) của 34 tỉnh/thành mới. Danh sách đầy đủ duy nhất nằm trong `stream/reference/provinces.csv` |
| `payment_method` | string hoặc null | chỉ với `purchase` | `cod`, `momo`, `zalopay`, `card` |
| `voucher_code` | string hoặc null | không | Mã voucher nếu đơn có dùng |
| `is_fraud` | bool | có | Nhãn ground truth, chỉ dùng để đánh giá. Luật phát hiện không được đọc trường này |
| `scenario` | string hoặc null | có | `bot`, `multi_account`, `price_glitch`, `payment_outage` hoặc null |
| `is_late` | bool | có | `true` nếu event bị cố ý gửi trễ |

Ví dụ một event purchase:

```json
{
  "schema_version": 1,
  "event_id": "7f0c2a3e-5b1d-4c7e-9a52-1d2f3e4a5b6c",
  "event_type": "purchase",
  "event_time": "2026-11-11T13:15:03.120Z",
  "original_time": "2019-11-17T09:15:03Z",
  "sent_time": "2026-11-11T13:15:03.150Z",
  "user_id": 512386086,
  "session_id": "0f039697-fedc-40fa-8830-39c1e8a2b9d4",
  "order_id": "o_0f039697fedc",
  "device_id": "dev_8a41c2d93f07",
  "is_new_account": false,
  "product_id": 1004856,
  "category_code": "electronics.smartphone",
  "brand": "samsung",
  "price_vnd": 3319657,
  "channel": "shopee",
  "province_code": "HCM",
  "payment_method": "momo",
  "voucher_code": "FREESHIP",
  "is_fraud": false,
  "scenario": null,
  "is_late": false
}
```

Quy ước gửi:

- Topic / event hub tên `events`.
- Partition key là `user_id`. Như vậy các event của cùng một user nằm chung một partition, giữ đúng thứ tự cho luật 1.
- Số partition do Sơn chốt khi viết Terraform.
- Dữ liệu gốc phải dedup trước khi replay (có 100,519 dòng trùng hoàn toàn).
- Tỷ giá USD → VND là một hằng số cố định, ghi rõ nguồn và ngày lấy tỷ giá trong báo cáo.

Nhãn kịch bản và ground truth:

- Event do kịch bản `bot`, `multi_account`, `price_glitch` chèn vào có `is_fraud = true` và `scenario` đúng tên. User giả có `user_id` từ 900,000,000 trở lên (user thật tối đa 579,969,851).
- `payment_outage` không chèn event mà bỏ các purchase thật của một phương thức thanh toán trong một khoảng thời gian, nên không có event nào mang nhãn này. Ground truth của nó là khoảng thời gian.
- Mỗi lần chạy với `--scenarios`, producer ghi một file JSON ground truth (mặc định `data/scenario_logs/`, hoặc cạnh file `--out`): `replay_start`, khoảng dữ liệu gốc, `speed` / `rate`, và mảng `scenarios`, mỗi phần tử gồm `scenario`, `start`, `end` (ISO 8601 UTC trên trục `event_time`), `entity_type` (`user`, `device`, `product`, `system`), `entity_ids` (khớp `entity_id` của `alerts`), số event chèn (`events`), cùng `payment_method` và `dropped_purchases` với `payment_outage`. Chi tiết tham số xem `producer/README.md`.

## 2. Reference data (Blob, Stream Analytics join vào)

File CSV, nằm trong `stream/reference/`, đẩy lên Blob.

`price_list.csv`: giá tham chiếu ước tính của từng sản phẩm (không phải giá niêm yết chính thức), dùng cho luật 3.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `product_id` | int64 | |
| `ref_price_vnd` | int64 | Trung vị giá dương (VND) của sản phẩm trong cả tháng 11/2019, sau dedup |

`provinces.csv`: danh sách 34 tỉnh/thành, dùng cho bản đồ và RLS theo miền.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `province_code` | string | Mã 2–3 chữ cái tự đặt, duy nhất |
| `province_name` | string | Tên không dấu, bỏ "Tỉnh" / "Thành phố" (ví dụ `Ho Chi Minh`) |
| `region` | string | `bac`: Bắc Bộ đến Ninh Bình; `trung`: Thanh Hóa đến duyên hải Nam Trung Bộ và Tây Nguyên; `nam`: Đông Nam Bộ và Tây Nam Bộ |
| `population` | int64 | "Quy mô dân số" theo Nghị quyết của Quốc hội về sắp xếp đơn vị hành chính cấp tỉnh 2025, chỉ dùng làm trọng số khi gán tỉnh (xem `producer/README.md`) |

## 3. Output của Stream Analytics

Các schema dưới đây là hợp đồng output của Stream Analytics. Thời gian dùng UTC; JSON serialize thời gian theo ISO 8601. Kiểu logic `int64`, `float64`, `bool`, `string` và `datetime` ánh xạ trong Azure SQL lần lượt sang `bigint`, `float`, `bit`, `nvarchar` và `datetime2(3)`. `entity_id` và `event_id` của `alerts` cho phép `null` theo quy tắc dưới đây.

### `raw_archive`

Đích: ADLS Gen2, Parquet, chia thư mục theo ngày/giờ tại `raw_archive/yyyy/MM/dd/HH`. Mỗi dòng giữ nguyên toàn bộ trường payload của event ở phần 1 và thêm metadata nhận từ Event Hubs:

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| Tất cả cột trong phần 1 | như phần 1 | có theo quy định từng cột | Event gốc sau khi producer làm giàu |
| `EventEnqueuedUtcTime` | datetime (UTC) | có | Thời điểm Event Hubs nhận event; dùng đối chiếu độ trễ và truy vết |

Query phải chiếu metadata `EventEnqueuedUtcTime` tường minh từ input Event Hubs. `SELECT *` chỉ giữ các trường payload; khi thêm metadata, liệt kê cột tường minh để tránh cột trùng.

### `kpi_1min`

Đích: Azure SQL DB và Power BI real-time. Dùng tumbling window một phút theo `event_time`. Mỗi dòng đại diện cho một phút và một cặp `channel` × `province_code` xuất hiện trong input của cửa sổ; không tạo dòng cho cặp không có event:

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `window_end` | datetime (UTC) | có | Thời điểm kết thúc cửa sổ tumbling một phút |
| `channel` | string | có | Sàn bán hàng |
| `province_code` | string | có | Mã tỉnh/thành |
| `view_count` | int64 | có | Số event `view` trong cửa sổ |
| `cart_count` | int64 | có | Số event `cart` trong cửa sổ |
| `purchase_count` | int64 | có | Số event `purchase` trong cửa sổ |
| `order_count` | int64 | có | Số `order_id` khác nhau trong cửa sổ |
| `gmv_vnd` | int64 | có | Tổng `price_vnd` của event `purchase`, đơn vị VND |

### `alerts`

Đích: Azure SQL DB và Azure Function. Một dòng cho mỗi cảnh báo; `entity_id` rỗng khi cảnh báo áp dụng cho toàn hệ thống, còn `event_id` có thể rỗng nếu luật không gắn được một event đại diện:

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `alert_time` | datetime (UTC) | có | Thời điểm Stream Analytics phát cảnh báo |
| `rule_name` | string | có | Tên luật: `bot`, `multi_account`, `price_glitch` hoặc `payment_outage` |
| `entity_type` | string | có | Loại đối tượng: `user`, `device`, `product` hoặc `system` |
| `entity_id` | string hoặc null | có | ID đối tượng; null với `system` |
| `metric_name` | string | có | Tên chỉ số đã vượt điều kiện cảnh báo |
| `metric_value` | float64 | có | Giá trị đo được |
| `threshold` | float64 | có | Ngưỡng kích hoạt; với luật mô hình thống kê, mốc tham khảo ban đầu được lưu để hiển thị, còn điều kiện kích hoạt do kết quả mô hình quyết định |
| `event_id` | string (UUID) hoặc null | có | Event đại diện để truy vết; null nếu không có event đơn lẻ phù hợp |

### `pipeline_latency`

Đích: Azure SQL DB. Dùng tumbling window một phút theo `event_time`, một dòng mỗi cửa sổ. Các giá trị độ trễ là trung bình mili giây trên các event thuộc cửa sổ. `EventEnqueuedUtcTime` là lúc Event Hubs nhận event; `EventProcessedUtcTime` là lúc Stream Analytics xử lý event. Đây là metadata của input, không phải trường trong payload của producer. `avg_end_to_end_ms` kết thúc ở lúc ASA xử lý event; nó không đo thời gian ghi/commit vào output sink.

| Cột | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `window_end` | datetime (UTC) | có | Thời điểm kết thúc cửa sổ đo |
| `event_count` | int64 | có | Số event được tính trong cửa sổ |
| `avg_producer_to_eventhub_ms` | float64 | có | Trung bình từ `sent_time` đến `EventEnqueuedUtcTime` |
| `avg_eventhub_to_asa_ms` | float64 | có | Trung bình từ `EventEnqueuedUtcTime` đến thời điểm Stream Analytics xử lý event |
| `avg_end_to_end_ms` | float64 | có | Trung bình từ `sent_time` đến thời điểm Stream Analytics xử lý event |

## 4. Mô hình star schema (Synapse, cho Power BI lịch sử)

Bảng fact `fact_events`: mỗi dòng là một event, chứa khóa tới các dimension và các số đo (giá, cờ gian lận, cờ trễ).

Các bảng dimension:

- `dim_date`: ngày, giờ, ngày trong tuần
- `dim_product`: sản phẩm, danh mục cấp 1/2/3, brand
- `dim_channel`: sàn
- `dim_province`: tỉnh, miền
- `dim_payment`: phương thức thanh toán

Thêm bảng `fact_alerts` để báo cáo gian lận theo thời gian.

Chi tiết cột do Thắng chốt ở tuần 3, sau khi đã có dữ liệu thật trong `raw_archive`.
