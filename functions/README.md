# functions/ – Azure Functions

Phụ trách: Minh (code), Sơn (hạ tầng Function App trong Terraform)

`fraud_alert/`: nhận event gian lận từ Stream Analytics và gửi cảnh báo Discord/Telegram. Mỗi function app có `function_app.py`, `host.json`, `requirements.txt` riêng, vì được deploy độc lập.
