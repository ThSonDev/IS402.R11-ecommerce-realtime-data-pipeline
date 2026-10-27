# Kế hoạch dự án

Đồ án IS402.R11 – Điện toán đám mây. Hạn hoàn thành nội bộ: **01/12/2026**.

Tài liệu này dành cho cả nhóm: mục tiêu, cách hệ thống hoạt động, lịch 5 tuần, quy tắc làm việc chung. Việc chi tiết của từng người nằm trong thư mục `plan/`:

- [plan/Son.md](plan/Son.md) – hạ tầng Azure, CI/CD, Grafana, đo độ trễ, tổng hợp báo cáo
- [plan/Minh.md](plan/Minh.md) – producer, môi trường dev local, Azure Function cảnh báo, đánh giá luật
- [plan/Thang.md](plan/Thang.md) – Stream Analytics, data lake, Synapse, tối ưu lưu trữ
- [plan/Tuan.md](plan/Tuan.md) – Power BI, phân quyền RLS, mobile, slide thuyết trình

## 1. Mình đang làm gì

Một thương hiệu đồ điện tử bán hàng trên cả Tiki, Shopee và Lazada. Trong các đợt sale lớn, họ cần một "phòng điều khiển" để xem theo thời gian thực: đang bán được bao nhiêu, ở đâu, sản phẩm nào; có ai đang gian lận không; hệ thống có đang gặp sự cố không.

Nhóm xây hệ thống đó trên Azure. Dữ liệu là log mua sắm thật của dataset REES46 (tháng 11/2019, 67.5 triệu event), được phát lại như đang diễn ra lúc này, gắn thêm bối cảnh Việt Nam và chèn các kịch bản gian lận có nhãn để kiểm chứng.

Hệ thống phát hiện gian lận và sự cố bằng 4 luật:

1. Bot gom hàng: một user đặt quá nhiều đơn trong 1 phút.
2. Săn voucher: một thiết bị gắn với nhiều tài khoản mới.
3. Sai giá: giá bán lệch mạnh so với giá niêm yết.
4. Sự cố: số đơn mỗi phút tăng hoặc giảm bất thường.

## 2. Hệ thống chạy như thế nào

```
Dataset REES46 ─► Producer (Python) ─► Event Hubs ─► Stream Analytics ─┬─► Power BI (dashboard real-time)
                  (dev: Kafka local)                     ▲              ├─► Data lake (Parquet) ─► Synapse ─► Power BI (báo cáo lịch sử)
                                                reference data          ├─► Azure SQL DB ─► Grafana (giám sát + cảnh báo)
                                                                        └─► Azure Function ─► Discord/Telegram
```

Đọc từ trái sang phải:

- **Producer** đọc dataset, phát lại theo thời gian, gửi từng event vào Event Hubs.
- **Stream Analytics** tính số liệu theo từng phút và chạy 4 luật.
- Kết quả đi ra 4 nơi:
  - Power BI cho quản lý.
  - Data lake để lưu trữ và phân tích lịch sử.
  - Azure SQL DB cho Grafana, nơi đội vận hành theo dõi.
  - Azure Function để gửi cảnh báo.

Định dạng dữ liệu ở từng chặng nằm trong [docs/event-schema.md](docs/event-schema.md). Đây là tài liệu quan trọng nhất cần đọc trước khi bắt đầu code.

Toàn bộ hạ tầng Azure được khai báo bằng Terraform trong `infra/`. Không ai tạo resource bằng tay trên Portal, trừ khi đã thống nhất với Sơn.

## 3. Phân công

| Người | Phụ trách chính | Phần rubric gánh chính |
|---|---|---|
| Sơn | Hạ tầng Azure, Event Hubs, Azure SQL DB, Grafana, CI/CD, đo độ trễ nhiều region, chi phí, tổng hợp báo cáo Word, kịch bản demo | 1.4, 2.3, 3.3, 5.2, 5.4 |
| Minh | Producer, Kafka local, Azure Function cảnh báo, benchmark local vs cloud, đánh giá precision/recall | 1.1–1.3, 3.1 |
| Thắng | Query Stream Analytics (KPI + 4 luật), reference data, data lake, Synapse star schema, tối ưu lưu trữ | 2.1, 2.2, 3.2, 3.4 |
| Tuấn | Power BI: dashboard real-time, báo cáo 4+ trang, RLS, chia sẻ, mobile; slide thuyết trình | 4 (toàn bộ), 5.1 |

