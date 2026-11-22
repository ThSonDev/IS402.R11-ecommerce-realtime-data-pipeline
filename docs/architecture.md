# Kiến trúc tổng thể

Trung tâm giám sát Mega Sale real-time cho thương hiệu điện tử bán đa sàn (Tiki, Shopee, Lazada): KPI kinh doanh theo phút và 4 luật gian lận, bất thường.

![Kiến trúc hệ thống giám sát Mega Sale real-time](architecture.drawio.svg)

Nguồn chỉnh sửa: [`architecture.drawio.svg`](architecture.drawio.svg) là SVG có nhúng sẵn dữ liệu draw.io, mở thẳng bằng draw.io để sửa (không cần file `.drawio` riêng). Sau khi lưu từ draw.io phải ép nền trắng và bỏ `light-dark()` (dark mode GitHub làm chìm chữ):

```powershell
python scripts/fix_drawio_svg.py docs/architecture.drawio.svg
```

Muốn xuất PNG:

```powershell
& "C:\Program Files\draw.io\draw.io.exe" -x -f png -b 20 -s 2 -o docs/architecture.png docs/architecture.drawio.svg
# Linux: drawio -x -f png -b 20 -s 2 -o docs/architecture.png docs/architecture.drawio.svg
```

Cách đọc hình: khung ngoài (nét chấm) là ranh giới hệ thống; Kaggle, 3 nhóm người dùng và Telegram nằm ngoài khung. Azure subscription, resource group, ADLS Gen2 (vẽ 2 container dùng trong luồng) và workspace Power BI (khung vàng) là các khung chứa thật. Số trong vòng tròn là luồng dữ liệu (nét liền), chữ A–E là điều khiển (nét đứt tím).

## 4 luật (chạy trong Stream Analytics)

1. Bot gom hàng: 1 user > N đơn / 1 phút (window + `COUNT` theo user).
2. Săn voucher: 1 `device_id` ↔ nhiều tài khoản mới (`COUNT(DISTINCT)` trong window).
3. Sai giá so với giá tham chiếu (JOIN reference data `price_list`).
4. Số đơn/phút giảm bất thường (`AnomalyDetection_SpikeAndDip`, mode `dips`).

Cùng job còn tính KPI 1 phút theo sàn × tỉnh (view, cart, purchase, đơn, GMV). Job dùng `TIMESTAMP BY event_time`, chịu event đến trễ và sai thứ tự 60 s (late arrival / out-of-order), query nằm trong Git (`stream/query.asaql`).

## Luồng dữ liệu (số, nét liền)

Real-time (xanh dương)

1. (xám, chạy 1 lần, xử lý trước) Tải bộ REES46 từ Kaggle (11/2019, 67.5 triệu event), `scripts/prepare_data.py` dedup và chuyển thành Parquet. Đây không phải luồng stream từ Kaggle. Producer đọc Parquet mỗi lần chạy (mũi tên xanh dương, không số).
2. Producer (Python, chạy trên máy) đọc Parquet, phát lại theo nhịp giờ gốc, `event_time` = giờ gửi (`--speed` ≤ 4), làm giàu dữ liệu VN có seed, chèn 4 kịch bản gian lận có nhãn (`is_fraud`) và event trễ (`is_late`). Gửi JSON bằng Kafka protocol qua TLS (cổng 9093), key = `user_id`, tới Event Hubs `evhns-megasale-dev`.
3. Event Hubs hub `events` (Standard 1 TU, 4 partition). Stream Analytics đọc bằng consumer group `asa`.
4. Dữ liệu tham chiếu `price_list.csv` (189,284 sản phẩm) và `provinces.csv` (34 tỉnh) ở container `reference` (Terraform upload từ Git), khai báo là reference input của ASA; luật 3 JOIN `price_list`.
5. Output `kpi_1min_powerbi` (KPI 1 phút) đẩy sang Power BI streaming dataset (dashboard real-time).

