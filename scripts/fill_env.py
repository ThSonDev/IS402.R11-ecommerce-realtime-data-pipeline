"""Fill .env with Azure connection settings, fetched with your own `az login`.

Secrets never go through chat: every member (Contributor on the RG) runs this themselves.
    python scripts/fill_env.py           # point the producer at Event Hubs
    python scripts/fill_env.py --local   # back to local Kafka (docker compose)
Names match infra/*.tf.
"""
import shutil
import subprocess
import sys
from pathlib import Path

RG = "rg-megasale-dev"
NAMESPACE = "evhns-megasale-dev"
HUB = "events"
POLICY = "producer-send"  # send-only

ENV = Path(".env")
EXAMPLE = Path(".env.example")


def az(*args: str) -> str:
    exe = shutil.which("az")  # az.cmd on Windows, so plain "az" fails in subprocess
    if exe is None:
        sys.exit("Azure CLI not found. Install it, then run: az login")
    result = subprocess.run([exe, *args, "-o", "tsv"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"az failed (logged in? resources deployed?):\n{result.stderr.strip()}")
    return result.stdout.strip()


def set_keys(text: str, values: dict) -> str:
    """Replace KEY=... lines in place, append keys that are missing."""
    lines = text.splitlines()
    for key, value in values.items():
        line = f"{key}={value}"
        idx = next((i for i, x in enumerate(lines) if x.startswith(f"{key}=")), None)
        if idx is None:
            lines.append(line)
        else:
            lines[idx] = line
    return "\n".join(lines) + "\n"


def main():
    if "--local" in sys.argv:
        values = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT",
            "EVENTHUBS_CONNECTION_STRING": "''",
        }
    else:
        conn = az("eventhubs", "eventhub", "authorization-rule", "keys", "list",
                  "-g", RG, "--namespace-name", NAMESPACE, "--eventhub-name", HUB, "-n", POLICY,
                  "--query", "primaryConnectionString")
        values = {
            "ARM_SUBSCRIPTION_ID": az("account", "show", "--query", "id"),
            "KAFKA_BOOTSTRAP_SERVERS": f"{NAMESPACE}.servicebus.windows.net:9093",
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            # single quotes: the value contains ; and =, see .env.example
            "EVENTHUBS_CONNECTION_STRING": f"'{conn}'",
        }

    text = ENV.read_text(encoding="utf-8") if ENV.exists() else EXAMPLE.read_text(encoding="utf-8")
    ENV.write_text(set_keys(text, values), encoding="utf-8")
    print(f".env updated: {', '.join(values)}")


if __name__ == "__main__":
    main()
