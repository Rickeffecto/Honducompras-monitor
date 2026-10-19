#!/usr/bin/env python3
"""Submit the official HonduCompras SICC search form and inspect its results."""
from urllib.parse import urljoin
import sys

import requests
from bs4 import BeautifulSoup

URL = "http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HonduComprasMonitor/0.5)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = (10, 30)


def build_form_payload(form):
    payload = []
    for field in form.find_all(["input", "select", "textarea", "button"]):
        name = field.get("name")
        if not name or field.has_attr("disabled"):
            continue
        tag = field.name
        kind = (field.get("type") or "").lower()
        if tag == "input":
            if kind in {"submit", "button", "image", "reset", "file"}:
                continue
            if kind in {"checkbox", "radio"} and not field.has_attr("checked"):
                continue
            payload.append((name, field.get("value", "")))
        elif tag == "textarea":
            payload.append((name, field.text or ""))
        elif tag == "select":
            options = field.find_all("option")
            selected = [o for o in options if o.has_attr("selected")]
            chosen = selected or (options[:1] if options else [])
            for option in chosen:
                if not option.has_attr("disabled"):
                    payload.append((name, option.get("value", option.get_text(strip=True))))
    return payload


def main():
    with requests.Session() as session:
        session.headers.update(HEADERS)
        response = session.get(URL, timeout=TIMEOUT)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", "").lower():
            raise RuntimeError("La URL no devolvió HTML.")
        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form")
        if not form:
            raise RuntimeError("La página respondió, pero no contiene formulario de búsqueda.")
        payload = build_form_payload(form)
        submit = form.find("input", attrs={"type": "submit"})
        if submit and submit.get("name"):
            payload.append((submit["name"], submit.get("value", "")))
        action = urljoin(response.url, form.get("action") or response.url)
        print("GET_STATUS:", response.status_code)
        print("FORM_ACTION:", action)
        print("FORM_FIELDS_SENT:", len(payload))
        print("SUBMITTING_SEARCH: yes")

        result = session.post(action, data=payload, headers={"Referer": response.url}, timeout=TIMEOUT)
        print("POST_STATUS:", result.status_code)
        print("POST_FINAL_URL:", result.url)
        print("POST_CONTENT_TYPE:", result.headers.get("content-type", ""))
        result.raise_for_status()
        page = BeautifulSoup(result.text, "html.parser")
        title = page.title.get_text(" ", strip=True) if page.title else "(sin título)"
        print("RESULT_PAGE_TITLE:", title)
        text = " ".join(page.stripped_strings)
        print("PAGE_TEXT_PREVIEW:", text[:1800])

        tables = page.find_all("table")
        candidates = []
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            parsed = []
            for row in rows[:8]:
                cells = row.find_all(["th", "td"])
                values = [" ".join(cell.stripped_strings) for cell in cells]
                if any(values):
                    parsed.append(" | ".join(values))
            if parsed:
                candidates.append((len(rows) - 1, parsed, table))
        candidates.sort(key=lambda item: item[0], reverse=True)
        print("TABLE_COUNT:", len(tables))
        print("CANDIDATE_RESULT_TABLES:", len(candidates))
        result_count = 0
        for index, (row_count, parsed, table) in enumerate(candidates[:5], 1):
            print(f"TABLE_{index}_DATA_ROWS:", row_count)
            for line in parsed[:6]:
                print(f"TABLE_{index}_ROW:", line[:500])
            for link in table.find_all("a", href=True)[:5]:
                print(f"TABLE_{index}_LINK:", link.get_text(" ", strip=True)[:120], urljoin(result.url, link["href"]))
            result_count = max(result_count, row_count)
        print("RESULT_ROWS_ESTIMATE:", result_count)
        if result_count == 0:
            print("NOTE: No table with data rows detected; inspect page text and WebForms postback behavior.")
        # A successful HTTP response is not proof that result extraction is production-ready.
        print("SEARCH_SUBMISSION_COMPLETED: yes")
        print("TELEGRAM_NOTIFICATIONS: not configured by this diagnostic")
        if result.status_code >= 400:
            return 1


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MONITOR_ERROR:", type(exc).__name__, str(exc)[:1000])
        sys.exit(1)
