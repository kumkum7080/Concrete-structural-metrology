import json
import os
from datetime import datetime

USER_DB_PATH = "users_db.json"
HISTORY_DB_PATH = "history_db.json"

def init_dbs():
    if not os.path.exists(USER_DB_PATH):
        with open(USER_DB_PATH, "w") as f:
            json.dump({"admin": "password123"}, f)

    if not os.path.exists(HISTORY_DB_PATH):
        with open(HISTORY_DB_PATH, "w") as f:
            json.dump([], f)

def verify_user(username, password):
    init_dbs()
    with open(USER_DB_PATH, "r") as f:
        users = json.load(f)
    return users.get(username) == password

def register_user(username, password):
    init_dbs()
    with open(USER_DB_PATH, "r") as f:
        users = json.load(f)
    if username in users:
        return False
    users[username] = password
    with open(USER_DB_PATH, "w") as f:
        json.dump(users, f, indent=4)
    return True

def log_inspection(username, filename, width, length, severity):
    init_dbs()
    with open(HISTORY_DB_PATH, "r") as f:
        history = json.load(f)

    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": username,
        "filename": filename,
        "max_width_mm": float(width),
        "tracked_length_mm": float(length),
        "severity": severity
    }
    history.append(record)
    with open(HISTORY_DB_PATH, "w") as f:
        json.dump(history, f, indent=4)

def get_user_history(username):
    init_dbs()
    with open(HISTORY_DB_PATH, "r") as f:
        history = json.load(f)
    return [r for r in history if r["username"] == username]
