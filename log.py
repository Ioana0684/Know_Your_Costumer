import os
import json
from datetime import datetime
from unittest.mock import DEFAULT

DEFAULT_LOG_PATH = os.path.join("log", "kyc_log.jsonl")  #locatia implicita a logului

def write_log(event: str, details: dict, log_path: str = DEFAULT_LOG_PATH) -> None:
    """Scrie o linie JSON cu ts event details, in fisierul log"""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)           #creaza folderul daca lipseste
    line = {                                                        #construim obiectul log
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),     #timestamp ISO in UTC
        "event": event,                                             #numele evenimentului
        "details" : details                                         #detalii non-PII, campuri prezente, status
    }
    with open(log_path, "a", encoding= "utf-8") as f:               #deschidem in append
        f.write(json.dumps(line, ensure_ascii=False) + "\n")        #scriem linia + newline

def tail_log(n: int = 10, log_path: str = DEFAULT_LOG_PATH) -> list[str]:
    """Returneaza ultimile linii din log daca acestea exista"""
    if not os.path.exists(log_path):                                #daca logul nu exista
        return[]
    with open(log_path, "r", encoding= "utf-8") as f:               #deschide pentru citire
        lines = f.readlines()                                       #citeste toate liniile
    return lines[-n:]                                               #ultimile n linii


