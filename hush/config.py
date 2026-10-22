import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

HUSH_DB_PATH = Path(os.getenv("HUSH_DB_PATH", DEFAULT_DATA_DIR / "hush.db"))
MACOS_NOTIFICATION_DB_PATH = Path(
    os.getenv(
        "MACOS_NOTIFICATION_DB_PATH",
        Path.home() / "Library/Group Containers/group.com.apple.usernoted/db2/db",
    )
)

# Ollama & Model Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
HUSH_MODEL = os.getenv("HUSH_MODEL", "gemma:2b")
HUSH_DEV_MODEL = os.getenv("HUSH_DEV_MODEL", "gemma:2b")

# Epoch difference between Cocoa (2001-01-01) and Unix (1970-01-01)
COCOA_EPOCH_OFFSET_SECONDS = 978307200

# Scoring Thresholds
T_HIGH = float(os.getenv("HUSH_T_HIGH", "0.55"))    # >= 0.55 triggers immediate interrupt
T_BRIEF = float(os.getenv("HUSH_T_BRIEF", "0.15"))  # >= 0.15 qualifies for brief slot; < 0.15 is rejected

# Category Consequence Lookup Table (Deterministic weights)
CONSEQUENCE_WEIGHTS = {
    "health": 1.00,
    "money": 0.90,
    "person": 0.85,
    "deadline": 0.80,
    "work": 0.50,
    "promo": 0.05,
}

# Brief Quotas (Total 4 slots)
BRIEF_QUOTAS = {
    "mail": 2,
    "wa": 1,
    "sms": 1,
}
BRIEF_MAX_LINES = 4

# Polling cadence
COLLECTOR_POLL_INTERVAL_SECONDS = 60
INTERRUPT_ACK_WAIT_MINUTES = 10
