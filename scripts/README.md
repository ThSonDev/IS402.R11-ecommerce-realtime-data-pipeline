# scripts/ – Script tiện ích

Phụ trách: Minh, Sơn

Script chạy một lần hoặc chạy tay.

| Script | Làm gì |
|---|---|
| `prepare_data.py` | Tải dữ liệu REES46, chuyển sang Parquet (xem `data/README.md`) |
| `fill_env.py` | Điền thông tin kết nối Event Hubs vào `.env` bằng quyền `az login` của chính bạn |

## fill_env.py

Cần: Azure CLI, đã `az login` bằng mail trường, hạ tầng đã `apply`.

```powershell
.venv\Scripts\python scripts\fill_env.py           # producer gửi lên Event Hubs
.venv\Scripts\python scripts\fill_env.py --local   # quay về Kafka local
# Linux: .venv/bin/python scripts/fill_env.py
```

- Chỉ sửa các dòng cần thiết trong `.env`, giữ nguyên phần còn lại. Chưa có `.env` thì tạo từ `.env.example`.
- Lấy connection string của policy `producer-send` (chỉ có quyền gửi). Không gửi secret qua chat.
- Sau mỗi lần `destroy` / `apply` Event Hubs, key đổi: chạy lại script.
