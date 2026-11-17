# warehouse/ – Synapse serverless SQL

Phụ trách: Thắng

Chỉ dùng Synapse **serverless SQL pool**; không tạo dedicated pool. Database `megasale_warehouse` chỉ chứa metadata SQL, dữ liệu vẫn nằm trong ADLS.

Các file `.sql` được chạy theo thứ tự:

1. `00_create_database.sql` trên database `master` để tạo database metadata nếu chưa có.
2. `10_external.sql` trong `megasale_warehouse` để khai báo external data source `MegasaleLake` trỏ tới container `lake` và schema `silver`.
3. `20_silver.sql` trong `megasale_warehouse` để tạo view dữ liệu thô đã ép kiểu và view đã loại trùng.
4. `30_gold_star.sql` tạo các view `gold.dim_date`, `gold.dim_product`, `gold.dim_channel`, `gold.dim_province`, `gold.dim_payment`, và `gold.fact_events`.

`gold` dùng natural keys để giữ đây là các view không trạng thái trên serverless pool. `dim_province` đọc `reference/provinces.csv`; các dimension còn lại được suy ra từ event đã chuẩn hóa. `fact_events` giữ cột phân vùng ngày/giờ để người dùng có thể giới hạn truy vấn theo ngày.

`fact_alerts` chưa được tạo trong PR này: output `alerts` hiện đang đi vào Azure SQL DB, không có file alerts trong ADLS mà Synapse serverless có thể đọc. Cần một nguồn alerts trong lake hoặc một giải pháp tích hợp khác trước khi bổ sung view đúng contract. Không dùng view rỗng thay thế vì sẽ che giấu việc chưa có dữ liệu.

Chạy từ PowerShell ở thư mục gốc repo. Cần Azure CLI đăng nhập bằng Entra ID, quyền Synapse SQL, và quyền Storage Blob Data Reader trên các container `lake` và `reference`. Cần cài `sqlcmd` (`winget install Microsoft.Sqlcmd`):

```powershell
$server = "synw-megasale-dev-ondemand.sql.azuresynapse.net"
az login
.venv\Scripts\python scripts/deploy_sql.py --server $server
# Xem các lệnh sẽ chạy mà chưa kết nối cloud:
.venv\Scripts\python scripts/deploy_sql.py --server $server --dry-run
```

Script chạy các file `.sql` có tiền tố số theo thứ tự; file `00_create_database.sql` chạy trong `master`, các file còn lại trong `megasale_warehouse`. Dừng ngay khi `sqlcmd` báo lỗi. Có thể truyền `--sqlcmd` nếu executable không nằm trong PATH. Các file dùng `CREATE OR ALTER` hoặc kiểm tra metadata trước khi tạo để có thể chạy lại.

`silver.events_raw` đưa các giá trị năm/tháng/ngày/giờ từ đường dẫn thành cột phân vùng; lọc các cột này để giới hạn số file đọc. `silver.events` chuẩn hóa kiểu dữ liệu theo contract, loại các dòng thiếu `event_id` hoặc `event_time` hợp lệ, rồi giữ bản nhận mới nhất của mỗi `event_id`. Dòng không hợp lệ vẫn xem được trong `silver.events_raw` để điều tra. Do view silver deduplicate toàn lịch sử, các truy vấn đo theo một run nên lọc `silver.events_raw` theo phân vùng trước rồi mới `ROW_NUMBER()` trên phần dữ liệu đã lọc; outer filter trên `silver.events` có thể không giảm lượng file được quét.

Đếm toàn bộ event duy nhất sau dedup:

```sql
SELECT COUNT_BIG(*) AS event_count
FROM silver.events
```

Ví dụ đếm run ngày 15/11/2026, giờ UTC 09:00. `silver.events_raw` giữ bản ghi trùng; lọc view theo phân vùng đường dẫn giúp giới hạn phạm vi file đọc:

```sql
SELECT COUNT_BIG(*) AS raw_event_count
FROM silver.events_raw
WHERE partition_year = 2026
  AND partition_month = 11
  AND partition_day = 15
  AND partition_hour = 9;
```

Kiểm chứng cloud ngày 17/11/2026: producer ghi nhận gửi 108,735 event trong run này; truy vấn phân vùng cho 108,735 dòng thô, 108,735 `event_id` khác nhau và view `silver.events` cũng có 108,735 dòng. Không có dòng thiếu ID/thời gian hoặc lỗi chuẩn hóa thời gian trong run đó. Toàn bộ lake hiện có 169,736 dòng thô và 127,736 ID khác nhau do chứa nhiều lần replay/test; vì vậy chỉ so sánh số đếm theo run/phân vùng tương ứng, không so tổng lịch sử với một lượt producer.
