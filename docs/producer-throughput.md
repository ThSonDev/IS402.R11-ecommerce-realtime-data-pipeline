# Throughput của producer: Kafka local và Event Hubs

Người đo: Minh. Ngày đo: 14/11/2026, khoảng 15:45–16:22 UTC (22:45–23:22 giờ Việt Nam). Phục vụ báo cáo mục 3.1 (tốc độ ghi, throughput).

## Mục đích

1. Đo tốc độ tối đa của chính producer (đọc Parquet, làm giàu, gửi) khi đích nhận không giới hạn: Kafka local.
2. Đo tốc độ gửi tối đa lên Azure Event Hubs (1 TU) và tìm xem giới hạn nằm ở đâu.

## Điều kiện đo

| Mục | Giá trị |
|---|---|
| Máy | AMD Ryzen 9 7945HX (16 nhân / 32 luồng), WSL2 Ubuntu được cấp 7.6 GiB RAM |
| Phần mềm | Python 3.12.8, `confluent-kafka` 2.11.0, producer một luồng |
| Kafka local | Apache Kafka 3.9.0 trong Docker, 1 node KRaft, topic `events` 3 partition |
| Event Hubs | `evhns-megasale-dev`, Standard, **1 TU**, region `japaneast`, hub `events` 4 partition, giao thức Kafka (SASL_SSL, cổng 9093) |
| Cấu hình producer | `enable.idempotence=true`, key = `user_id`, hàng đợi client tối đa 10,000 message (lần đo đầu ở mức 500 và 1,000 dùng mặc định của client) |
| Dữ liệu | REES46, từ 2019-11-01 09:00 UTC (giờ cao điểm) |
| Kích thước event | Trung bình khoảng 637 byte (Incoming Bytes / Incoming Messages trên Event Hubs) |

## Phương pháp

Dùng `scripts/bench_producer.py`: chạy `producer/main.py --rate N` ở từng mức, mỗi lần khoảng 60 giây, lặp 3 lần, nghỉ 5 giây giữa các lần. Tốc độ báo cáo là số event **đích đã xác nhận nhận được** chia cho thời gian chạy (tính cả lúc khởi động và lúc gửi nốt hàng đợi). `behind schedule` là producer chậm hơn lịch bao nhiêu giây ở cuối lần chạy: gần 0 nghĩa là đích theo kịp. Mức `--rate 100000` cao hơn hẳn khả năng thực tế, dùng để đo mức trần.

```bash
python scripts/bench_producer.py                                    # 500, 1,000, 1,500, 2,000, tối đa
python scripts/bench_producer.py --rates 1500,2000,100000           # chỉ các mức cao
KAFKA_LINGER_MS=50 KAFKA_BATCH_SIZE=1000000 python scripts/bench_producer.py --rates 100000   # gửi theo lô lớn
```

Đích (Kafka local hay Event Hubs) lấy từ `.env` (`scripts/fill_env.py`). Đối chiếu thêm metrics của Event Hubs (`IncomingMessages`, `IncomingBytes`, `ThrottledRequests`, theo phút) bằng `az monitor metrics list`.

## Kết quả

### Kafka local: mức trần của producer

`--rate 100000 --limit 200000`, 3 lần:

| Lần | Thời gian | ev/s |
|---|---|---|
| 1 | 5.4 s | 37,153 |
| 2 | 5.3 s | 37,560 |
| 3 | 5.3 s | 37,875 |
| **Trung bình** | | **37,529** |

Cả 3 lần đều 0 lỗi, 0 event chưa gửi. Producer chạy một luồng nên con số này là sức của một nhân CPU.

### Event Hubs (1 TU)

| `--rate` đặt | ev/s đích nhận (trung bình 3 lần) | Nhỏ nhất – lớn nhất | Trễ lịch cuối lần chạy | Lỗi |
|---|---|---|---|---|
| 500 | 499 | 499–499 | 0.0 s | 0 |
| 1,000 | 997 | 997–998 | 0.0 s | 0 |
| 1,500 | 1,382 | 1,352–1,423 | 0.0 s | 0 |
| 2,000 | 1,508 | 1,340–1,592 | 11.7 s | 0 |
| tối đa (100,000) | 1,524 | 1,504–1,542 | 71.5 s | 0 |
| tối đa, gửi theo lô lớn (`linger.ms=50`, `batch.size=1,000,000`) | 1,788 | 1,544–2,266 | 68.8 s | 0 |

Ghi chú:

- Hai mức 500 và 1,000 đo bằng phiên bản script đầu (đếm event đã đưa vào hàng đợi). Ở hai mức này trễ lịch bằng 0 và không có event nào chưa gửi, nên con số trùng với số event đích nhận.
- Ở mức 1,500, ev/s thấp hơn 1,500 dù trễ lịch bằng 0 vì thời gian chạy tính cả lúc khởi động và lúc gửi nốt.
- Hai lần ở mức 2,000 có 693 và 653 event chưa gửi kịp: script dừng lần chạy đúng lúc producer đang gửi nốt hàng đợi. Đây là giới hạn của cách đo, không phải Event Hubs từ chối.
- Thí nghiệm gửi theo lô: lần 1 đạt 2,266 ev/s ngay sau một khoảng nghỉ, lần 2 và 3 về 1,544 và 1,554 ev/s.

### Metrics phía Event Hubs

