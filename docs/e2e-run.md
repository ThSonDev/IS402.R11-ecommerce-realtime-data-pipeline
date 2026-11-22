# Buổi chạy đủ kịch bản trên cloud (#86) và đo độ trễ nhiều region (#66)

Ngày 22/11/2026, một lần bật Event Hubs: 09:23 → 11:04 UTC (~1.7 giờ), ASA chạy 09:26 → ~11:04. Số thô và lệnh nằm ở `data/runs/2026-11-22/` (gitignored); bản sao ở `lake/eval/2026-11-22/` (Minh đọc được, xem cuối file).

## 1. Cấu hình

| Lượt | Lệnh producer (`--speed 4`) | Giờ UTC | Event gửi | Lỗi gửi |
|---|---|---|---|---|
| A (query cũ) | `--start 2019-11-01T09:00 --end 2019-11-01T10:30 --scenarios all --late-rate 0.05 --late-delay 50` | 09:26:03 → 09:49:24 | 113,928 (5,704 trễ) | 0 |
| A2 (query sửa) | như A | 10:00:13 → 10:23:34 | 113,928 (5,704 trễ) | 0 |
| B (sự cố thật) | `--start 2019-11-14T17:20 --end 2019-11-14T19:20 --scenarios multi_account,price_glitch --scenario-start 1200` | 10:27:04 → 10:57:06 | 498,298 | 0 |

Khoảng sự cố thật của lượt B trên trục `event_time` = bắt đầu + 12.25 phút → hết lượt = 10:39:19 → 10:57:06. Tốc độ B ~277–310 ev/s, `behind schedule` ≤ 0.03 s.

