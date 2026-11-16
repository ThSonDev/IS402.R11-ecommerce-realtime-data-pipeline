# functions/ – Azure Functions

Phụ trách: Minh (code), Sơn (hạ tầng Function App trong Terraform)

`fraud_alert/`: nhận cảnh báo từ Stream Analytics và gửi vào group Telegram. Mỗi function app có `function_app.py`, `host.json`, `requirements.txt` riêng, vì được deploy độc lập.

## Deploy

Function App `func-megasale-dev` (Python 3.12, Linux Consumption) do Terraform tạo, không tính tiền khi rảnh. Deploy code bằng zip, Azure tự cài `requirements.txt` (cần `az login`, role Contributor trên RG):

```powershell
Compress-Archive -Path functions\fraud_alert\* -DestinationPath $env:TEMP\fraud_alert.zip -Force
az functionapp deployment source config-zip -g rg-megasale-dev -n func-megasale-dev --src $env:TEMP\fraud_alert.zip --build-remote true
# Linux: (cd functions/fraud_alert && zip -r /tmp/fraud_alert.zip .) && az functionapp deployment source config-zip -g rg-megasale-dev -n func-megasale-dev --src /tmp/fraud_alert.zip --build-remote true
```

Token bot và chat ID đọc từ app settings `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (cách đặt xem `infra/README.md`). Chạy local thì lấy từ `.env`.