Vận hành và cảnh báo (cam)

6. Output `kpi_1min_sql`, `pipeline_latency`, `alerts` → bảng `dbo.kpi_1min`, `dbo.pipeline_latency`, `dbo.alerts` trong SQL Database, ghi bằng managed identity (Entra-only).
7. `alerts` của 4 luật gửi sang Functions (`func-megasale-dev`).
8. Function gộp cảnh báo (Telegram giới hạn 20 tin/phút/nhóm) rồi gọi `sendMessage` tới nhóm on-call.
9. Grafana chạy local (Windows) đọc SQL bằng Entra app chỉ đọc (`grafana-megasale-reader`); dashboard provision từ Git. Đội vận hành xem war room trên Grafana (mũi tên không đánh số).
10. Alert rule độ trễ pipeline của Grafana dùng chung bot Telegram. Cảnh báo gian lận chỉ gửi Telegram qua Function; Grafana trên `dbo.alerts` chỉ hiện panel, để không trùng tin. Telegram gửi tới nhóm on-call (mũi tên không đánh số).

Lịch sử (xanh lá)

11. ASA ghi event thô `raw_archive` (Parquet, lớp bronze) và `kpi_1min` (JSON) vào container `lake` (Data lake) (`<output>/yyyy/MM/dd/HH`).
12. Synapse serverless SQL đọc Parquet: view silver, rồi star schema gold (`fact_events` + `dim_date`, `dim_product`, `dim_channel`, `dim_province`, `dim_payment`).
13. Power BI đọc lớp gold cho báo cáo lịch sử ≥ 4 trang, RLS theo sàn và miền (RLS chỉ áp cho Viewer). Báo cáo được publish qua Power BI App cho giám đốc, quản lý sàn, quản lý miền (mũi tên cuối không đánh số).

## Điều khiển (chữ A–E, nét đứt tím)

- **A.** Mọi thứ là code trong Git: Terraform, ASA query, SQL, PBIP, Grafana dashboard.
- **B.** GitHub Actions: `ci.yaml` (ruff, pytest, terraform validate) và `terraform.yaml` (plan, apply, destroy-eventhubs, destroy) chạy Terraform.
- **C.** Terraform (azurerm + azapi) dựng mọi resource trong `rg-megasale-dev` (RG và role Azure cấp tay); state ở Blob `stmegasaletf2911` (versioning + khóa xóa).
- **D.** Entra ID: SQL và Synapse chỉ đăng nhập Entra. Event Hubs (producer, ASA) dùng SAS; ASA → Storage dùng account key; ASA → SQL, Power BI qua managed identity.
- **E.** GitHub Actions → Entra ID: Actions gửi OIDC token, nhận lại access token (federated credential của app `gh-actions-is402`), không dùng secret.
- Budget 30 USD/tháng (`budget-megasale`, cảnh báo 50/80/100%) gắn với resource group: Event Hubs destroy khi rảnh, ASA stop sau buổi test.

## Số đo và nguồn dữ liệu

Số đo thực: 67.5 triệu event, trung bình 26.5 event/s, đỉnh 243 event/s. Test E2E 17/11: 76,790 event (3,803 trễ), KPI khớp raw 16/16 phút, gửi → ASA ~476 ms.

Nguồn dữ liệu: Kaggle `mkechinov/ecommerce-behavior-data-from-multi-category-store` (REES46).

## Môi trường dev (không vẽ trong hình)

