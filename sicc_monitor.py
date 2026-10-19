#!/usr/bin/env python3
"""Submit the official HonduCompras SICC search form and inspect its results."""
from urllib.parse import urljoin
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

import requests
from bs4 import BeautifulSoup

URL = "http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HonduComprasMonitor/0.5)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = (10, 120)
STATE_FILE = Path("seen_processes.json")
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


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


def load_seen():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except (OSError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def telegram_send(token, chat_id, message):
    response = requests.post(
        TELEGRAM_API.format(token=token),
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=(10, 20),
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("Telegram no confirmó el envío.")


def extract_processes(page, base_url):
    """Conservatively select tables that look like procurement results."""
    processes = []
    keywords = ("proceso", "licitacion", "licitación", "institucion", "institución",
                "objeto", "modalidad", "contratacion", "contratación", "publicacion", "publicación")
    for table in page.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        first_cells = rows[0].find_all(["th", "td"])
        header = " ".join(cell.get_text(" ", strip=True).lower() for cell in first_cells)
        if not any(word in header for word in keywords):
            continue
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            parts = [" ".join(cell.stripped_strings) for cell in cells]
            text = " | ".join(part for part in parts if part)
            if not text:
                continue
            links = [urljoin(base_url, a["href"]) for a in row.find_all("a", href=True)]
            if not links and len(parts) < 2:
                continue
            identity = hashlib.sha256((text + "|" + "|".join(links)).encode("utf-8")).hexdigest()
            processes.append({"id": identity, "text": text[:1200], "url": links[0] if links else ""})
    return processes


def main():
    seen = load_seen()
    save_seen(seen)  # Ensure the workflow cache has a file even while SICC is unavailable.
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
        # The blank/default form searches too much history and can stall the legacy server.
        # Narrow the first validation to the most recent 14 days.
        start_date = (date.today() - timedelta(days=14)).strftime("%d/%m/%Y")
        end_date = date.today().strftime("%d/%m/%Y")
        date_fields = {
            "ctl00_cphCuerpo_wpParametros_wdInicio_input": start_date,
            "ctl00_cphCuerpo_wpParametros_wdFin_input": end_date,
        }
        payload = [(name, date_fields.get(name, value)) for name, value in payload]
        action = urljoin(response.url, form.get("action") or response.url)
        print("GET_STATUS:", response.status_code, flush=True)
        print("FORM_ACTION:", action, flush=True)
        print("FORM_FIELDS_SENT:", len(payload), flush=True)
        print("SEARCH_DATE_RANGE:", start_date, "to", end_date, flush=True)
        print("SUBMITTING_SEARCH: yes", flush=True)

        result = session.post(action, data=payload, headers={"Referer": response.url}, timeout=TIMEOUT)
        print("POST_STATUS:", result.status_code, flush=True)
        print("POST_FINAL_URL:", result.url, flush=True)
        print("POST_CONTENT_TYPE:", result.headers.get("content-type", ""), flush=True)
        result.raise_for_status()
        page = BeautifulSoup(result.text, "html.parser")
        title = page.title.get_text(" ", strip=True) if page.title else "(sin título)"
        print("RESULT_PAGE_TITLE:", title)
        text = " ".join(page.stripped_strings)
        print("PAGE_TEXT_PREVIEW:", text[:1800])

        tables = page.find_all("table")
        processes = extract_processes(page, result.url)
        print("TABLE_COUNT:", len(tables))
        print("PROCUREMENT_ROWS_DETECTED:", len(processes))
        for process in processes[:5]:
            print("PROCESS_PREVIEW:", process["text"][:500])
            if process["url"]:
                print("PROCESS_URL:", process["url"])

        new_processes = [item for item in processes if item["id"] not in seen]
        print("NEW_PROCESSES:", len(new_processes))
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if new_processes and token and chat_id:
            sent_ids = []
            for item in new_processes:
                message = "📢 Nueva oportunidad en HonduCompras\n\n" + item["text"]
                if item["url"]:
                    message += "\n\nVer proceso: " + item["url"]
                telegram_send(token, chat_id, message[:4000])
                sent_ids.append(item["id"])
            seen.update(sent_ids)
            print("TELEGRAM_SENT:", len(sent_ids))
        elif new_processes:
            print("TELEGRAM_NOT_CONFIGURED: add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in repository Actions secrets.")
        else:
            print("No se detectaron procesos nuevos según las tablas reconocidas.")
        save_seen(seen)
        print("SEARCH_SUBMISSION_COMPLETED: yes")
        if result.status_code >= 400:
            return 1


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MONITOR_ERROR:", type(exc).__name__, str(exc)[:1000])
        sys.exit(1)
