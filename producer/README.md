# producer/ – Python producer

Phụ trách: Minh

## Làm gì

Đọc `data/processed/2019-Nov.parquet`, bỏ dòng trùng, làm giàu bối cảnh Việt Nam, dịch thời gian sang trục replay và tạo event đúng [docs/event-schema.md](../docs/event-schema.md).

| File | Chức năng |
|---|---|
| `reader.py` | `read_events(path, start, end)`: đọc một khoảng thời gian, bỏ dòng trùng, sắp xếp ổn định, trả từng dòng (dict). Đọc theo khúc 10,000 dòng |
| `enrich.py` | `load_provinces(path)`, `enrich(row, provinces, event_time, sent_time)`: dòng gốc thành event 22 trường |
| `timeshift.py` | `parse_raw`, `replay_time`, `to_iso_ms`: đặt thời gian 2019 lên trục replay |

Chưa có: gửi vào Kafka / Event Hubs (`main.py`), kịch bản gian lận, event trễ.

## Cách chạy

Chạy từ thư mục gốc repo. Kafka local (Kafka UI ở http://localhost:8080, producer kết nối `localhost:9092`):

```powershell
docker compose up -d
```

Thử reader và enrich trong Python:

```powershell
.venv\Scripts\python
# Linux: .venv/bin/python
```

```python
import sys; sys.path.insert(0, "producer")
import reader, enrich
provinces = enrich.load_provinces("stream/reference/provinces.csv")
row = next(reader.read_events("data/processed/2019-Nov.parquet", "2019-11-01 09:00:00 UTC", "2019-11-01 09:05:00 UTC"))
print(enrich.enrich(row, provinces))
```

## Input / Output

- Input: `data/processed/2019-Nov.parquet` (xem [data/README.md](../data/README.md)), `stream/reference/provinces.csv`.
- Output: event dạng dict / JSON theo contract. File mẫu: `stream/test/events_sample.json` (1,036 event, JSON Lines).

## Lưu ý và giả định

**Tính xác định.** Mọi trường giả lập được tính từ SHA-256 với `SEED = "IS402R11"`, không dùng `random` hay `hash()`. Cùng tham số thì ra cùng dữ liệu. Đổi seed thì mọi trường giả lập đổi theo.

**Dữ liệu gốc.**
- Bỏ 100,519 dòng trùng hoàn toàn. Dòng trùng luôn nằm trong cùng một giây.
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
- `event_time = replay_start + (original_time − original_start) / speed`. Dịch +4h để cao điểm gốc 08–10 UTC rơi vào 19–21h giờ Việt Nam.
- Khi chạy thật `replay_start` là giờ máy. File mẫu dùng mốc cố định 2026-11-11 13:00 UTC.
- `sent_time` trong file mẫu bằng `event_time` (giữ chỗ), không dùng để đo độ trễ.

**Giới hạn tốc độ.** Dataset trung bình 26.5 event/giây, đỉnh 243 event/giây. Một TU Event Hubs nhận 1,000 event/giây, nên `speed` tối đa khoảng 4 nếu không lấy mẫu.