Khi phát triển, Kafka local `apache/kafka:3.9.0` + Kafka UI (`docker-compose.yaml`, broker `localhost:9092`, UI `:8080`) thay Event Hubs. Producer dùng cùng code, chỉ đổi `.env`: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL` (local `PLAINTEXT`, Event Hubs `SASL_SSL`) và `EVENTHUBS_CONNECTION_STRING`. Hình chỉ vẽ luồng chạy thật trên cloud; Kafka chỉ là giao thức của Event Hubs.

## Đường đi của 1 event

```mermaid
sequenceDiagram
    participant P as Producer
    participant EH as Event Hubs
    participant ASA as Stream Analytics
    participant SQL as SQL Database
    participant PBI as Power BI streaming
    participant L as Data lake
    participant G as Grafana
    P->>EH: JSON qua Kafka, key = user_id (~320 ms)
    EH->>ASA: đọc event (~140 ms)
    ASA->>L: event thô (Parquet, không chờ cửa sổ, lô 2,000 dòng hoặc 1 phút)
    Note over ASA: xếp theo event_time<br/>chờ trễ / sai thứ tự tối đa 60 s<br/>cửa sổ 1 phút đóng
    par sau khi cửa sổ đóng
        ASA->>SQL: kpi_1min, pipeline_latency
    and
        ASA->>PBI: KPI 1 phút
    and
        ASA->>L: KPI (JSON)
    end
    G->>SQL: truy vấn (refresh 1 phút)
    Note over P,ASA: gửi đến khi ASA xử lý ~476 ms (đo 17/11)
    Note over ASA,G: KPI hiện sau 1–3 phút
```

Event thô ghi thẳng vào data lake, không chờ cửa sổ. KPI thì phải đợi: watermark = `event_time` lớn nhất trừ 60 s, cửa sổ chỉ đóng khi watermark vượt mốc cuối phút. Event đến trễ hơn 60 s bị dời giờ (Adjust) sang phút khác, nên số phút đó có thể lệch.

## Luồng cảnh báo

```mermaid
flowchart LR
    ASA["Stream Analytics<br/>phát hiện 1 trong 4 luật"] --> AL["output alerts"]
    AL --> SQL[("SQL Database<br/>dbo.alerts")]
    SQL --> GP["Grafana<br/>panel cảnh báo"]
    AL -- "lô JSON qua HTTP<br/>+ function key" --> FN["Functions<br/>gộp ≤ 20 tin/phút"]
    FN -- sendMessage --> TG["Telegram"]
    TG --> OC(["Nhóm on-call"])
    PL[("SQL Database<br/>dbo.pipeline_latency")] --> LAT["Grafana alert rule<br/>độ trễ > 5,000 ms kéo dài 1 phút"]
    LAT -- "Firing / Resolved" --> TG
    classDef ops fill:#fff,stroke:#C43E00,color:#333
    class AL,SQL,GP,FN,PL,LAT ops
    classDef rt fill:#fff,stroke:#0078D4,color:#333
    class ASA rt
    classDef ext fill:#fff,stroke:#8A8886,color:#333
    class TG,OC ext
```

Cảnh báo của 4 luật chỉ đi Telegram qua Functions, để gộp và không vượt giới hạn 20 tin/phút/nhóm. Grafana đọc `dbo.alerts` chỉ để hiển thị panel, không gửi Telegram (tránh trùng tin). Telegram từ Grafana chỉ có alert độ trễ pipeline, báo cả Firing lẫn Resolved.

ASA gửi sang Functions theo HTTP và chờ HTTP 200, quá 100 s thì gửi lại. Lô mặc định tối đa 100 event / 262,144 byte, và có lô rỗng lúc kiểm tra kết nối. Vì vậy Function phải trả 200 nhanh, chịu được lô rỗng và bỏ trùng theo khóa cảnh báo ([nguồn](https://learn.microsoft.com/en-us/azure/stream-analytics/azure-functions-output)).

## Lớp dữ liệu

```mermaid
flowchart LR
    ASA["Stream Analytics"]
    subgraph COLD["Lịch sử (batch)"]
        direction LR
        B["Bronze · Data lake<br/>event thô Parquet theo yyyy/MM/dd/HH<br/>KPI JSON (lưu trữ, silver không đọc)"]
        S["Silver · Synapse serverless view<br/>events_raw: ép kiểu + cột partition từ đường dẫn<br/>events: bỏ dòng hỏng, dedup event_id"]
        GD["Gold · star schema<br/>fact_events + dim_date, dim_product,<br/>dim_channel, dim_province, dim_payment"]
        R["Power BI báo cáo lịch sử<br/>RLS sàn/miền, qua App"]
        B --> S --> GD --> R
    end
    subgraph HOT["Real-time"]
        direction LR
        SQL[("SQL Database<br/>KPI, cảnh báo, độ trễ")] --> GF["Grafana"]
        PS["Power BI streaming"]
    end
    ASA --> B
    ASA --> SQL
    ASA --> PS
    style COLD fill:none,stroke:#107C10
    style HOT fill:none,stroke:#0078D4
    classDef cold fill:#fff,stroke:#107C10,color:#333
    class B,S,GD,R cold
    classDef hot fill:#fff,stroke:#0078D4,color:#333
    class ASA,PS hot
    classDef ops fill:#fff,stroke:#C43E00,color:#333
    class SQL,GF ops