Mỗi người tự viết phần báo cáo của mình, Sơn ghép lại. Mục 5.3 (thuyết trình và demo) cả nhóm cùng làm.

## 4. Lịch 5 tuần

| Tuần | Thời gian | Mốc cần đạt cuối tuần |
|---|---|---|
| 1 | 27/10 – 02/11 | Chốt data contract. Mỗi người chạy được phần của mình trên máy local. Azure có resource group, budget, quyền cho cả nhóm |
| 2 | 03/11 – 09/11 | Pipeline end-to-end đầu tiên trên cloud: producer → Event Hubs → Stream Analytics → Power BI + data lake + SQL DB, chỉ với số liệu KPI đơn giản |
| 3 | 10/11 – 16/11 | Đủ 4 luật. Synapse có star schema. Grafana có dashboard. Function gửi được cảnh báo. Power BI có bản nháp 4 trang |
| 4 | 17/11 – 23/11 | Hoàn thiện RLS, chia sẻ, mobile. Chạy các thí nghiệm: độ trễ nhiều region, throughput, local vs cloud, tối ưu lưu trữ, precision/recall. **Đóng băng tính năng** cuối tuần này |
| 5 | 24/11 – 01/12 | Viết xong báo cáo Word và slide, quay video demo dự phòng, tổng duyệt, chốt chi phí, dọn resource |

Tuần 4 là tuần cuối cùng được thêm tính năng. Sang tuần 5 chỉ sửa lỗi và viết báo cáo.

Báo cáo không để dồn đến tuần 5. Mỗi tuần, ai làm xong phần nào thì ghi luôn phần đó vào `docs/` (chụp màn hình, số liệu, giải thích ngắn).

## 5. Quy tắc làm việc chung

### Git và GitHub

- Không commit thẳng lên `main`. Mỗi việc làm trên một nhánh riêng, đặt tên ngắn, ví dụ `minh/producer-replay`, `thang/asa-rule-bot`.
- Xong thì mở Pull Request vào `main`. GitHub tự gán người review theo `CODEOWNERS`. Cần ít nhất 1 người duyệt mới merge.
- Commit message tiếng Anh, ngắn, có tiền tố: `feat:`, `fix:`, `docs:`, `chore:`, `test:`. Ví dụ `feat: add bot detection rule`.
- Việc cần làm được quản lý bằng GitHub Issues và một bảng GitHub Projects. Mỗi issue gắn người phụ trách và tuần. Bảng này và lịch sử PR là bằng chứng cộng tác cho mục 5.4 của rubric.
- Không commit dữ liệu (`data/`), secret (`.env`, `*.tfvars`), file `.pbix`.

### Môi trường

- Cả nhóm dùng **Python 3.12.8 trở lên**. Kiểm tra bằng `python --version` trước khi tạo venv.
- Python dùng venv trong repo, cài thư viện từ `requirements.txt`. Thêm thư viện mới thì ghi đúng phiên bản vào file này trong cùng PR.
- Lấy dữ liệu theo hướng dẫn trong [data/README.md](data/README.md).
- Môi trường dev local (Kafka, Grafana) chạy bằng Docker. Không cần Azure để phát triển phần lớn tính năng.
- Lệnh trong tài liệu: ghi lệnh Windows trước, dòng dưới là `# Linux: ...` nếu khác.

### Azure và chi phí

Ngân sách thật cho cả đồ án khoảng 30 USD, nằm trên subscription của Sơn. Mấy việc tốn tiền nhất là để quên resource chạy, nên:

- Stream Analytics chỉ start khi đang test hoặc demo, xong là stop. Job đang chạy tính tiền theo giờ.
- Event Hubs và các resource tính tiền theo thời gian tồn tại được dựng lên khi cần và xóa đi khi xong buổi, bằng Terraform.
- Tuyệt đối không tạo Synapse dedicated SQL pool, Databricks, hay máy ảo.
- Trước khi tạo hoặc bật resource mới, báo vào nhóm chat.
- Tiền thật xem ở Cost Management, không tin số ước tính.

