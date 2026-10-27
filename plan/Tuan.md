# Kế hoạch – Tuấn

Vai trò: biến dữ liệu thành thứ người quản lý nhìn vào là hiểu. Phụ trách toàn bộ Power BI: dashboard real-time, báo cáo lịch sử nhiều trang, phân quyền theo sàn / miền, chia sẻ, xem trên điện thoại. Cuối kỳ làm slide thuyết trình.

Đây là phần nặng điểm nhất của rubric (mục 4, 3 điểm), đồng thời là con đường vào hướng Data Analyst / BI.

Thư mục phụ trách: `dashboards/powerbi/`.

## Kết quả cuối cùng cần có

| Hạng mục | Kết quả mong đợi |
|---|---|
| Dashboard real-time | Số liệu tự cập nhật trong vài giây khi producer đang chạy |
| Báo cáo lịch sử | Ít nhất 4 trang, có nút điều hướng qua lại |
| Phân quyền (RLS) | Quản lý sàn chỉ thấy sàn của mình, quản lý miền chỉ thấy miền của mình |
| Chia sẻ | Báo cáo publish thành Power BI App, chia sẻ cho người xem |
| Mobile | Xem được trên app Power BI điện thoại, bố cục riêng cho màn hình dọc |
| Slide | Slide thuyết trình theo mẫu KLTN UIT |

## Tuần 1 (27/10 – 02/11): chuẩn bị và phác thảo

Phụ thuộc: Minh. File dữ liệu mẫu nhỏ (khoảng 1 ngày).

Việc cần làm:

- Bật Power BI Pro trial trên tài khoản `MSSV@ms.uit.edu.vn` (app.fabric.microsoft.com → avatar → Start trial). Ghi lại ngày hết hạn.
- Cài Power BI Desktop. Bật lưu dạng PBIP (Power BI Project) trong Options để file lưu được vào Git.
- Liệt kê các chỉ số cần hiển thị và cách tính, ví dụ:
  - GMV: tổng tiền các đơn.
  - Số đơn.
  - Tỷ lệ chuyển đổi: số phiên có mua / số phiên có xem.
  - Giá trị trung bình mỗi đơn.
  - Tỷ lệ đơn bị gắn cờ gian lận.
- Phác thảo 4 trang báo cáo trên giấy hoặc Figma:
  - Tổng quan.
  - Chi tiết sản phẩm và danh mục.
  - Theo sàn × tỉnh (bản đồ).
  - Gian lận và sự cố.
- Dựng thử trên file dữ liệu mẫu Minh gửi (khoảng 1 ngày).

Kết quả mong đợi:

- Bản phác thảo 4 trang được cả nhóm góp ý.
- Danh sách chỉ số có công thức rõ ràng.

## Tuần 2 (03/11 – 09/11): dashboard real-time

Phụ thuộc: Thắng. Output real-time `kpi_1min` đẩy vào Power BI.

Việc cần làm:

- Tạo workspace trên Power BI Service, mời cả nhóm.
- Khi Stream Analytics bắt đầu đẩy dữ liệu (output `kpi_1min`), dữ liệu tự xuất hiện trong workspace dưới dạng streaming dataset.
- Tạo dashboard real-time với các tile: số đơn mỗi phút, GMV, so sánh theo sàn.
- Làm bố cục mobile cho dashboard này.

Kết quả mong đợi:

- Producer chạy là các tile tự nhảy số, không cần bấm refresh.

## Tuần 3 (10/11 – 16/11): báo cáo lịch sử

Phụ thuộc: Thắng. Star schema trên Synapse.

Việc cần làm:

- Kết nối Power BI Desktop vào star schema trên Synapse serverless (Thắng cung cấp).
- Dựng mô hình dữ liệu: quan hệ giữa bảng fact và các bảng dimension, các measure DAX cho chỉ số ở tuần 1.
- Làm đủ 4 trang theo bản phác thảo:
  - Bộ lọc: thời gian, sàn, danh mục.
  - Nút điều hướng giữa các trang.
  - Bản đồ tỉnh.
- Publish lên workspace.

Kết quả mong đợi:

- Bản nháp 4 trang chạy trên dữ liệu thật, cả nhóm mở xem được.

## Tuần 4 (17/11 – 23/11): phân quyền, chia sẻ, mobile

Phụ thuộc: Sơn. Hỗ trợ quyền trong tenant khi chia sẻ báo cáo.

Việc cần làm:

- Tạo RLS:
  - 3 vai trò quản lý sàn (Tiki, Shopee, Lazada).
  - 3 vai trò quản lý miền (Bắc, Trung, Nam).
- Kiểm tra bằng chức năng "View as role" trong Desktop.
- Publish thành Power BI App, gán người xem vào từng vai trò.
- Bố cục mobile cho từng trang báo cáo. Thử trên app Power BI điện thoại.
- Chụp màn hình: cùng một trang nhìn bằng hai tài khoản khác nhau ra hai bộ số khác nhau.

Kết quả mong đợi:

- Mở App bằng tài khoản được gán vai trò "Shopee", chỉ thấy số của Shopee.

## Tuần 5 (24/11 – 01/12): slide và demo

Phụ thuộc: cả nhóm. Slide phần của từng người.

Giao cho: Sơn. Phần báo cáo của mình.

- Làm slide theo mẫu KLTN UIT. Mọi người gửi slide phần mình, Tuấn ghép và thống nhất giao diện.
- Viết phần báo cáo được giao (dưới đây).
- Trong demo, trình bày phần dashboard, RLS và mobile.

## Gợi ý và lưu ý

- RLS chỉ có tác dụng với người có quyền **Viewer**. Admin, Member, Contributor của workspace luôn thấy toàn bộ dữ liệu. Khi test, người xem phải chỉ có quyền Viewer hoặc xem qua App.
- Với Pro trial, cả người chia sẻ lẫn người xem đều cần license Pro. Nhắc cả nhóm bật trial trong tuần 1.
- Trial của Sơn hết hạn khoảng 18/12/2026, nên mọi thứ phải xong trước đó.
- Lưu file dạng PBIP, không commit `.pbix`. PBIP là thư mục file text nên xem được thay đổi trong PR.
- Không đưa toàn bộ 67.5 triệu dòng vào Desktop khi đang dựng thử. Dùng dữ liệu mẫu, khi xong mới trỏ sang Synapse.
- Tính năng real-time streaming của Power BI đã được Microsoft thông báo ngừng (mốc 31/10/2027). Vẫn dùng được cho đồ án, nhưng ghi chú điều này trong báo cáo.

## Phần báo cáo phải viết

- 4: hiện thực trực quan dữ liệu: các trang báo cáo, navigation, cập nhật real-time, RLS và chia sẻ, mobile. Kèm ảnh chụp màn hình.
- Slide toàn bộ bài thuyết trình (phần ghép và giao diện).
