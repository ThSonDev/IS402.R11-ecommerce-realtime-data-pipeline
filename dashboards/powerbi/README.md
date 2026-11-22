# dashboards/powerbi/ – Business dashboard

Phụ trách: Tuấn

Lưu report dưới dạng **PBIP** (Power BI Project, thư mục file text, diff được), không commit `.pbix`. Gồm 1 dashboard real-time (streaming tile) và report lịch sử ≥4 trang có navigation, RLS và mobile layout.

## Nội dung hiện có

| Đường dẫn | Là gì |
|---|---|
| `METRICS.md` | Danh sách KPI kèm công thức và bố cục 4 trang báo cáo |
| `sketch/` | Ảnh phác thảo bố cục 4 trang |
| `megasale-report.pbip` | Project Power BI mở bằng Power BI Desktop (bản thử trên dữ liệu mẫu, issue #41) |

## Cách mở bản thử

1. Cần Power BI Desktop, bật tính năng Power BI Project (.pbip) trong Options → Preview features.
2. Mở `megasale-report.pbip`.
3. Nguồn dữ liệu là `data/events_1day.csv` (1 ngày dữ liệu mẫu do Minh gửi, không có trong git). Đặt file vào `data/` của repo rồi chọn Transform data → Data source settings, trỏ lại đúng đường dẫn trên máy.

## Lưu ý

- `.pbi/cache.abf` và `.pbi/localSettings.json` bị `.gitignore` chặn (cache hơn 100 MB, không đưa lên git).
