# Kế hoạch – Sơn (Lead)

Vai trò: dựng và giữ hạ tầng Azure cho cả nhóm, lo CI/CD, giám sát vận hành (Grafana), đo độ trễ nhiều region, quản lý chi phí. Cuối kỳ tổng hợp báo cáo Word và kịch bản demo.

Thư mục phụ trách: `infra/`, `.github/`, `dashboards/grafana/`, `scripts/` (phần deploy, đo độ trễ), `docs/`.

## Kết quả cuối cùng cần có

| Hạng mục | Kết quả mong đợi |
|---|---|
| Hạ tầng | `terraform apply` dựng toàn bộ hệ thống, `terraform destroy` xóa sạch. Không có resource nào tạo tay |
| Quyền | Cả 4 người cùng làm trên một resource group, có ảnh chụp IAM làm bằng chứng |
| CI/CD | Mỗi PR tự chạy kiểm tra code. Deploy lên Azure chạy bằng GitHub Actions qua OIDC |
| Grafana | Dashboard war room và alert rule, nạp tự động từ file trong Git |
| Độ trễ | Bảng so sánh độ trễ giữa ít nhất 3 region |
| Chi phí | Bảng chi phí thật theo từng dịch vụ, lấy từ Cost Management, cùng quota đã dùng |
| Báo cáo | File Word hoàn chỉnh theo mẫu KLTN, kịch bản demo, video demo dự phòng |

## Tuần 1 (27/10 – 02/11): nền móng

Giao cho: cả nhóm. Quyền truy cập resource group trên Azure.

Việc cần làm:

- Đăng ký các provider còn thiếu: `Microsoft.EventHub`, `Microsoft.StreamAnalytics`, `Microsoft.Synapse`, `Microsoft.Web`, `Microsoft.Insights`, `Microsoft.Sql`.
- Tạo resource group ở `japaneast`. Đặt budget 30 USD, cảnh báo ở các mức 50%, 80% và 100%.
- Cấp role cho Minh, Thắng, Tuấn trên resource group.
- Tạo storage account riêng chứa Terraform state, bằng một script `az` chạy một lần (Terraform không tự tạo được nơi lưu state của chính nó).
- Viết khung Terraform: provider, backend, biến, quy ước đặt tên resource.
- Hoàn tất OIDC cho GitHub Actions:
  - Đổi tên app registration cho dễ nhận biết.
  - Thêm federated credential.
  - Gán role Contributor trong phạm vi resource group.
  - Thêm các biến `AZURE_*` vào GitHub Variables.
- Tạo bảng GitHub Projects, chuyển việc trong `plan/` thành issue.
- Chốt data contract với cả nhóm.

Kết quả mong đợi:

- Ba bạn kia đăng nhập Portal là thấy resource group.
- `terraform plan` chạy được, cả trên máy lẫn trên GitHub Actions.
- Bảng Projects có đủ issue của tuần 1–2.

## Tuần 2 (03/11 – 09/11): pipeline đầu tiên trên cloud

Phụ thuộc: Minh. Producer gửi được event.

Phụ thuộc: Thắng. File query Stream Analytics và định nghĩa các output.

Giao cho: cả nhóm. Thông tin kết nối trong `.env`.

Việc cần làm:

- Terraform cho các thành phần chính:
  - Event Hubs Standard: namespace, event hub `events`, consumer group riêng cho Stream Analytics.
  - Storage ADLS Gen2: container cho reference data và data lake.
  - Azure SQL Database bản free offer, bật auto-pause khi hết hạn mức.
  - Stream Analytics job: đọc query từ `stream/query.asaql`, khai báo input và output.
  - Synapse workspace, chỉ dùng serverless.
- Workflow deploy chạy tay, và workflow CI chạy `ruff`, `pytest`, `terraform fmt` / `validate`.
- Cùng Minh và Thắng chạy pipeline end-to-end lần đầu.
- Đưa connection string cho các bạn qua `.env` (không commit).

Kết quả mong đợi:

- Producer của Minh gửi được vào Event Hubs.
- Job của Thắng chạy và ghi ra data lake, SQL DB, Power BI.
- Một lệnh `terraform destroy` xóa hết, một lệnh `apply` dựng lại được.

