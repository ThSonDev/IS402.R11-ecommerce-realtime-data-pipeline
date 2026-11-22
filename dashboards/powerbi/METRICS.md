# Chỉ số và bố cục báo cáo Power BI

Phục vụ issue #39 (danh sách KPI kèm công thức) và #40 (phác thảo 4 trang).

Tên cột lấy từ `docs/event-schema.md`. Tên bảng star schema lấy từ `warehouse/30_gold_star.sql` (schema `gold`). Trong Power BI các bảng này hiện tên có tiền tố `gold` (ví dụ `gold fact_events`); DAX bên dưới viết ngắn gọn là `fact_events`.

## 1. Các nguồn dữ liệu của Power BI

| Nguồn | Dùng cho | Có gì |
|---|---|---|
| Synapse gold views (lịch sử) | Báo cáo 4 trang | `fact_events` (mỗi dòng một event), `dim_date`, `dim_product`, `dim_channel`, `dim_province`, `dim_payment` |
| Azure SQL DB `sqldb-megasale-dev` trên server `sql-megasale-dev.database.windows.net`, bảng `dbo.alerts` (đăng nhập Entra) | Trang 4: cảnh báo thật của 4 luật | `alert_time`, `rule_name` (`bot`, `multi_account`, `price_glitch`, `payment_outage`), `entity_type`, `entity_id`, `metric_name`, `metric_value`, `threshold`, `event_id` |
| Dataset streaming `megasale_kpi_1min` (real-time) | Dashboard real-time | Bảng `kpi_1min`: mỗi phút theo sàn × tỉnh có `window_end`, `channel`, `province_code`, `view_count`, `cart_count`, `purchase_count`, `order_count`, `gmv_vnd` |

Giờ trong dữ liệu là UTC. Giờ Việt Nam = UTC + 7.

## 2. Danh sách chỉ số

| Chỉ số | Cách tính | Cột dùng | Nguồn |
|---|---|---|---|
| GMV | Tổng `price_vnd` của event `purchase` | `price_vnd`, `event_type` | `fact_events` |
| Số đơn | Đếm `order_id` khác nhau của event `purchase` | `order_id` | `fact_events` |
| Giá trị trung bình mỗi đơn (AOV) | GMV / số đơn | | `fact_events` |
| Tỷ lệ chuyển đổi | Số session có `purchase` / số session có `view` | `session_id`, `event_type` | `fact_events` |
| Tỷ lệ đơn bị gắn cờ gian lận | Số đơn có `is_fraud = true` / tổng số đơn | `is_fraud`, `order_id` | `fact_events` |

Real-time (`kpi_1min`) chỉ có số view, cart, purchase, số đơn và GMV mỗi phút. Dataset này **không có `session_id`**, nên tỷ lệ chuyển đổi chỉ tính được ở báo cáo lịch sử.

DAX đã dùng trong báo cáo (rút gọn tên bảng):

```dax
GMV = CALCULATE(SUM(fact_events[price_vnd]), fact_events[event_type] = "purchase")
Orders = CALCULATE(DISTINCTCOUNT(fact_events[order_id]), fact_events[event_type] = "purchase")
AOV = DIVIDE([GMV], [Orders])
Fraud Orders = CALCULATE(DISTINCTCOUNT(fact_events[order_id]), fact_events[event_type] = "purchase", fact_events[is_fraud] = TRUE())
Fraud Order Rate = DIVIDE([Fraud Orders], [Orders])
Sessions Viewed = CALCULATE(DISTINCTCOUNT(fact_events[session_id]), fact_events[event_type] = "view")
Sessions Purchased = CALCULATE(DISTINCTCOUNT(fact_events[session_id]), fact_events[event_type] = "purchase")
Conversion Rate = DIVIDE([Sessions Purchased], [Sessions Viewed])
Late Events = CALCULATE(COUNTROWS(fact_events), fact_events[is_late] = TRUE())
Alerts Count = COUNTROWS(alerts)
```

## 3. Bốn trang báo cáo

Tên trang và bộ lọc theo `plan/Tuan.md`. Các biểu đồ cụ thể là đề xuất của Tuấn, chỉnh được khi dựng.

### Trang 1. Tổng quan
- Thẻ số: GMV, số đơn, AOV, tỷ lệ chuyển đổi.
- Biểu đồ đường: GMV và số đơn theo thời gian (`dim_date`).
- Biểu đồ cột: GMV theo sàn (`dim_channel`).
- Bộ lọc: thời gian, sàn, danh mục.

### Trang 2. Sản phẩm và danh mục
- Cơ cấu GMV theo danh mục dạng thanh ngang (`dim_product.category_level_1`), bấm xuống được `category_level_2`. Giá trị rỗng hiển thị là "Chưa phân loại", không lọc bỏ.
- Top 10 brand và top 10 sản phẩm theo GMV.
- Bộ lọc: thời gian, sàn, danh mục.

### Trang 3. Sàn × tỉnh (bản đồ)
- Bản đồ tỉnh theo GMV (`dim_province.province_name`).
- Bảng GMV theo sàn và miền (`dim_province.region`: `bac`, `trung`, `nam`).
- Bộ lọc: thời gian, sàn.

### Trang 4. Gian lận và sự cố
- Số đơn bị gắn cờ gian lận và tỷ lệ theo thời gian (`is_fraud`).
- Thẻ số: số cảnh báo phát hiện (đếm dòng `dbo.alerts`).
- Biểu đồ so sánh theo loại (`bot`, `multi_account`, `price_glitch`, `payment_outage`), hai cột cạnh nhau: gian lận thực tế (`is_fraud` theo `scenario` từ `fact_events`) và hệ thống phát hiện (`dbo.alerts` theo `rule_name`). Cho thấy hệ thống phát hiện được bao nhiêu so với gian lận thực tế. `alerts` không có `order_id` nên so số lượng theo loại, không so từng đơn.
- Số event đến trễ (`is_late`).
- Lưu ý: `is_fraud` và `scenario` là nhãn đúng (ground truth) do producer tạo ra để chấm điểm, không phải kết quả của 4 luật. `payment_outage` không gắn nhãn trên từng event (chỉ có khoảng thời gian), nên cột gian lận thực tế của loại này để trống; trang có ghi chú điều này.

Điều hướng: có nút chuyển giữa 4 trang trên mọi trang. Bộ lọc thời gian, sàn, danh mục là slicer dùng chung giữa các trang (Sync slicers). Bấm vào một biểu đồ thì các biểu đồ cùng trang lọc theo (Edit interactions).

## 4. Dashboard real-time (Power BI Service)
- Nguồn: dataset `megasale_kpi_1min`, bảng `kpi_1min`, workspace `Megasale-powerBI`. Dataset đã có dữ liệu thật.
- Tile: số đơn mỗi phút, GMV, so sánh theo sàn.
- Có bố cục mobile.
- Lưu ý: tính năng real-time streaming của Power BI được Microsoft thông báo ngừng (mốc 31/10/2027). Vẫn dùng cho đồ án, sẽ ghi chú trong báo cáo.