Region mặc định là `japaneast`. Chỉ dùng được 5 region trường cho phép: `japaneast`, `japanwest`, `koreacentral`, `centralindia`, `indonesiacentral`.

### Viết số và tài liệu

- Số: dấu `,` phân cách hàng nghìn, dấu `.` phân cách thập phân (`67,501,979`, `1.5`).
- Tài liệu và báo cáo viết tiếng Việt. Code, tên biến, commit viết tiếng Anh.
- Mọi con số đưa vào báo cáo phải đo được hoặc có nguồn. Không ước lượng rồi ghi như số thật.

## 6. Báo cáo cuối kỳ cần những gì

Theo rubric, báo cáo Word và slide phải trả lời đủ các phần dưới đây. Cột cuối là người viết chính.

| Phần | Nội dung | Người viết |
|---|---|---|
| 1. Giới thiệu bài toán | Loại bài toán, loại dữ liệu, kích thước dữ liệu, so sánh tốc độ xử lý trên máy thường và trên cloud | Minh |
| | Các dịch vụ cloud dùng, thuộc nhóm IaaS / PaaS / FaaS / SaaS | Sơn |
| 2. Cơ sở lý thuyết | Định dạng lưu trữ (CSV, JSON, Parquet), xử lý luồng (window, event time, dữ liệu trễ, phát hiện bất thường) | Thắng |
| | Giới thiệu chi tiết các dịch vụ Azure dùng trong đồ án | Sơn |
| 3. Mô hình dữ liệu | Tốc độ đọc/ghi, throughput | Minh |
| | Luồng ETL tự động | Thắng |
| | Độ trễ khi đặt server ở nhiều region | Sơn |
| | Tối ưu lưu trữ và tốc độ đọc/ghi | Thắng |
| 4. Hiện thực | Dashboard, RLS, chia sẻ, mobile, cập nhật real-time | Tuấn |
| | Đánh giá 4 luật (precision/recall) | Minh |
| 5. Quản lý dự án | Phân quyền trên Azure, GitHub, chi phí và quota | Sơn |

Định dạng Word và slide theo mẫu khóa luận tốt nghiệp UIT: đúng font, đánh số hình và bảng, có tài liệu tham khảo. Nguồn dataset bắt buộc phải trích (link Kaggle và REES46).

## 7. Demo

Buổi demo nên đi theo một câu chuyện, khoảng 10 phút:

1. Giới thiệu bài toán và kiến trúc.
2. Bật producer, dashboard real-time bắt đầu chạy.
3. Bật một kịch bản gian lận, cảnh báo xuất hiện trên Grafana và tin nhắn Discord/Telegram.
4. Phát lại đoạn sự cố thật trong dataset (14–17/11/2019), luật 4 bắt được.
5. Mở báo cáo Power BI lịch sử bằng hai tài khoản khác nhau, mỗi người chỉ thấy dữ liệu sàn/miền của mình.
6. Mở trên điện thoại.
7. Kết quả thí nghiệm: độ trễ, chi phí, precision/recall.

Luôn có video quay sẵn để dự phòng nếu mạng hoặc Azure gặp sự cố lúc demo.

## 8. Mốc ngoài cần nhớ

- Power BI Pro trial của Sơn hết hạn khoảng **18/12/2026**. Demo phải trước ngày đó. Các thành viên khác bật trial của mình trong tuần 1.
- Microsoft đã thông báo ngừng tính năng real-time streaming của Power BI (mốc 31/10/2027). Vẫn dùng được cho đồ án, nhưng cần nêu trong báo cáo.

## 9. Khi gặp vấn đề

- Kẹt quá nửa ngày thì hỏi trong nhóm, đừng ôm.
- Thay đổi data contract, kiến trúc hoặc phân công thì phải báo cả nhóm và cập nhật tài liệu này.
- Mỗi tuần họp nhanh một lần (khoảng 30 phút): mỗi người nói đã xong gì, tuần tới làm gì, đang kẹt gì.
