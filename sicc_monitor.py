#!/usr/bin/env python3
"""Monitor the official HonduCompras SICC search without alerting on form controls."""
from urllib.parse import urljoin
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import requests
from bs4 import BeautifulSoup

URL = "http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HonduComprasMonitor/0.6)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = (10, 120)
STATE_FILE = Path("seen_processes.json")
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
NO_RESULTS_PHRASES = (
    "no se encontraron procesos", "no existen registros", "sin resultados",
    "no hay registros", "no se encontraron resultados",
)
HEADER_KEYWORDS = {
    "process": ("proceso", "licitacion", "licitación", "numero de proceso",
                "número de proceso", "codigo de proceso", "código de proceso"),
    "context": ("objeto", "institucion", "institución", "modalidad",
                "contratacion", "contratación", "publicacion", "publicación",
                "estado", "fecha"),
}


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


def normalized(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def find_results_tables(page):
    """Only accept tables that resemble actual process results, not layout/forms."""
    candidates = []
    for table in page.find_all("table"):
        if table.find(["input", "select", "textarea"]):
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"], recursive=False)
        if len(header_cells) < 3:
            continue
        header = normalized(" ".join(cell.get_text(" ", strip=True) for cell in header_cells))
        has_process = any(word in header for word in HEADER_KEYWORDS["process"])
        has_context = any(word in header for word in HEADER_KEYWORDS["context"])
        if has_process and has_context:
            candidates.append(table)
    return candidates


def extract_processes(page, base_url, results_tables):
    processes = []
    for table in results_tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            parts = [" ".join(cell.stripped_strings) for cell in cells]
            text = " | ".join(part for part in parts if part)
            if not text or len(parts) < 3:
                continue
            links = [
                urljoin(base_url, anchor["href"])
                for anchor in row.find_all("a", href=True)
                if anchor["href"].strip() and not anchor["href"].strip().lower().startswith(("javascript:", "#"))
            ]
            # Process rows must have a real detail link; controls/navigation are not opportunities.
            if not links:
                continue
            identity = hashlib.sha256((text + "|" + "|".join(links)).encode("utf-8")).hexdigest()
            processes.append({"id": identity, "text": text[:1200], "url": links[0]})
    return processes


def main():
    seen = load_seen()
    save_seen(seen)  # Preserve cache state even if the portal is currently unavailable.
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    print("TELEGRAM_CONFIGURED:", "yes" if token and chat_id else "no", flush=True)

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
        page_text = normalized(page.get_text(" ", strip=True))
        print("RESULT_PAGE_TITLE:", title, flush=True)

        results_tables = find_results_tables(page)
        print("RESULT_TABLES_VALIDATED:", len(results_tables), flush=True)
        if not results_tables:
            if any(phrase in page_text for phrase in NO_RESULTS_PHRASES):
                print("SEARCH_RESULTS_VALIDATED: yes (explicit no-results response)", flush=True)
                processes = []
            else:
                preview = page.get_text(" ", strip=True)[:600]
                print("PAGE_TEXT_PREVIEW:", preview, flush=True)
                raise RuntimeError(
                    "HonduCompras no devolvió una tabla verificable de procesos; "
                    "se bloquean alertas para evitar falsos positivos. La búsqueda puede seguir en 'Cargando...'."
                )
        else:
            processes = extract_processes(page, result.url, results_tables)
            if not processes and not any(phrase in page_text for phrase in NO_RESULTS_PHRASES):
                raise RuntimeError(
                    "Se encontró una posible tabla, pero ninguna fila tenía enlace de detalle verificable; "
                    "se bloquean alertas por seguridad."
                )
            print("SEARCH_RESULTS_VALIDATED: yes", flush=True)

        print("PROCUREMENT_ROWS_DETECTED:", len(processes), flush=True)
        new_processes = [item for item in processes if item["id"] not in seen]
        print("NEW_PROCESSES:", len(new_processes), flush=True)

        if new_processes and token and chat_id:
            sent_ids = []
            for item in new_processes:
                message = "📢 Nueva oportunidad en HonduCompras\n\n" + item["text"]
                if item["url"]:
                    message += "\n\nVer proceso: " + item["url"]
                telegram_send(token, chat_id, message[:4000])
                sent_ids.append(item["id"])
            seen.update(sent_ids)
            print("TELEGRAM_SENT:", len(sent_ids), flush=True)
        elif new_processes:
            print(
                "TELEGRAM_NOT_CONFIGURED: agrega TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID "
                "en Settings > Secrets and variables > Actions.",
                flush=True,
            )
        else:
            print("No se detectaron procesos nuevos verificables.", flush=True)

        save_seen(seen)
        print("SEARCH_SUBMISSION_COMPLETED: yes", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MONITOR_ERROR:", type(exc).__name__, str(exc)[:1000], flush=True)
        sys.exit(1)