Query sửa giữa A và A2 (theo **định nghĩa luật**, không chỉnh ngưỡng theo dữ liệu test; ngưỡng là việc #72):

- Luật 2: `TUMBLINGWINDOW(minute,10)` → `HOPPINGWINDOW(minute,10,1)` (tumbling cắt 3+3 tài khoản nên lọt).
- Luật 3: bỏ `ABS`, chỉ báo giá **thấp** hơn giá tham chiếu quá 50% (sai giá = bán lỗ).
- Luật 4: `'spikesanddips'` → `'dips'` (sự cố = đơn giảm; spike lúc phục hồi không phải sự cố).

## 2. Kết quả precision / recall (`analysis/evaluate_rules.py`)

| Luật | A trước khi sửa | A2 sau khi sửa | B (sự cố thật) |
|---|---|---|---|
| bot | 3 alert, P 100%, R 100% | 3 alert, P 100%, R 100% | không có kịch bản |
| multi_account | 1 alert, P 100%, **R 50%** | 20 dòng alert (2 thiết bị), P 100%, R 100% | 17 dòng (2 thiết bị), P 100%, R 100% |
| price_glitch | 6 alert, **P 60%**, R 100% | 5 alert, P 100%, R 100% | 4 alert, P 100%, R 100% |
| payment_outage | 5 alert, **P 40%**, R 100% | 0 alert, **R 0%** | 1 alert (10:41, 0 đơn/phút), P 100%, R 100% |

Giải thích:

- **Luật 2:** lượt A lọt `dev_2ec235002de4` do cửa sổ tumbling cắt tài khoản vào 2 cửa sổ. Hopping 10 phút bước 1 phút bắt đủ, đổi lại một thiết bị ra nhiều dòng alert (tối đa 10 dòng/cửa sổ trượt; Function đã chặn lặp 10 phút; evaluate tính theo thiết bị).
- **Luật 3:** 2 sản phẩm báo nhầm ở lượt A đều là giá **cao**: `12704397` mua ~1,577,884 VND so với giá tham chiếu 798,506 (×1.98), `2500566` ~1,696,000 so với 1,130,420 (×1.50; ratio 0.5003 sát ngưỡng). Bỏ `ABS` loại được cả hai. Giá tham chiếu là trung vị ước tính nên sản phẩm có giá dao động mạnh vẫn có thể lệch cao.
- **Luật 4, lượt A:** 2 "TP" thực ra là **spike** nằm trong khoảng nhãn (89, 95, 93, 101 đơn/phút ở 09:44–09:47, sau khi sự cố giả lập kết thúc), không phải bắt được dip. 3 FP còn lại cùng loại (spike phục hồi).
- **Luật 4, lượt A2:** sự cố giả lập chỉ làm đơn/phút giảm từ ~100–120 xuống ~65 (−40%, `kpi_1min` 10:09–10:17), không về 0; ở confidence 80 mô hình không coi là dip → 0 alert. Đây là đầu vào cho #72 (hạ confidence hoặc kịch bản outage mạnh hơn), không chỉnh trong buổi này.
- **Luật 4, lượt B:** sự cố thật (purchase về 0) → 1 alert lúc 10:41 (metric_value 0), nằm trong khoảng 10:39:19 → 10:57:06; 0 FP ngoài khoảng. Chỉ 1 alert trong ~18 phút sự cố (mô hình báo dip đầu tiên rồi coi 0 là bình thường), chưa kiểm khả năng báo suốt sự cố.
- Lượt B: CSV có 17 dòng multi_account còn SQL (10:27–10:58) đếm 16; chênh 1 dòng ở biên giờ, chưa kiểm dòng nào; evaluate tính theo thiết bị nên P/R không đổi.

## 3. ASA và độ trễ pipeline

Metric ASA (`az monitor metrics list`, 09:20–11:10 UTC, theo giờ UTC 09 / 10): `Errors` 0 / 0, `DroppedOrAdjustedEvents` 0 / 0, `LateInputEvents` 0 / 0, `ConversionErrors` 0 / 0, `InputEvents` 617,683 / 517,738, `OutputEvents` 213,148 / 535,370. `InputEvents` lớn hơn nhiều so với số event gửi (tổng 1,135,421 so với 726,154 gửi, gồm 8,000 event rác ở mục 5); chưa rõ nguyên nhân phần còn lại (cũng chưa rõ ở lượt 17/11).

`pipeline_latency` (`dbo.pipeline_latency`, trung bình theo phút `event_time`) chỉ dùng chặng **Event Hubs → ASA**, vì cả hai mốc (`EventEnqueuedUtcTime`, `EventProcessedUtcTime`) đều theo đồng hồ Azure (ms):

| Lượt | Số phút | Event | Trung vị các phút | Phút cao nhất | Thấp nhất |
|---|---|---|---|---|---|
| A2 | 23 | 113,928 | 136 | 6,775 (10:01) | 125 |
| B | 31 | 498,298 | 128 | 165 (10:53) | 106 |

Ở A2, phút 10:01 (6,775 ms) cao bất thường; phút này nằm ngay sau lúc start ASA (10:00) nên khả năng do job vừa khởi động, chưa kiểm chứng. Các phút còn lại 125–197 ms (cao hơn một chút ở 10:02–10:04 và 10:18: 197, 164, 161, 186, chưa rõ nguyên nhân). Cột `producer_to_eventhub` và end-to-end trong `pipeline_latency` **không dùng** ở lượt này: mốc `sent_time` lấy từ đồng hồ máy producer nên ra số âm (−61 đến −91 ms trung bình) do lệch đồng hồ với Azure.

Ước tính end-to-end ≈ ack gửi tới japaneast (~118–122 ms, mục 4, một đồng hồ duy nhất trên máy producer) + EH → ASA (~128–136 ms) ≈ 250–260 ms. Đây là **cộng hai phép đo riêng** (khác thời điểm, khác phương pháp), không phải đo end-to-end trực tiếp.

So với 17/11 (CLAUDE.md: producer → EH ~320 ms, EH → ASA ~140 ms): EH → ASA cùng cỡ (~130–140 ms); chặng gửi khác nhiều (320 ms so với ack ~120 ms) vì hai lần đo khác phương pháp (17/11 theo `sent_time` của producer, 22/11 đo ack bằng một đồng hồ; chưa kiểm vì sao 17/11 không âm), nên không so trực tiếp được.

## 4. #66: độ trễ ack theo region

`scripts/measure_send_latency.py` gửi 2,000 event 600 byte, 50 ev/s, từ cùng một máy, đo từ `produce()` tới delivery callback (ms). Namespace Standard 1 TU, 4 partition. Hai namespace tạm ở `koreacentral`, `centralindia` đã **xóa** ngay sau khi đo. Đo song song với lượt A nên có thể nhiễu nhẹ; bản script đã sửa (bỏ 50 event đầu làm warm-up) chưa chạy lại, các số dưới đây gồm cả 50 event đầu.

| Region | Lần | mean | p50 | p95 | p99 |
|---|---|---|---|---|---|
| japaneast | 1 | 117.9 | 94 | 141 | 844 |
| japaneast | 2 | 121.6 | 94 | 172 | 922 |
| koreacentral | 1 | 106.8 | 79 | 110 | 937 |
| koreacentral | 2 | 98.0 | 78 | 109 | 703 |
| centralindia | 1 | 126.4 | 94 | 188 | 1,062 |
| centralindia | 2 | 114.5 | 94 | 141 | 922 |

0 lỗi ở cả 6 lần đo. p99 ~0.7–1.1 giây ở mọi region: khả năng là do mở kết nối và các event đầu, chưa kiểm chứng. Giới hạn: chỉ đo ack producer → Event Hubs; end-to-end (qua ASA) chỉ có ở japaneast vì ASA chỉ ở đó. Máy đo ở Việt Nam, chênh vài chục ms giữa các region nên 2 lần đo chưa đủ kết luận chắc (koreacentral thấp nhất ở cả 2 lần). Chưa test được với Kafka local vì máy không có Docker.

## 5. Sự cố và hạn chế trong buổi chạy

- Lần đo #66 đầu lấy sai khóa nên chỉ japaneast chạy; script gửi `payload` 600 byte `x` vào hub `events` japaneast chính (4,000 event × 2 lần = 8,000) → ASA `DeserializationError` = 8,000. Không ảnh hưởng alert/KPI (ASA bỏ qua), nhưng nằm trong `InputEvents`. Lần sau đo japaneast bằng hub riêng.
- Alert xuất ra CSV theo khoảng giờ (`alert_time ≥` giờ bắt đầu lượt), nên đuôi alert của lượt trước có thể lẫn vào lượt sau.
- Chưa có video quay (Grafana, Telegram, ASA metrics): #86 chưa đóng.

## 6. Chi phí ước tính (Cost Management trễ 8–24 giờ, số thật: chưa có)

Theo bảng giá `CLAUDE.md`: Event Hubs ~1.7 giờ × 0.03 = ~0.05 USD; ASA ~1.6 giờ × 0.155 = ~0.25 USD; 2 namespace tạm ~0.01 USD; event ~0.02 USD (~0.74M event × 0.028/1M). Tổng ước tính ~0.33 USD.

## 7. Lệnh tạo số

```powershell
# alert theo luật / độ trễ: sqlcmd -S sql-megasale-dev.database.windows.net -d sqldb-megasale-dev --authentication-method ActiveDirectoryAzCli -i scripts\sql\e2e_metrics.sql -v from="'2026-11-22 10:27'" to="'2026-11-22 10:58'"
.venv\Scripts\python analysis\evaluate_rules.py --alerts data\runs\2026-11-22\alerts-B.csv --scenario-log data\runs\2026-11-22\scenario-B.json --incident 2026-11-22T10:39:19Z,2026-11-22T10:57:06Z
.venv\Scripts\python scripts\measure_send_latency.py --bootstrap <namespace>.servicebus.windows.net:9093 --conn-env <TÊN_BIẾN_MÔI_TRƯỜNG>
# Linux: .venv/bin/python analysis/evaluate_rules.py ...
```

Tải bộ số cho Minh (#68): `az storage blob download-batch --account-name stmegasaledev -s lake --pattern "eval/2026-11-22/*" -d data/runs --auth-mode login`
