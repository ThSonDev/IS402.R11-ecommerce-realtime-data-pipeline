# producer/ – Python producer

Phụ trách: Minh

## Làm gì

Đọc `data/processed/2019-Nov.parquet`, bỏ dòng trùng, làm giàu bối cảnh Việt Nam, dịch thời gian sang trục replay và tạo event đúng [docs/event-schema.md](../docs/event-schema.md).

| File | Chức năng |
|---|---|
| `reader.py` | `read_events(path, start, end)`: đọc một khoảng thời gian, bỏ dòng trùng, sắp xếp ổn định, trả từng dòng (dict). Đọc theo khúc 10,000 dòng |
| `enrich.py` | `load_provinces(path)`, `enrich(row, provinces, event_time, sent_time)`: dòng gốc thành event 22 trường |
| `timeshift.py` | `parse_raw`, `replay_time`, `to_iso_ms`: đặt thời gian 2019 lên trục replay |
| `scenarios.py` | 4 kịch bản gian lận / sự cố có nhãn: `bot`, `multi_account`, `price_glitch`, `payment_outage` |
| `main.py` | Chương trình chính: replay một đoạn dữ liệu vào Kafka / Event Hubs (hoặc ra file) theo `--speed` hoặc `--rate`, có thể gửi trễ một phần event (`--late-rate`) và chèn kịch bản (`--scenarios`) |

Test nằm trong [tests/](../tests/README.md).

## Cách chạy

Chạy mọi lệnh từ thư mục gốc repo.

**1. Chuẩn bị (một lần).** Cài thư viện, tạo `.env` từ mẫu (giá trị mặc định đã đúng cho Kafka local):

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
# Linux: .venv/bin/python -m pip install -r requirements.txt
copy .env.example .env
# Linux: cp .env.example .env
```

**2. Bật Kafka local** (Kafka UI ở http://localhost:8080, producer kết nối `localhost:9092`):

```powershell
docker compose up -d
```

**3. Chạy producer.** Chọn đúng một trong hai chế độ:

```powershell
# Replay nhanh gấp 4 lần, giữ đúng tỷ lệ khoảng cách giữa các event (demo, dashboard)
.venv\Scripts\python producer\main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4
# Linux: .venv/bin/python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4

# Gửi đều 500 event/giây (benchmark)
.venv\Scripts\python producer\main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --rate 500
# Linux: .venv/bin/python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --rate 500

# Thêm 1% event gửi trễ (is_late = true), mỗi event bị giữ lại 6–60 giây
.venv\Scripts\python producer\main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4 --late-rate 0.01
# Linux: .venv/bin/python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4 --late-rate 0.01
```

| Tham số | Bắt buộc | Ý nghĩa |
|---|---|---|
| `--start`, `--end` | có | Đoạn dữ liệu gốc cần phát (giờ UTC của dataset), dạng `2019-11-01T09:00`. Không lấy mốc `--end` |
| `--speed N` | một trong hai | Phát nhanh gấp N lần, giữ tỷ lệ khoảng cách giữa các event |
| `--rate N` | một trong hai | Gửi đều N event/giây, bỏ qua khoảng cách gốc |
| `--sample-rate R` | không (mặc định 1.0) | Chỉ giữ toàn bộ event của tỷ lệ R user, để giảm lưu lượng mà không cắt vụn hành trình của user |
| `--late-rate R` | không (mặc định 0, tắt) | Tỷ lệ event cố ý gửi trễ, gắn `is_late = true` |
| `--late-delay S` | không (mặc định 60) | Thời gian giữ lại tối đa của một event trễ (giây). Mỗi event trễ bị giữ 10–100% con số này |
| `--scenarios LIST` | không | `all` hoặc danh sách cách nhau bởi dấu phẩy, ví dụ `bot,price_glitch` (xem mục Kịch bản) |
| `--scenario-start S` | không (mặc định 60) | Kịch bản đầu tiên bắt đầu sau S giây replay, các kịch bản sau cách nhau 120 giây |
| `--outage-minutes M` | không (mặc định 10) | Độ dài `payment_outage`, tính theo phút replay |
| `--scenario-log PATH` | không | Nơi ghi ground truth của kịch bản (JSON). Mặc định cạnh `--out`, hoặc `data/scenario_logs/` |
| `--out PATH` | không | Ghi event ra file JSON Lines thay vì gửi Kafka, chạy hết tốc độ trên đồng hồ giả lập |
| `--replay-start T` | không | `event_time` của event đầu tiên khi dùng `--out` (ví dụ `2026-11-11T13:00`), mặc định là giờ hiện tại |
| `--limit N` | không | Dừng sau N event, tiện khi thử |

Cứ 10,000 event chương trình in tiến độ (tốc độ thực tế, mức trễ so với lịch, số event trễ đang giữ). Hết dữ liệu thì chương trình chờ gửi nốt các event trễ đúng giờ của chúng. Bấm `Ctrl+C` để dừng: event trễ còn giữ và event đang chờ vẫn được gửi nốt, rồi in tổng kết `done: ... sent (... late), ... delivered in ...s (... ev/s), ... failed, ... not delivered`. `delivered` là số event Kafka / Event Hubs đã xác nhận nhận được, và tốc độ `ev/s` tính theo con số này. Khi có `--scenarios`, dòng tổng kết thêm số event của kịch bản (`fraud`) và số purchase bị `payment_outage` loại (`dropped by outage`).

**4. Xem event trong Kafka.** Mở Kafka UI → Topics → `events` → Messages, hoặc xem trực tiếp trong terminal:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic events --property print.key=true --property print.partition=true
```

