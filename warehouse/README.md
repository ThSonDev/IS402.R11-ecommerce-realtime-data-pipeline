# warehouse/ – Synapse serverless SQL

Phụ trách: Thắng

File `.sql` đánh số theo thứ tự chạy: `10_external.sql` (nguồn ngoài trỏ vào Parquet trên ADLS), `20_silver.sql` (làm sạch, dedup), `30_gold_star.sql` (star schema cho Power BI). Deploy bằng script trong `scripts/`.

Chỉ dùng serverless SQL pool, **không** tạo dedicated pool.
