# dashboards/grafana/ – War room (ops)

Phụ trách: Sơn

Grafana OSS (bản Windows, chạy dạng service) đọc Azure SQL Database. Data source, dashboard và contact point Telegram nạp tự động từ thư mục này (provisioning), không tạo tay trên giao diện.

| Đường dẫn | Nội dung |
|---|---|
| `provisioning/datasources/megasale-sql.yaml` | Data source `megasale-sql`: Azure SQL, đăng nhập Entra bằng app chỉ đọc `grafana-megasale-reader` |
| `provisioning/dashboards/megasale.yaml` | Nạp mọi dashboard trong `dashboards/` vào folder `Megasale` |
| `provisioning/alerting/` | Contact point `telegram-oncall` (chung bot với Function) và alert rule |
| `dashboards/war-room.json` | Dashboard `Mega Sale war room`: GMV, đơn, phễu, top tỉnh, độ trễ pipeline, bảng cảnh báo mới nhất và số cảnh báo theo luật (từ `dbo.alerts`, chỉ hiển thị, không gửi Telegram) |
| `setup-windows.ps1` | Cài một lần: bật Azure auth, trỏ provisioning vào repo, nạp secret từ `.env` vào service |

## Cài đặt (một lần)

Cần Grafana OSS cho Windows (đã thử 13.3.1) và `.env` có `GRAFANA_SQL_TENANT_ID`, `GRAFANA_SQL_CLIENT_ID`, `GRAFANA_SQL_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Mở PowerShell **Run as administrator** ở thư mục gốc repo:

```powershell
powershell -ExecutionPolicy Bypass -File dashboards\grafana\setup-windows.ps1
# Cài Grafana ở chỗ khác: thêm -GrafanaHome "C:\Program Files\GrafanaLabs\grafana"
```

Mở http://localhost:3000 (lần đầu `admin` / `admin`, đổi mật khẩu). Đổi secret trong `.env` thì chạy lại script.

## Dùng hằng ngày

Service để **Manual**: Grafana đang chạy sẽ truy vấn SQL liên tục, DB free không auto-pause được và tốn hạn mức vCore-giây miễn phí của tháng.

```powershell
Start-Service Grafana   # trước buổi test/demo (PowerShell admin)
Stop-Service Grafana    # sau buổi
```

SQL DB đang ngủ thì truy vấn đầu báo lỗi "not currently available", chờ khoảng 1 phút rồi refresh.

## Sửa dashboard / alert

- Dashboard: sửa trên giao diện → Save → **Export → Export as JSON** (tắt "Export for sharing externally") → ghi đè `dashboards/war-room.json` → commit.
- Alert rule: tạo trên giao diện → **Alerting → Alert rules → More → Export** dạng YAML → lưu vào `provisioning/alerting/` → commit. Sau khi đã có file, rule thành bản provisioning, chỉ sửa bằng file.
