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
| `event_time` | string (ISO 8601, UTC, có mili giây) | có | Thời điểm sự kiện xảy ra sau khi replay. Stream Analytics xử lý theo trường này (event time) |
| `original_time` | string (ISO 8601, UTC) | có | Thời điểm gốc trong dataset, để truy vết |
| `sent_time` | string (ISO 8601, UTC, có mili giây) | có | Lúc producer gửi đi, dùng để đo độ trễ end-to-end |
| `user_id` | int64 | có | Từ dataset, hoặc ID giả cho bot / tài khoản ảo |
| `session_id` | string | có | Từ `user_session` của dataset |
| `order_id` | string | chỉ với `purchase` | Các purchase cùng session là một đơn, nên `order_id` sinh từ `session_id` |
| `device_id` | string | có | Giả lập, gắn theo user. Luật 2 dựa vào trường này |
| `is_new_account` | bool | có | Giả lập. Luật 2 dựa vào trường này |
| `product_id` | int64 | có | Từ dataset |
| `category_code` | string hoặc null | không | Từ dataset, thiếu khoảng 32% |
| `brand` | string hoặc null | không | Từ dataset, thiếu khoảng 14% |
| `price_vnd` | int64 | có | Giá dataset (USD) nhân tỷ giá cố định |
| `channel` | string | có | `tiki`, `shopee`, `lazada` |
| `province_code` | string | có | Mã tỉnh trong danh sách 34 tỉnh/thành mới (xem reference data) |
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
  "original_time": "2019-11-17T05:15:03Z",
  "sent_time": "2026-11-11T13:15:03.150Z",
  "user_id": 512386086,
  "session_id": "0f039697-fedc-40fa-8830-39c1e8a2b9d4",
  "order_id": "o_0f039697fedc",
  "device_id": "dev_8a41c2",
  "is_new_account": false,
  "product_id": 1004856,
  "category_code": "electronics.smartphone",
  "brand": "samsung",
  "price_vnd": 3210500,
  "channel": "shopee",
  "province_code": "HCM",
  "payment_method": "momo",
  "voucher_code": "MEGA1111",
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

## 2. Reference data (Blob, Stream Analytics join vào)

File CSV, nằm trong `stream/reference/`, đẩy lên Blob.

`price_list.csv`: giá niêm yết của từng sản phẩm, dùng cho luật 3.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `product_id` | int64 | |
| `list_price_vnd` | int64 | Gợi ý: trung vị giá của sản phẩm trong cả tháng |

`provinces.csv`: danh sách 34 tỉnh/thành, dùng cho bản đồ và RLS theo miền.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `province_code` | string | |
| `province_name` | string | Tên tiếng Việt có dấu |
| `region` | string | `bac`, `trung`, `nam` |
| `population` | int64 | Lấy từ nguồn chính thức, dùng làm trọng số khi gán tỉnh |

## 3. Output của Stream Analytics

Phần này sẽ được chốt chi tiết ở tuần 2. Hiện chỉ cố định tên và ý nghĩa để Tuấn và Sơn bắt đầu thiết kế dashboard.

| Output | Đích | Nội dung |
|---|---|---|
| `raw_archive` | ADLS Gen2, Parquet, chia thư mục theo ngày/giờ | Toàn bộ event, thêm thời điểm Event Hubs nhận (`EventEnqueuedUtcTime`). Nguồn cho Synapse và Power BI lịch sử |
| `kpi_1min` | Azure SQL DB và Power BI streaming | Mỗi phút, theo `channel` × `province_code`: số view, cart, purchase, số đơn, GMV |
| `alerts` | Azure SQL DB và Azure Function | Mỗi cảnh báo của 4 luật: thời điểm, tên luật, đối tượng (user / device / product / toàn hệ thống), giá trị đo được, ngưỡng, `event_id` mẫu |
| `pipeline_latency` | Azure SQL DB | Độ trễ theo cửa sổ: từ `sent_time` đến lúc Event Hubs nhận và lúc Stream Analytics xuất kết quả |

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
