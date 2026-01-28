"""
Simple JSONL logger for the KYC pipeline.

Each log entry is written as a single JSON object per line and contains:
- UTC timestamp
- event name
- non-PII details
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List

DEFAULT_LOG_PATH = os.path.join("logs", "kyc_log.jsonl")


def write_log(event: str, details: Dict[str, Any], log_path: str = DEFAULT_LOG_PATH) -> None:
    """
    Append a single JSONL log entry.

    Parameters:
        event: Short event name (e.g. 'KYC_VERDICT')
        details: Dictionary with non-PII metadata
        log_path: Path to the JSONL log file
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    line = {
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "details": details,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def tail_log(n: int = 10, log_path: str = DEFAULT_LOG_PATH) -> List[str]:
    """
    Return the last n raw JSONL lines from the log file.
    Useful for quick debugging or demos.
    """
    if not os.path.exists(log_path):
        return []

    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    return lines[-n:]