- Lần đo đầu (500, 1,000 và một lần thử 1,500): tổng `IncomingMessages` 360,100, khớp đúng số event producer đã gửi (100 gửi thử + 90,000 + 180,000 + 90,000).
- Khi chạy ở các mức cao: ổn định khoảng 70,000–85,000 message/phút, tức khoảng 45–54 MB/phút (0.75–0.9 MB/giây). Có một phút đạt 119,658 message (khoảng 76 MB, tức 1.27 MB/giây), trùng lần 1 của thí nghiệm gửi theo lô.
- `ThrottledRequests` bằng 0 trong toàn bộ thời gian đo.

## Nhận xét

1. **Producer không phải nút thắt.** Trên máy đo, producer gửi được khoảng 37,500 ev/s, gấp khoảng 25 lần mức Event Hubs nhận được.
2. **Đến khoảng 1,000 ev/s Event Hubs nhận kịp hoàn toàn** (trễ lịch 0, không lỗi). Từ khoảng 1,500 ev/s trở lên, tốc độ dừng quanh **1,500–1,550 ev/s** dù đặt mức cao hơn bao nhiêu, và trễ lịch tăng dần.
3. **Mức dừng khớp giới hạn dung lượng hơn là giới hạn số event.** 1 TU cho phép nhận 1,000 event/giây hoặc 1 MB/giây. Với event khoảng 637 byte, 1 MB/giây tương đương khoảng 1,570 event/giây, gần mức dừng đo được. Vì vậy, với event của nhóm, giới hạn 1,000 event/giây không bị áp dụng chặt, và giới hạn có tác dụng là dung lượng. Đây là suy luận từ số đo, chưa đối chiếu với tài liệu chính thức về cách Event Hubs đếm event nhận qua giao thức Kafka.
4. **Giới hạn nằm ở Event Hubs, không ở đường mạng.** Gửi theo lô lớn hơn không nâng được tốc độ ổn định (1,544–1,554 ev/s so với 1,504–1,542 ev/s).
5. **Event Hubs cho phép vượt ngắn hạn sau lúc rảnh** (2,266 ev/s trong khoảng một phút), rồi quay về mức ổn định.
6. **`ThrottledRequests` bằng 0 dù đã chạm trần.** Khả năng là với client Kafka, Event Hubs làm chậm việc trả lời thay vì từ chối request, nên metric này không ghi nhận. Muốn thấy việc bị giới hạn phải nhìn tốc độ dừng lại và trễ lịch tăng.

## Đối chiếu với lượt đo trong `docs/event-time-policy.md`

Lượt chạy cloud ngày 17/11/2026 ([event-time-policy.md](event-time-policy.md), mục Throughput) ghi nhận 1,451 ev/s ở mức 1,500 và 1,922 ev/s ở mức 2,000, cao hơn mức ổn định khoảng 1,520 ev/s đo ở đây. Hai kết quả không mâu thuẫn, vì đo hai thứ khác nhau:

| | Lượt 17/11 | Tài liệu này |
|---|---|---|
| Độ dài mỗi đợt | 10,000 event (khoảng 5–7 giây ở mức 1,500–2,000 ev/s) | Khoảng 60 giây, lặp 3 lần mỗi mức |
| Hàng đợi của client | Mặc định của client (khoảng 100,000 message) | Giới hạn 10,000 message |
| Tốc độ báo cáo | Tốc độ trong tiến trình producer | Số event Event Hubs đã xác nhận chia cho thời gian, tính cả lúc gửi nốt |

- Đợt chỉ vài giây nằm gọn trong khả năng vượt ngắn hạn của Event Hubs (nhận xét 5), nên đạt gần mức đặt. Bản thân tài liệu 17/11 cũng ghi đó là đợt ngắn, không phải phép đo tải bền vững.
- Với hàng đợi lớn, 10,000 event có thể vào hết hàng đợi trong RAM trước khi Event Hubs xác nhận. Nếu con số 17/11 lấy từ dòng tiến độ (in ngay khi đã đưa 10,000 event vào hàng đợi) thì nó là tốc độ đưa vào hàng đợi, chưa phải tốc độ Event Hubs nhận. Nếu lấy từ dòng `done:` (đã tính cả thời gian gửi nốt) thì chênh lệch chủ yếu do vượt ngắn hạn. Tài liệu 17/11 không ghi rõ dùng dòng nào. Dù vậy, lượt đó vẫn giao đủ mọi event (0 failed, 0 not delivered).

Vì vậy, dùng **khoảng 1,500 ev/s** làm tốc độ gửi tối đa ổn định với 1 TU, và **khoảng 1,900–2,300 ev/s** là mức đạt được trong đợt ngắn vài giây đến một phút.

## Hệ quả cho demo và vận hành

- Muốn không trễ, giữ lưu lượng **dưới khoảng 1,000 ev/s** với 1 TU. Giờ cao điểm của dataset là 243 ev/s nên `--speed` tối đa khoảng 4. Muốn nhanh hơn thì dùng thêm `--sample-rate` hoặc tăng TU (tốn thêm chi phí).
- Không dùng `ThrottledRequests` để phát hiện nghẽn. Theo dõi `IncomingMessages` / `IncomingBytes` và trễ lịch của producer.

## Hạn chế

- Chỉ một máy, một đường mạng, một buổi đo.
- Hiệu ứng vượt ngắn hạn làm lần chạy đầu sau lúc rảnh cao hơn bình thường. Nên bỏ qua lần đầu hoặc chạy làm nóng trước khi đo.
- Metrics Event Hubs gộp theo phút nên lẫn cả thời gian nghỉ giữa các lần chạy.
