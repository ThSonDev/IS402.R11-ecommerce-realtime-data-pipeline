# dashboards/grafana/ – War room (ops)

Phụ trách: Sơn

Grafana OSS chạy bằng Docker, đọc từ Azure SQL Database. Data source, dashboard (JSON) và alert rule được nạp tự động qua `provisioning/`, không tạo bằng tay trên giao diện.
