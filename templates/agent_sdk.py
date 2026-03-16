import urllib.request
import json
import os

STATE_FILE = "sandbox_state.json"
MASTER_AGENT = os.getenv("MASTER_AGENT", "agent_core")
IN_DOCKER = os.path.exists('/.dockerenv')
HOST = MASTER_AGENT if IN_DOCKER else "127.0.0.1"
LISTENER_URL = f"http://{HOST}:18790/alert"

def send_alert(message: str):
    try:
        data = json.dumps({"message": message}).encode('utf-8')
        req = urllib.request.Request(LISTENER_URL, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=3) as response:  # noqa: F841
            pass 
    except Exception as e:
        print(f"Failed to send alert to Agent '{MASTER_AGENT}': {e}")

def save_state(key: str, value):
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            pass
    state[key] = value
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def load_state(key: str, default=None):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return state.get(key, default)
        except Exception:
            pass
    return default 