```

Dữ liệu đi qua ba lớp: bronze là file ASA ghi nguyên trạng, silver là view làm sạch, gold là star schema cho báo cáo. Khi truy vấn phải lọc partition trên `silver.events_raw` trước rồi mới dedup, vì `silver.events` dedup bằng `ROW_NUMBER` nên không prune được partition. Nhánh real-time chạy song song, không qua data lake.

Thử CETAS trên 1 partition giờ (#92): giảm 72% số file, 64% dung lượng; chưa đưa vào luồng.

## IaC và CI/CD

```mermaid
flowchart TB
    BR["Nhánh"] --> PR["Pull request"]
    PR --> TP["terraform.yaml: plan<br/>khi PR sửa infra/, stream/query.asaql,<br/>stream/reference/ hoặc terraform.yaml<br/>(đỏ nếu có destroy/replace)"]
    PR --> CI["ci.yaml<br/>lint-test (ruff, pytest)<br/>tf-validate (fmt, validate)<br/>bắt buộc để merge"]
    CI --> M["Merge vào main"]
    TP -. "không bắt buộc" .-> M
    M --> RUN["Chạy tay terraform.yaml<br/>plan / apply / destroy-eventhubs / destroy"]
    RUN -- "OIDC token" --> ENT["Entra ID<br/>app gh-actions-is402, không secret"]
    TP -- OIDC --> ENT
    ENT -- "access token" --> RUN
    RUN -- "Terraform" --> AZ["Azure<br/>rg-megasale-dev"]
    RUN <--> ST[("Terraform state ở Blob<br/>versioning + khóa xóa")]
    subgraph TEST["Buổi test (Event Hubs tính tiền theo giờ tồn tại)"]
        direction LR
        T1["apply"] --> T2["fill_env.py"] --> T3["start ASA"] --> T4["chạy producer"] --> T5["stop ASA"] --> T6["destroy-eventhubs"]
    end
    RUN -. "mỗi buổi test" .-> TEST
    style TEST fill:none,stroke:#7030A0
    classDef ctl fill:#fff,stroke:#7030A0,color:#333
    class BR,PR,CI,TP,M,RUN,ENT,AZ,ST,T1,T2,T3,T4,T5,T6 ctl
```

Mọi thay đổi hạ tầng đi qua PR: `ci.yaml` chặn merge nếu lint, test hoặc validate lỗi; `terraform.yaml` hiện plan và đỏ nếu có destroy hay replace (không bắt buộc). Sau khi merge, thành viên chạy tay `terraform.yaml`; GitHub Actions đăng nhập Azure bằng OIDC, không có secret. Vì Event Hubs tính tiền theo giờ tồn tại, mỗi buổi test phải kết thúc bằng stop ASA rồi `destroy-eventhubs`.