**Lên Event Hubs:** không sửa code, chạy `scripts/fill_env.py` để đổi `.env` (`KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SASL_SSL`, `EVENTHUBS_CONNECTION_STRING`); `scripts/fill_env.py --local` để quay về Kafka local.

**Kịch bản gian lận.** Bật bằng `--scenarios`. Mỗi kịch bản chạy ở một mốc cố định trên trục replay, theo thứ tự `bot` → `multi_account` → `price_glitch` → `payment_outage`, nên chạy lại cùng tham số ra đúng các event đó. Event chèn vào có `is_fraud = true` và `scenario` đúng tên; event thật giữ `is_fraud = false`, `scenario = null`. Cuối lần chạy, producer ghi file ground truth (JSON) liệt kê từng kịch bản: khoảng thời gian (theo `event_time`) và đối tượng (user, thiết bị, sản phẩm). File này là đầu vào của `analysis/evaluate_rules.py`. Lần chạy phải đủ dài: với `--scenario-start 60` và cả 4 kịch bản, sự cố kết thúc ở giây thứ 1,020 của replay (khoảng 17 phút).

```powershell
# Live, cả 4 kịch bản: 90 phút dữ liệu giờ cao điểm, nhanh gấp 4 (khoảng 22 phút)
.venv\Scripts\python producer\main.py --start 2019-11-01T09:00 --end 2019-11-01T10:30 --speed 4 --scenarios all
# Linux: .venv/bin/python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:30 --speed 4 --scenarios all

# Ra file cho Stream Analytics local (vài giây, không cần Kafka)
.venv\Scripts\python producer\main.py --start 2019-11-01T09:00 --end 2019-11-01T10:30 --speed 4 --scenarios all --out data\samples\events_scenarios_full.json --replay-start 2026-11-11T13:00
# Linux: .venv/bin/python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:30 --speed 4 --scenarios all --out data/samples/events_scenarios_full.json --replay-start 2026-11-11T13:00
```

`stream/test/events_scenarios.json` là bản nhỏ đã commit (5% user, chỉ `bot`, `multi_account`, `price_glitch`, kèm `events_scenarios.scenarios.json`) để thử luật 1–3. Luật 4 cần lưu lượng đơn thật nên phải dùng bản đầy đủ như lệnh trên (khoảng 114,000 event, 68 MB, không commit).

### Replay cloud để kiểm tra luật 2–4 (#62)

Dùng đoạn dữ liệu có sự cố purchase thật, đồng thời để producer phát dữ liệu bình thường hơn 10 phút trước lúc sự cố bắt đầu. Lệnh dưới đây chạy khoảng 30 phút ở `4x`; purchase thật dừng khoảng phút 12.25. Kịch bản nhiều tài khoản và sai giá bắt đầu ở phút 20 và 22, sau khi ASA đã có baseline và quan sát được dip. Không bật synthetic `payment_outage` ở lượt này vì đang kiểm tra khoảng sự cố thật trong dữ liệu.

```powershell
.venv\Scripts\python producer\main.py --start 2019-11-14T17:20 --end 2019-11-14T19:20 --speed 4 --scenarios multi_account,price_glitch --scenario-start 1200
# Linux: .venv/bin/python producer/main.py --start 2019-11-14T17:20 --end 2019-11-14T19:20 --speed 4 --scenarios multi_account,price_glitch --scenario-start 1200
```

Lệnh này cần chạy sau khi ASA job đã khởi động và input Event Hubs sẵn sàng. Trước khi dùng trên cloud, cập nhật query/config theo branch đang kiểm thử; sau lượt test, dừng ASA và dọn Event Hubs bằng workflow `destroy-eventhubs` để tránh phát sinh chi phí.

