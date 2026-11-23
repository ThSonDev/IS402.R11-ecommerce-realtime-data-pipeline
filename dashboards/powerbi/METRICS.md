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
Rule Alerts = CALCULATE(DISTINCTCOUNT(alerts[entity_id]), alerts[rule_name] = SELECTEDVALUE(Loai[Loai]))
```

## 3. Bốn trang báo cáo

Tên trang và bộ lọc theo `plan/Tuan.md`. Các biểu đồ cụ thể là đề xuất của Tuấn, chỉnh được khi dựng.

### Trang 1. Tổng quan
- Thẻ số: GMV, số đơn, AOV, tỷ lệ chuyển đổi.
- Biểu đồ cột: GMV và số đơn theo ngày (`dim_date.calendar_date`).
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
- Thẻ số: số đơn gắn cờ gian lận, tỷ lệ đơn gian lận (`is_fraud`), số cảnh báo phát hiện (đếm dòng `dbo.alerts`), số event đến trễ.
- Bảng danh sách cảnh báo từ `dbo.alerts`: `alert_time`, `rule_name`, `entity_id`, `metric_value`.
- Biểu đồ so sánh theo loại (`bot`, `multi_account`, `price_glitch`, `payment_outage`), hai cột cạnh nhau: "Đơn gian lận (nhãn)" (`is_fraud` theo `scenario` từ `fact_events`) và "Đối tượng bị cảnh báo" (số `entity_id` khác nhau trong `dbo.alerts` theo `rule_name`). `alerts` không có `order_id` nên so số lượng theo loại, không so từng đơn.
- Số event đến trễ (`is_late`).
- Lưu ý: `is_fraud` và `scenario` là nhãn đúng (ground truth) do producer tạo ra để chấm điểm, không phải kết quả của 4 luật. `payment_outage` không gắn nhãn trên từng event (chỉ có khoảng thời gian), nên cột gian lận thực tế của loại này để trống; trang có ghi chú điều này.

Điều hướng: có nút chuyển giữa 4 trang trên mọi trang. Bộ lọc thời gian, sàn, danh mục là slicer dùng chung giữa các trang (Sync slicers). Bấm vào một biểu đồ thì các biểu đồ cùng trang lọc theo (Edit interactions).

## 4. Dashboard real-time (Power BI Service)
- Nguồn: dataset `megasale_kpi_1min`, bảng `kpi_1min`, workspace `Megasale-powerBI`. Dataset đã có dữ liệu thật.
- Mỗi dòng `kpi_1min` là một sàn x một tỉnh x một phút (khoảng 100 dòng mỗi phút). Tile streaming chỉ hiện dòng mới nhất nên không cộng được. Vì vậy các tile được dựng từ báo cáo `megasale-realtime` (có phép Sum) rồi ghim lên dashboard "Megasale Realtime".
- Tile: Tổng số đơn (`order_count`), Tổng GMV (`gmv_vnd`), Số đơn theo phút (theo `window_end`), GMV theo sàn (theo `channel`).
- Có bố cục mobile cho dashboard.
- Kết quả thử 23/11/2026: khi producer chạy, tile tăng không cần làm mới (Tổng số đơn 10.515K lên 10.633K, GMV 94,80 lên 95,80 tỷ). ASA gom theo cửa sổ 1 phút nên số cập nhật theo phút. Trục thời gian hiển thị giờ UTC (giờ Việt Nam = UTC + 7).
- Lưu ý: tính năng real-time streaming của Power BI được Microsoft thông báo ngừng (mốc 31/10/2027). Vẫn dùng cho đồ án, sẽ ghi chú trong báo cáo.

## 5. Phân quyền (RLS), chia sẻ và mobile
- 6 vai trò RLS trên semantic model `megasale-report`: `Shopee`, `Tiki`, `Lazada` lọc `gold dim_channel[channel]` bằng `shopee`, `tiki`, `lazada`; `Bac`, `Trung`, `Nam` lọc `gold dim_province[region]` bằng `bac`, `trung`, `nam`.
- Bảng `alerts` không có cột sàn hay miền nên RLS không lọc được, trang 4 luôn hiện toàn bộ cảnh báo.
- RLS chỉ áp cho người có quyền Viewer. Admin, Member, Contributor luôn thấy hết, nên kiểm tra bằng View as role (Desktop) hoặc Test as role (Service).
- Power BI App "Megasale Dashboard" gồm báo cáo `megasale-report` và dashboard "Megasale Realtime"; người xem chỉ có quyền xem. Sau mỗi lần publish lại báo cáo phải bấm Update app.
- Bố cục mobile làm cho cả 4 trang (View, Mobile layout): thẻ số xếp dọc, bảng cho vuốt ngang.
