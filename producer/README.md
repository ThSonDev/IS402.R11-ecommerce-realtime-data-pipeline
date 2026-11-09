# producer/ – Python producer

Phụ trách: Minh

## Làm gì

Đọc `data/processed/2019-Nov.parquet`, bỏ dòng trùng, làm giàu bối cảnh Việt Nam, dịch thời gian sang trục replay và tạo event đúng [docs/event-schema.md](../docs/event-schema.md).

| File | Chức năng |
|---|---|
| `reader.py` | `read_events(path, start, end)`: đọc một khoảng thời gian, bỏ dòng trùng, sắp xếp ổn định, trả từng dòng (dict). Đọc theo khúc 10,000 dòng |
| `enrich.py` | `load_provinces(path)`, `enrich(row, provinces, event_time, sent_time)`: dòng gốc thành event 22 trường |
| `timeshift.py` | `parse_raw`, `replay_time`, `to_iso_ms`: đặt thời gian 2019 lên trục replay |
| `main.py` | Chương trình chính: replay một đoạn dữ liệu vào Kafka / Event Hubs theo `--speed` hoặc `--rate`, có thể gửi trễ một phần event (`--late-rate`) |

Test nằm trong [tests/](../tests/README.md). Chưa có: kịch bản gian lận.

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
| `--limit N` | không | Dừng sau N event, tiện khi thử |

Cứ 10,000 event chương trình in tiến độ (tốc độ thực tế, mức trễ so với lịch, số event trễ đang giữ). Hết dữ liệu thì chương trình chờ gửi nốt các event trễ đúng giờ của chúng. Bấm `Ctrl+C` để dừng: event trễ còn giữ và event đang chờ vẫn được gửi nốt, rồi in tổng kết `done: ... sent (... late), ... failed, ... not delivered`.

**4. Xem event trong Kafka.** Mở Kafka UI → Topics → `events` → Messages, hoặc xem trực tiếp trong terminal:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic events --property print.key=true --property print.partition=true
```

**Lên Event Hubs (tuần 2):** không sửa code, chỉ đổi trong `.env`: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SASL_SSL` và `EVENTHUBS_CONNECTION_STRING`.

## Input / Output

- Input: `data/processed/2019-Nov.parquet` (xem [data/README.md](../data/README.md)), `stream/reference/provinces.csv`, cấu hình Kafka trong `.env`.
- Output: event JSON theo contract gửi vào topic `events`, key là `user_id` (cùng user luôn vào cùng partition, giữ đúng thứ tự). File mẫu: `stream/test/events_sample.json` (1,036 event, JSON Lines).

## Lưu ý và giả định

**Tính xác định.** Mọi trường giả lập được tính từ SHA-256 với `SEED = "IS402R11"`, không dùng `random` hay `hash()`. Cùng tham số thì ra cùng dữ liệu. Đổi seed thì mọi trường giả lập đổi theo.

**Dữ liệu gốc.**
- Bỏ 100,519 dòng trùng hoàn toàn. Dòng trùng luôn nằm trong cùng một giây.
- 41,287 trường hợp một user có nhiều loại event trong cùng một giây (dataset chỉ chính xác đến giây). Các event cùng giây được sắp theo thứ tự phễu view → cart → purchase.
- Giữ nguyên dòng giá 0 (188,088 dòng, chỉ ở `view` và `cart`, không có ở `purchase`).
- Giữ nguyên đoạn 14–17/11/2019 không có purchase (ca kiểm thử thật cho luật 4).

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

| | Chạy live (`main.py`) | File mẫu (`stream/test/events_sample.json`) |
|---|---|---|
| `replay_start` | Giờ máy lúc bắt đầu chạy | Mốc cố định 2026-11-11 13:00 UTC |
| Dịch +4h | Không áp dụng: `event_time` luôn là thời điểm hiện tại | Có: đoạn gốc 09:00 UTC đặt vào 13:00 UTC (20h giờ Việt Nam) |
| `sent_time` | Giờ máy ngay lúc gửi, dùng để đo độ trễ | Bằng `event_time` (giữ chỗ), không dùng để đo độ trễ |

- Chạy live bắt buộc dùng giờ hiện tại: Stream Analytics đối chiếu `event_time` với lúc event đến (event quá cũ hoặc ở tương lai bị điều chỉnh hoặc bỏ), và dashboard real-time chỉ hiển thị khoảng thời gian gần đây.
- Muốn demo có lưu lượng giờ cao điểm thì chọn đoạn dữ liệu cao điểm, ví dụ `--start 2019-11-01T09:00`.

**Event trễ.**
- Bật bằng `--late-rate`. Event nào trễ và trễ bao lâu được chọn bằng hash của `event_id`, nên chạy lại cùng đoạn dữ liệu thì đúng những event đó bị trễ, đúng thời gian đó.
- `event_time` của event trễ vẫn là thời điểm đúng theo lịch, chỉ có lúc đến Kafka bị muộn; `sent_time` là lúc thật sự gửi, nên `sent_time − event_time` là độ trễ.
- Event trễ cố ý phá thứ tự (ví dụ một `view` trễ đến sau `purchase` của cùng user). Không dùng `--late-rate` thì thứ tự luôn được giữ.
- Mặc định giữ lại 6–60 giây, đủ lâu để thử chính sách late arrival của Stream Analytics. Ngưỡng của job do Thắng cấu hình.

**Giới hạn tốc độ.** Dataset trung bình 26.5 event/giây, đỉnh 243 event/giây. Một TU Event Hubs nhận 1,000 event/giây, nên `speed` tối đa khoảng 4 nếu không lấy mẫu.