**Đo throughput:** `scripts/bench_producer.py` chạy producer ở nhiều mức `--rate`, mỗi mức nhiều lần, rồi in bảng (xem [docs/producer-throughput.md](../docs/producer-throughput.md)). Hai biến tùy chọn trong `.env` hoặc môi trường dùng cho thí nghiệm gửi theo lô: `KAFKA_LINGER_MS` (`linger.ms`) và `KAFKA_BATCH_SIZE` (`batch.size`); không đặt thì dùng mặc định của client.

## Input / Output

- Input: `data/processed/2019-Nov.parquet` (xem [data/README.md](../data/README.md)), `stream/reference/provinces.csv`, `stream/reference/price_list.csv` (giá tham chiếu cho kịch bản), cấu hình Kafka trong `.env`.
- Output: event JSON theo contract gửi vào topic `events`, key là `user_id` (cùng user luôn vào cùng partition, giữ đúng thứ tự); hoặc file JSON Lines khi dùng `--out`. Khi có `--scenarios`: thêm file ground truth JSON.
- File mẫu đã commit: `stream/test/events_sample.json` (1,036 event, không kịch bản) và `stream/test/events_scenarios.json` (2,109 event, có `bot`, `multi_account`, `price_glitch`, kèm `.scenarios.json`).

## Lưu ý và giả định

**Tính xác định.** Mọi trường giả lập được tính từ SHA-256 với `SEED = "IS402R11"`, không dùng `random` hay `hash()`. Cùng tham số thì ra cùng dữ liệu. Đổi seed thì mọi trường giả lập đổi theo.

**Dữ liệu gốc.**
- Bỏ 100,519 dòng trùng hoàn toàn. Dòng trùng luôn nằm trong cùng một giây.
- 41,287 trường hợp một user có nhiều loại event trong cùng một giây (dataset chỉ chính xác đến giây). Các event cùng giây được sắp theo thứ tự phễu view → cart → purchase.
- Giữ nguyên dòng giá 0 (188,088 dòng, chỉ ở `view` và `cart`, không có ở `purchase`).
- Giữ nguyên hai đoạn không có purchase nào dù lượt xem vẫn cao (150,000–340,000 view mỗi giờ): 2019-11-14 18:09 → 2019-11-16 08:32 UTC (khoảng 38 giờ) và 2019-11-16 15:34 → 2019-11-17 03:43 UTC (khoảng 12 giờ). Đây là ca kiểm thử thật cho luật 4. Ngày 15/11 có 0 purchase cả ngày, còn ngày 17/11 lại là ngày nhiều purchase nhất tháng (185,195).

**Giả định mô phỏng** (không dựa trên số liệu thật):

| Trường | Gắn theo | Giả định |
|---|---|---|
| `channel` | user | shopee 60%, lazada 30%, tiki 10% |
| `province_code` | user | theo trọng số dân số trong `provinces.csv` |
| `device_id` | user | `dev_` + 12 ký tự hex (1 user, 1 thiết bị) |
| `is_new_account` | user | 3% user |
| `payment_method` | session (đơn) | cod 40%, momo 30%, zalopay 20%, card 10% |
| `voucher_code` | session (đơn) | 20% đơn có voucher, chọn đều trong 5 mã: FLASH70, FREESHIP, FLASH50, NEWMEMBER, STUDENT20 |
| `order_id` | session | `o_` + 12 ký tự hex đầu của `session_id`. Mọi purchase trong một session là một đơn |

