# Rubric đánh giá

| STT | Tiêu chí | Điểm | Chi tiết |
|:---:|---|---:|---|
| 1 | Giới thiệu bài toán | **1,5** | |
| 2 | Cơ sở lý thuyết | **1,5** | |
| 3 | Mô hình dữ liệu | **2,0** | |
| 4 | Hiện thực phân tích / trực quan dữ liệu | **3,0** | Có thể rơi vào 1 trong 3 trường hợp sau: Web, Trực quan dữ liệu, Phân tích tiên đoán dữ liệu. |
| 5 | Trình bày báo cáo & Thực hiện quản lý dự án trên môi trường điện toán đám mây | **2,0** | |

## 1. Giới thiệu bài toán — 1,5 điểm

| STT | Nội dung | Điểm | Chi tiết |
|:---:|---|---:|---|
| 1 | Giới thiệu loại bài toán | 0,25 | Giới thiệu loại bài toán thuộc nhóm: lưu trữ, thu thập, trực quan, xử lý. |
| 2 | Loại dữ liệu | 0,25 | WEB; Database; Data Analyst; Dataset. |
| 3 | Kích thước dữ liệu - dung lượng bộ nhớ cho xử lý | 0,75 | >4GB; 0,25-KB; 0,5-MB; 0,75-GB. So sánh tốc độ xử lý trong trường hợp máy chủ truyền thống và hệ thống cloud. |
| 4 | Các thành phần sử dụng trong cloud | 0,25 | Liệt kê, giới thiệu các thành phần sử dụng trong cloud thuộc nhóm nào: IaaS, PaaS, FaaS, SaaS. |

## 2. Cơ sở lý thuyết — 1,5 điểm

| STT | Nội dung | Điểm | Chi tiết |
|:---:|---|---:|---|
| 1 | Cơ sở lý thuyết về định dạng lưu trữ | 0,5 | Web - Visualize; Database; Train model; Dataset - Storage cloud?? |
| 2 | Cơ sở lý thuyết về thuật toán xử lý | 0,5 | Xử lý luồng dữ liệu. Web - luồng dữ liệu, logic của trang web. DA - model - lý thuyết model. |
| 3 | Các dịch vụ sử dụng cloud | 0,5 | Trình bày chi tiết các dịch vụ sử dụng cloud. |

## 3. Mô hình dữ liệu — 2,0 điểm

| STT | Nội dung | Điểm | Chi tiết |
|:---:|---|---:|---|
| 1 | Tốc độ cho phép đọc / ghi | 0,5 | |
| 2 | Thiết lập luồng xử lý dữ liệu tự động ETL | 0,5 | WEB: data nhận từ client → detect → lưu trữ vào trong storage cloud. Data analyst: Collect data. |
| 3 | Đo độ trễ (delay) | 0,5 | Khi thiết lập server ở từng region khác nhau. |
| 4 | Tối ưu hóa lưu trữ và tốc độ đọc / ghi | 0,5 | Các giải pháp thực hiện tối ưu hóa cho việc lưu trữ dữ liệu và cải thiện tốc độ đọc / ghi dữ liệu từ vùng lưu trữ sang các ứng dụng. |

## 4. Hiện thực phân tích / trực quan dữ liệu — 3,0 điểm

**Có thể rơi vào 1 trong 3 trường hợp sau: Web, Trực quan dữ liệu, Phân tích tiên đoán dữ liệu.**

### Web

| Nội dung | Điểm |
|---|:---:|
| Deploy trang web lên hệ thống cloud ít nhất có 4 trang: trang chủ, trang chi tiết, trang thêm vào giỏ hàng, trang liệt kê giỏ hàng. | 1,0 |
| Triển khai hệ thống Blue / Green. | 0,5 |
| Triển khai 2 service: service đăng ký tài khoản người dùng, service mua sản phẩm - giao tiếp giữa 2 service. | 1,0 |
| Sử dụng FaaS. Chức năng function trong Azure. | 0,5 |

### Trực quan dữ liệu

| Nội dung | Điểm |
|---|:---:|
| Deploy 1 dashboard lên SaaS, ít nhất có 4 report: trang tổng quan, trang chi tiết, trang filter 1, filter 2. Sử dụng các button, navigation để điều hướng giữa các report. | 1,0 |
| 4 report | 0,75 |
| Navigation giữa các report | 0,25 |
| Triển khai việc cập nhật dữ liệu tức thời từ mô hình dữ liệu lên dashboard. | 0,5 |
| Thực hiện các phương pháp bảo mật như chia sẻ dashboard đến người dùng xem, và ràng buộc từng nhóm người chỉ được xem một vài loại dữ liệu nhất định. | 1,0 |
| Thực hiện Responsive, cho phép xem các dashboard trên mobile. | 0,5 |

### Phân tích dữ liệu

| Nội dung | Điểm |
|---|:---:|
| Hiện thực huấn luyện model trên tập dữ liệu. | 1,0 |
| Cung cấp cơ chế API cho phép sử dụng model. | 0,5 |
| Trực quan kết quả trên các tham số hoặc trên các loại model. | 1,0 |
| Viết trang web sử dụng API của model: gửi request đến hệ thống cloud và nhận kết quả trả về đồng thời parse kết quả. | 0,5 |

## 5. Trình bày báo cáo & Thực hiện quản lý dự án trên môi trường điện toán đám mây — 2,0 điểm

| Nội dung | Điểm | Chi tiết |
|---|:---:|---|
| PowerPoint báo cáo | 0,5 | Theo định dạng báo cáo KLTN. Lỗi font chữ, chính tả, hình ảnh, số hình, số bảng biểu, tài liệu tham khảo, ... |
| Word báo cáo | 0,5 | Theo định dạng báo cáo KLTN. Lỗi font chữ, chính tả, hình ảnh, số hình, số bảng biểu, tài liệu tham khảo, ... |
| Trình bày PowerPoint & demo | 0,5 | |
| Quản lý dự án trên môi trường điện toán đám mây | 0,5 | Phân chia và các thành viên cùng làm trên 1 resource trên môi trường cloud. |

### Ghi chú

- Đối với các chủ đề làm offline thì chứng minh thông qua GitHub - việc cộng tác các thành viên trong nhóm, có thể sử dụng các tool teamwork để thể hiện.
- Thông tin chi phí, quotas.
