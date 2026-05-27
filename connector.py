import json
import os
import platform
import socket
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


DEFAULTS = {
    "RAT_C2_BASE_URL": "http://localhost:8000",
    "RAT_AGENT_API_TOKEN": "lab-token-change-me",
    "RAT_AGENT_LABEL": "connector-client",
    "RAT_POLL_SECONDS": "3",
}

C2_BASE_URL = os.getenv("RAT_C2_BASE_URL", DEFAULTS["RAT_C2_BASE_URL"]).rstrip("/")
AGENT_TOKEN = os.getenv("RAT_AGENT_API_TOKEN", DEFAULTS["RAT_AGENT_API_TOKEN"])
AGENT_ID = os.getenv("RAT_AGENT_ID", str(uuid.uuid4()))
AGENT_LABEL = os.getenv("RAT_AGENT_LABEL", DEFAULTS["RAT_AGENT_LABEL"])
POLL_SECONDS = int(os.getenv("RAT_POLL_SECONDS", DEFAULTS["RAT_POLL_SECONDS"]))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def envelope(msg_type: str) -> dict:
    return {
        "message_id": str(uuid.uuid4()),
        "agent_id": AGENT_ID,
        "timestamp_utc": now_iso(),
        "type": msg_type,
        "payload": {},
    }


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{C2_BASE_URL}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-agent-token": AGENT_TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def register() -> None:
    payload = {
        "envelope": envelope("register"),
        "payload": {
            "agent_label": AGENT_LABEL,
            "os_name": platform.platform(),
        },
    }
    post_json("/api/agent/register", payload)


def execute_safe(command: dict | None) -> dict:
    if not command:
        return {}
    command_type = command.get("command_type", "")
    args = command.get("args", {})

    # Intentional safety boundary:
    # this connector demonstrates C2 transport flow only.
    if command_type == "health_check":
        return {
            "status": "success",
            "stdout": "connector healthy",
            "stderr": "",
            "error_message": "",
            "artifact_name": "",
        }
    if command_type == "sysinfo":
        return {
            "status": "success",
            "stdout": json.dumps(
                {
                    "hostname": socket.gethostname(),
                    "os": platform.platform(),
                    "python": platform.python_version(),
                    "agent_id": AGENT_ID,
                }
            ),
            "stderr": "",
            "error_message": "",
            "artifact_name": "",
        }
    if command_type == "echo":
        return {
            "status": "success",
            "stdout": str(args.get("message", "")),
            "stderr": "",
            "error_message": "",
            "artifact_name": "",
        }
    return {
        "status": "error",
        "stdout": "",
        "stderr": "",
        "error_message": f"unsupported command_type={command_type}",
        "artifact_name": "",
    }


def post_response(command_id: str, result: dict) -> None:
    payload = {
        "envelope": envelope("response"),
        "payload": {
            "command_id": command_id,
            "status": result.get("status", "error"),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "error_message": result.get("error_message", ""),
            "artifact_name": result.get("artifact_name", ""),
        },
    }
    post_json("/api/agent/response", payload)


def run() -> None:
    while True:
        try:
            register()
            break
        except Exception as exc:  # noqa: BLE001
            print(f"register failed: {exc}")
            time.sleep(POLL_SECONDS)

    while True:
        try:
            poll_payload = {"envelope": envelope("poll")}
            response = post_json("/api/agent/poll", poll_payload)
            command = response.get("command")
            if command:
                result = execute_safe(command)
                post_response(command.get("command_id", ""), result)
        except urllib.error.HTTPError as exc:
            print(f"http error: {exc.code}")
        except Exception as exc:  # noqa: BLE001
            print(f"loop error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
