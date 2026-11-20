"""Azure Function `fraud_alert`: Stream Analytics posts batches of `alerts` rows here (HTTP).

ASA's Azure Functions output sends a JSON array per batch and treats any non-2xx answer as
a failure to retry. Telegram errors are logged but still answered with 200: a retry would
resend the alerts that did go out, and dbo.alerts keeps every alert anyway.
"""
import json
import logging
import os

import alerts
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
log = logging.getLogger(__name__)
deduper = alerts.Deduper()   # module level: shared by calls on the same instance


@app.route(route="fraud_alert", methods=["POST"])
def fraud_alert(req: func.HttpRequest) -> func.HttpResponse:
    try:
        batch = req.get_json()
    except ValueError:
        return func.HttpResponse("body must be JSON", status_code=400)
    if isinstance(batch, dict):
        batch = [batch]
    if not batch:   # ASA sends an empty batch when testing the connection
        return func.HttpResponse("no alerts", status_code=200)

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID app settings are missing")
        return func.HttpResponse("telegram not configured", status_code=200)

    try:
        sent = alerts.handle(batch, deduper, token, chat)
    except Exception:   # Telegram down or rate limited: log, do not make ASA retry
        log.exception("sending %d alert(s) to Telegram failed", len(batch))
        sent = 0
    body = json.dumps({"received": len(batch), "messages_sent": sent})
    return func.HttpResponse(body, status_code=200, mimetype="application/json")
