import requests
import json

URL = "http://localhost:8000/api/orchestrate"

def call(exception_id: str):
    payload = {"exception_id": exception_id, "case": {"exception_id": exception_id, "exception_type": "Technical Glitch", "amount": 12.34}}
    r = requests.post(URL, json=payload, timeout=10)
    print(f"Status: {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)


if __name__ == "__main__":
    for eid in ["EXC-100", "EXC-101", "EXC-102", "EXC-103"]:
        print("---", eid)
        call(eid)