## Tuần 3 (10/11 – 16/11): giám sát và cảnh báo

Phụ thuộc: Minh. Code Azure Function `fraud_alert`.

Giao cho: cả nhóm. Dashboard Grafana.

Việc cần làm:

- Thêm Grafana vào `docker-compose.yml`, nạp sẵn data source Azure SQL và dashboard qua provisioning.
- Dashboard war room gồm:
  - Số đơn mỗi giây.
  - GMV theo sàn.
  - Bảng cảnh báo mới nhất.
  - Độ trễ pipeline.
  - Trạng thái 4 luật.
- Alert rule của Grafana gửi về Discord hoặc Telegram.
- Terraform cho Function App (consumption plan) và output từ Stream Analytics sang Function. Code của Function do Minh viết.

Kết quả mong đợi:

- Bật kịch bản bot, sau vài giây Grafana hiện cảnh báo và có tin nhắn gửi về.

## Tuần 4 (17/11 – 23/11): thí nghiệm và số liệu

Giao cho: Tuấn. Hỗ trợ quyền trong tenant khi chia sẻ báo cáo.

Việc cần làm:

- Đo độ trễ nhiều region:
  - Dựng tạm Event Hubs ở `japaneast`, `koreacentral`, `centralindia` trong 1–2 giờ.
  - Từ máy ở Việt Nam, gửi cùng một lượng event tới từng region, đo thời gian gửi và độ trễ end-to-end.
  - Đo xong xóa ngay.
- Tổng hợp chi phí thật từ Cost Management. Chụp màn hình quota.
- Lập bảng các dịch vụ đã dùng, xếp vào nhóm IaaS / PaaS / FaaS / SaaS.
- Hỗ trợ Tuấn phần chia sẻ và RLS (tài khoản trong tenant, quyền Viewer).

Kết quả mong đợi:

- Bảng độ trễ có trung bình và p95 cho từng region, kèm giải thích ngắn vì sao khác nhau.
- Bảng chi phí có số thật.

## Tuần 5 (24/11 – 01/12): báo cáo và demo

Phụ thuộc: cả nhóm. Phần báo cáo của từng người.

Giao cho: Tuấn. Slide phần hạ tầng, độ trễ và chi phí.

Việc cần làm:

- Ghép báo cáo Word từ phần của mọi người, theo mẫu KLTN UIT: font, đánh số hình/bảng, mục lục, tài liệu tham khảo.
- Viết kịch bản demo theo mục 7 của `PLAN.md`, quay video dự phòng.
- Tổng duyệt với cả nhóm ít nhất một lần.
- Sau demo chạy `terraform destroy`, kiểm tra Cost Management không còn phát sinh.

Kết quả mong đợi:

- Bản Word hoàn chỉnh trước 30/11 để còn một ngày soát lỗi.

## Gợi ý và lưu ý

- Mỗi dịch vụ một file `.tf`, chưa cần chia module. Đặt tên resource theo một mẫu chung, ví dụ `<loại>-megasale-<môi trường>`.
- Dùng `MSYS_NO_PATHCONV=1` khi chạy `az` trong Git Bash.
- Một số tham số chưa xác minh cần kiểm tra trên Cost Management sau ngày đầu dùng: meter Kafka endpoint của Event Hubs Standard (bảng giá có ghi 0.09 USD/giờ).
- Azure SQL free offer chỉ tự pause khi không còn kết nối. Nhắc cả nhóm tắt Stream Analytics và Grafana sau mỗi buổi.
- Budget chỉ gửi email, không tự chặn chi tiêu. Nên tự kiểm tra Cost Management mỗi vài ngày.

## Phần báo cáo phải viết

- 1.4: các thành phần cloud và phân loại IaaS / PaaS / FaaS / SaaS.
- 2.3: giới thiệu chi tiết từng dịch vụ Azure dùng trong đồ án.
- 3.3: đo độ trễ nhiều region.
- 5: quản lý dự án trên cloud (IAM, GitHub, chi phí, quota).
- Phần mở đầu, kết luận, tổng hợp toàn bộ báo cáo.
