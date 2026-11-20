# functions/ – Azure Functions

Phụ trách: Minh (code), Sơn (hạ tầng Function App trong Terraform)

`fraud_alert/`: nhận cảnh báo từ Stream Analytics và gửi vào group Telegram. Mỗi function app có `function_app.py`, `host.json`, `requirements.txt` riêng, vì được deploy độc lập.

## fraud_alert

| File | Chức năng |
|---|---|
| `function_app.py` | HTTP trigger `POST /api/fraud_alert` (cần function key). Output Azure Functions của ASA gửi mỗi lô `alerts` thành một mảng JSON |
| `alerts.py` | Phần không phụ thuộc Azure: gộp, chặn lặp, định dạng, gửi Telegram. Test trong `tests/test_fraud_alert.py` |

Xử lý mỗi lô:

1. **Gộp trong lô:** cùng luật + cùng đối tượng (`rule_name`, `entity_type`, `entity_id`) chỉ giữ một dòng, lấy `metric_value` lớn nhất và ghi số lần lặp.
2. **Chặn lặp giữa các lô:** cùng luật + đối tượng đã gửi trong 10 phút thì bỏ. Bộ nhớ nằm trong instance của Function, nên khởi động lạnh sẽ quên; lịch sử đầy đủ vẫn ở `dbo.alerts`.
3. **Một tin cho cả lô** (tách nếu dài quá 4,096 ký tự), để không vượt giới hạn khoảng 20 tin / phút của bot trong group. Ví dụ:

   ```
   🚨 2 cảnh báo lúc 20:10 11/11 (giờ VN)
   • Bot gom hàng - user 900000000: orders_per_minute = 20 (ngưỡng 5), 2 lần
   • Số đơn bất thường - system: orders_per_minute = 57 (ngưỡng 90)
   ```

Lỗi gửi Telegram chỉ ghi log, Function vẫn trả 200: trả lỗi thì ASA gửi lại cả lô (lặp tin đã gửi), còn cảnh báo vẫn được lưu ở `dbo.alerts`. Lô rỗng (ASA thử kết nối) trả 200.

Thử ở máy (không cần Azure Functions Core Tools):

```powershell
.venv\Scripts\python functions\fraud_alert\alerts.py          # in tin mẫu
.venv\Scripts\python functions\fraud_alert\alerts.py --send   # gửi tin mẫu vào group, cần TELEGRAM_* trong .env
# Linux: .venv/bin/python functions/fraud_alert/alerts.py [--send]
```

Thử trên Azure (gửi một lô giả giống ASA; group sẽ nhận tin):

```powershell
az functionapp function keys list -g rg-megasale-dev -n func-megasale-dev --function-name fraud_alert --query default -o tsv
curl -s -X POST "https://func-megasale-dev.azurewebsites.net/api/fraud_alert?code=<key>" -H "Content-Type: application/json" -d '[{"alert_time":"2026-11-11T13:01:00Z","rule_name":"bot","entity_type":"user","entity_id":"900000000","metric_name":"orders_per_minute","metric_value":20,"threshold":5,"event_id":null}]'
```

Kết quả mong đợi `{"received": 1, "messages_sent": 1}`. `messages_sent` bằng 0 nghĩa là Function không gửi được Telegram (thường do token trong app settings đã cũ).

Tạo bot: nhắn `@BotFather` lệnh `/newbot`, thêm bot vào group của nhóm, gửi một tin bất kỳ trong group, rồi mở `https://api.telegram.org/bot<token>/getUpdates` để lấy `chat.id` (group có id âm). Ghi `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` vào `.env`, không commit.

## Deploy

Function App `func-megasale-dev` (Python 3.12, Linux Consumption) do Terraform tạo, không tính tiền khi rảnh. Deploy code bằng zip, Azure tự cài `requirements.txt` (cần `az login`, role Contributor trên RG):

```powershell
Compress-Archive -Path functions\fraud_alert\* -DestinationPath $env:TEMP\fraud_alert.zip -Force
az functionapp deployment source config-zip -g rg-megasale-dev -n func-megasale-dev --src $env:TEMP\fraud_alert.zip --build-remote true
# Linux: (cd functions/fraud_alert && zip -r /tmp/fraud_alert.zip .) && az functionapp deployment source config-zip -g rg-megasale-dev -n func-megasale-dev --src /tmp/fraud_alert.zip --build-remote true
```

Token bot và chat ID đọc từ app settings `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (cách đặt xem `infra/README.md`). Chạy local thì lấy từ `.env`.
