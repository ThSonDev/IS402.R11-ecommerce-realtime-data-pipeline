# dashboards/powerbi/ – Business dashboard

Phụ trách: Tuấn

Lưu report dưới dạng **PBIP** (Power BI Project, thư mục file text, diff được), không commit `.pbix`. Gồm 1 dashboard real-time (streaming tile) và report lịch sử 4 trang có navigation, RLS và mobile layout.

## Nội dung hiện có

| Đường dẫn | Là gì |
|---|---|
| `METRICS.md` | Danh sách KPI kèm công thức DAX và bố cục 4 trang báo cáo |
| `sketch/` | Ảnh phác thảo bố cục 4 trang |
| `megasale-report.pbip` | Project Power BI mở bằng Power BI Desktop: báo cáo lịch sử 4 trang trên dữ liệu thật (issue #65) |

## Báo cáo lịch sử (4 trang)

| Trang | Nội dung |
|---|---|
| 1. Tổng quan | GMV, số đơn, AOV, tỷ lệ chuyển đổi, GMV theo thời gian và theo sàn |
| 2. Sản phẩm và danh mục | Cơ cấu GMV theo danh mục (bấm xuống cấp 2), top 10 brand, top 10 sản phẩm |
| 3. Sàn và tỉnh | Bản đồ GMV theo tỉnh, bảng GMV theo sàn và miền |
| 4. Gian lận và sự cố | Đơn gian lận, số cảnh báo của hệ thống, so sánh gian lận thực tế với cảnh báo theo loại |

Có nút chuyển giữa 4 trang. Bộ lọc thời gian, sàn, danh mục dùng chung giữa các trang.

## Nguồn dữ liệu

| Nguồn | Máy chủ | Database | Dùng cho |
|---|---|---|---|
| Synapse serverless, schema `gold` | `synw-megasale-dev-ondemand.sql.azuresynapse.net` | `megasale_warehouse` | Toàn bộ báo cáo (star schema) |
| Azure SQL, bảng `dbo.alerts` | `sql-megasale-dev.database.windows.net` | `sqldb-megasale-dev` | Trang 4 (cảnh báo của 4 luật) |

Cả hai đều đăng nhập bằng Microsoft account của trường (Entra ID), không có mật khẩu SQL. Truy cập `gold` cần quyền Synapse (xem `warehouse/README.md`); Azure SQL cần được Sơn thêm người dùng vào database.

## Cách mở

1. Cần Power BI Desktop, bật tính năng Power BI Project (.pbip) trong Options → Preview features.
2. Mở `megasale-report.pbip`.
3. Khi hỏi đăng nhập, chọn **Microsoft account** và dùng tài khoản trường. Chọn **Refresh** để nạp dữ liệu.
4. Bản đã publish nằm ở workspace `Megasale-powerBI` (báo cáo `megasale-report`).

## Lưu ý

- `.pbi/cache.abf` và `.pbi/localSettings.json` bị `.gitignore` chặn (cache hơn 100 MB, không đưa lên git).
- Bản đồ tỉnh dùng visual bản đồ cũ của Power BI, Microsoft đã báo sẽ ngừng. Tên tỉnh Quảng Ninh được định vị bằng tọa độ vì tên bị nhận nhầm sang Trung Quốc (xem cột `Lat`, `Lon` của `gold dim_province`).
- Trang 4: `alerts` không nối với `fact_events` (không có `order_id`), nên bộ lọc thời gian và sàn không tác động lên số cảnh báo.
