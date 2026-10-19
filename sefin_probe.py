#!/usr/bin/env python3
"""Read-only connectivity probe for SEFIN's official EDCA API.

This is a diagnostic only. It does not create procurement notices, infer new
opportunities, or send Telegram notifications. SEFIN's dataset is focused on
budget/expenditure and payment information; it is not a substitute for ONCAE's
live tender publication system.
"""
import json
import requests

BASE = "https://guancasco.sefin.gob.hn/EDCA_WEBAPI"
CHECKS = [
    ("Swagger UI", f"{BASE}/swagger/ui/index"),
    ("Swagger specification", f"{BASE}/swagger/docs/v1"),
    ("OCIDs JSON endpoint", f"{BASE}/api/ocids_json"),
    ("OCIDs CSV endpoint", f"{BASE}/api/ocids_cvs"),
]
TIMEOUT = (10, 25)
HEADERS = {
    "User-Agent": "HonduComprasMonitor/0.4 (read-only SEFIN EDCA API diagnostic)",
    "Accept": "application/json,text/html,text/plain,*/*",
}


def summarize(response):
    content_type = response.headers.get("content-type", "(unknown)")
    print("HTTP:", response.status_code)
    print("Final URL:", response.url)
    print("Content-Type:", content_type)
    body = response.text or ""
    if "json" in content_type.lower():
        try:
            data = response.json()
            if isinstance(data, dict):
                print("JSON keys:", ", ".join(str(k) for k in list(data.keys())[:30]))
                print("JSON preview:", json.dumps(data, ensure_ascii=False)[:1200])
            elif isinstance(data, list):
                print("JSON list items:", len(data))
                print("JSON preview:", json.dumps(data[:2], ensure_ascii=False)[:1200])
            else:
                print("JSON preview:", json.dumps(data, ensure_ascii=False)[:1200])
        except ValueError:
            print("Body preview:", body[:800].replace("\n", " "))
    else:
        print("Body preview:", body[:800].replace("\n", " "))


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    results = []
    for label, url in CHECKS:
        print("\n" + "=" * 84)
        print(label + ":", url)
        try:
            response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            summarize(response)
            results.append((label, response.status_code < 400))
        except requests.RequestException as exc:
            print("REQUEST ERROR:", type(exc).__name__, str(exc)[:500])
            results.append((label, False))

    print("\n" + "=" * 84)
    print("RESULT: SEFIN EDCA connectivity probe finished.")
    for label, ok in results:
        print(f"{'OK' if ok else 'FAILED'}: {label}")
    print("Diagnostic only: no new-process detection, deduplication, or Telegram messages.")
    print("TLS certificate verification remains enabled for SEFIN.")


if __name__ == "__main__":
    main()