**Giá.** `price_vnd` = giá USD × 25,850, làm tròn. Tỷ giá trung bình thị trường (mid-market) của [Wise](https://wise.com/vn/currency-converter/usd-to-vnd-rate), lấy lúc 9h ngày 23/10/2026.

**Dân số tỉnh.** "Quy mô dân số" theo Nghị quyết của Quốc hội về sắp xếp đơn vị hành chính cấp tỉnh 2025 (23 đơn vị sáp nhập đã đối chiếu với văn bản; 11 đơn vị giữ nguyên lấy từ bảng xếp hạng của thuvienphapluat.vn). Tổng 113,571,926 người, cao hơn dân số thống kê cả nước, nên đây là số theo văn bản pháp lý, không phải dân số trung bình. Chỉ dùng làm trọng số khi gán tỉnh.

**Thời gian.**
- `event_time = replay_start + (original_time − original_start) / speed` (chế độ `--speed`); chế độ `--rate` thì event thứ k có `event_time = replay_start + k / rate`. `original_time` luôn giữ giờ gốc 2019.

| | Chạy live (`main.py`) | Ra file (`--out`, các file mẫu) |
|---|---|---|
| `replay_start` | Giờ máy lúc bắt đầu chạy | `--replay-start`; các file mẫu dùng 2026-11-11 13:00 UTC |
| Dịch +4h | Không áp dụng: `event_time` luôn là thời điểm hiện tại | Chọn qua `--replay-start`: file mẫu đặt đoạn gốc 09:00 UTC vào 13:00 UTC (20h giờ Việt Nam) |
| `sent_time` | Giờ máy ngay lúc gửi, dùng để đo độ trễ | Thời điểm gửi trên đồng hồ giả lập: bằng `event_time` với event đúng giờ, muộn hơn với event trễ. Không dùng để đo độ trễ thật. Riêng `events_sample.json` (xuất trước khi có `--out`) có `sent_time` luôn bằng `event_time` |

- Chạy live bắt buộc dùng giờ hiện tại: Stream Analytics đối chiếu `event_time` với lúc event đến (event quá cũ hoặc ở tương lai bị điều chỉnh hoặc bỏ), và dashboard real-time chỉ hiển thị khoảng thời gian gần đây.
- Muốn demo có lưu lượng giờ cao điểm thì chọn đoạn dữ liệu cao điểm, ví dụ `--start 2019-11-01T09:00`.
- Muốn demo sự cố thật cho luật 4, chọn đoạn bao quanh lúc purchase biến mất, ví dụ `--start 2019-11-14T17:30 --end 2019-11-14T19:00 --speed 4`: purchase dừng ở phút thứ 39 của đoạn gốc (khoảng phút thứ 10 khi phát nhanh gấp 4), lượt xem vẫn đều.

**Event trễ.**
- Bật bằng `--late-rate`. Event nào trễ và trễ bao lâu được chọn bằng hash của `event_id`, nên chạy lại cùng đoạn dữ liệu thì đúng những event đó bị trễ, đúng thời gian đó.
- `event_time` của event trễ vẫn là thời điểm đúng theo lịch, chỉ có lúc đến Kafka bị muộn; `sent_time` là lúc thật sự gửi, nên `sent_time − event_time` là độ trễ.
- Event trễ cố ý phá thứ tự (ví dụ một `view` trễ đến sau `purchase` của cùng user). Không dùng `--late-rate` thì thứ tự luôn được giữ.
- Mặc định giữ lại 6–60 giây, đủ lâu để thử chính sách late arrival của Stream Analytics. Ngưỡng của job do Thắng cấu hình.

**Kịch bản gian lận** (`producer/scenarios.py`; mốc so sánh lấy từ dữ liệu thật tháng 11/2019):

| Kịch bản | Bắt đầu (`--scenario-start 60`) | Chèn gì | Vì sao mạnh đến mức này |
|---|---|---|---|
| `bot` | giây 60 | 3 user giả (`user_id` từ 900,000,000), mỗi user 20 đơn trong 60 giây | User thật tối đa 3 đơn khác nhau (7 dòng purchase) / phút; luật 1 báo khi > 10 đơn |
| `multi_account` | giây 180 | 2 thiết bị, mỗi thiết bị 6 tài khoản mới (`is_new_account = true`), mỗi tài khoản một đơn dùng voucher `NEWMEMBER`, trong 5 phút | Mỗi user thật có thiết bị riêng; luật 2 thử 3–5 tài khoản / 10 phút |
| `price_glitch` | giây 300 | 3 sản phẩm có giá tham chiếu ≥ 5,000,000 VND, mỗi sản phẩm 5 đơn giá 10–30% giá tham chiếu, trong 2 phút | Giá thật dao động tới 1.67 lần (p99); luật 3 thử lệch trên 50% |
| `payment_outage` | giây 420, dài 10 phút | Không chèn: bỏ mọi purchase thật trả bằng `cod` (40% đơn) trong khoảng đó | Số đơn mỗi phút giảm khoảng 40%; ground truth là khoảng thời gian trong file log |

User, sản phẩm và thời điểm được chọn bằng hash nên lần chạy nào cũng giống nhau. Đơn của kịch bản không bị `payment_outage` loại, và vẫn có thể bị `--late-rate` gửi trễ như event thường. Trên đoạn 2019-11-01 09:00–10:30 (`--speed 4`), dữ liệu thật không có user nào ≥ 5 đơn / phút, không thiết bị nào ≥ 3 tài khoản mới và không đơn nào thấp hơn 50% giá tham chiếu, nên mọi tín hiệu của luật 1–3 trên đoạn này đến từ kịch bản.

**Giới hạn tốc độ.** Dataset trung bình 26.5 event/giây, đỉnh 243 event/giây. Đo thực tế với 1 TU: Event Hubs nhận kịp hoàn toàn đến 1,000 event/giây, tối đa ổn định khoảng 1,500 event/giây (giới hạn 1 MB/giây). Để không bị trễ, giữ `--speed` ≤ 4 ở giờ cao điểm nếu không lấy mẫu. Hàng đợi của client giới hạn 10,000 message: khi đích nhận không kịp, producer phải chờ ngay, nên `behind schedule` tăng thay vì dồn event trong RAM. Kết quả đo xem [docs/producer-throughput.md](../docs/producer-throughput.md).
