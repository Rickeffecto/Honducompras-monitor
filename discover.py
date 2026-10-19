#!/usr/bin/env python3
"""Read-only discovery of HonduCompras' official advanced process search.

TLS certificate verification remains enabled. This script deliberately does not
use SEFIN's EDCA API and does not submit search forms or send notifications.
"""
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OFFICIAL_HOSTS = {"honducompras.gob.hn", "www.honducompras.gob.hn", "sicc.honducompras.gob.hn", "h1.honducompras.gob.hn"}
START_URLS = [
    "https://honducompras.gob.hn/",
    "https://www.honducompras.gob.hn/",
]
SEARCH_TERMS = ("búsqueda avanzada", "busqueda avanzada", "búsqueda de procesos",
                "busqueda de procesos", "proceso", "licitación", "licitacion",
                "compra", "contratación", "contratacion")
HEADERS = {
    "User-Agent": "HonduComprasMonitor/0.2 (read-only public procurement discovery)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = (10, 20)
MAX_LINKS = 80


def make_session():
    session = requests.Session()
    retry = Retry(
        total=2, connect=2, read=1, status=1, backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def is_official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in OFFICIAL_HOSTS


def relevant(label, url):
    value = f"{label} {url}".lower()
    return any(term in value for term in SEARCH_TERMS)


def inspect_page(session, url):
    print("\n" + "=" * 88 + "\nURL:", url)
    if not is_official_url(url):
        print("SKIPPED: URL is not HTTPS on an official HonduCompras host")
        return []
    try:
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        print("HTTP:", response.status_code)
        print("Final URL:", response.url)
        print("Content-Type:", response.headers.get("content-type", "(unknown)"))
        response.raise_for_status()
    except requests.RequestException as exc:
        print("REQUEST ERROR:", type(exc).__name__, str(exc)[:600])
        print("TLS verification is enabled; no insecure certificate bypass was attempted.")
        return []

    if not is_official_url(response.url):
        print("SKIPPED: redirect left the official HonduCompras HTTPS hosts")
        return []

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type:
        print("Not HTML; response preview:", response.text[:300].replace("\n", " "))
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    print("Title:", soup.title.get_text(" ", strip=True) if soup.title else "(none)")
    discovered = []
    print("Relevant official links:")
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        target = urljoin(response.url, anchor["href"].strip())
        if relevant(label, target) and is_official_url(target):
            discovered.append((label, target))
            print(f"  - {label[:100] or '(sin texto)'} -> {target}")
            if len(discovered) >= MAX_LINKS:
                print(f"  ... límite de {MAX_LINKS} enlaces")
                break
    if not discovered:
        print("  (no se encontraron enlaces relevantes en el HTML recibido)")

    forms = soup.find_all("form")
    print("Forms:", len(forms))
    for i, form in enumerate(forms[:10], 1):
        action = urljoin(response.url, form.get("action", ""))
        print(f"  Form {i}: method={form.get('method', 'get')} action={action}")
        for field in form.find_all(["input", "select", "textarea", "button"])[:30]:
            print(
                f"    field: tag={field.name} type={field.get('type', '')} "
                f"name={field.get('name', '')} id={field.get('id', '')}"
            )
    return discovered


def main():
    session = make_session()
    all_links = []
    for url in START_URLS:
        all_links.extend(inspect_page(session, url))

    # Follow only official links explicitly identified as advanced/process search.
    candidates = []
    for label, url in all_links:
        if any(term in f"{label} {url}".lower() for term in
               ("búsqueda avanzada", "busqueda avanzada", "búsqueda de procesos",
                "busqueda de procesos", "busquedahistorico", "procesos/")):
            if url not in candidates:
                candidates.append(url)

    if not candidates:
        print("\nRESULT: No se could not verify a working advanced-search link from the official homepage.")
        print("This run is diagnostic only; it has not confirmed access to current process listings.")
        return

    print("\nAdvanced-search candidates found:", len(candidates))
    for url in candidates[:10]:
        inspect_page(session, url)

    print("\nNOTE: This diagnostic does not yet claim new-process detection or send Telegram alerts.")


if __name__ == "__main__":
    main()
