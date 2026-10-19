#!/usr/bin/env python3
"""Read-only diagnostic for public HonduCompras/SEFIN pages."""
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

TARGETS = [
    "https://www.honducompras.gob.hn/",
    "https://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx",
    "https://guancasco.sefin.gob.hn/EDCA_WEBAPI/swagger/ui/index",
    "https://guancasco.sefin.gob.hn/EDCA_WEBAPI/ocids_json/",
    "https://guancasco.sefin.gob.hn/EDCA_WEBAPI/ocids_cvs/",
]
HEADERS = {"User-Agent": "HonduComprasMonitor/0.1 (read-only diagnostics)"}

def inspect(url):
    print("\n" + "=" * 88 + "\nURL:", url)
    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
        print("HTTP:", response.status_code)
        print("Final URL:", response.url)
        print("Content-Type:", response.headers.get("content-type", "(unknown)"))
        response.raise_for_status()
    except requests.RequestException as exc:
        print("REQUEST ERROR:", exc)
        return
    if "html" not in response.headers.get("content-type", "").lower():
        print("Response preview:", response.text[:500].replace("\n", " "))
        return
    soup = BeautifulSoup(response.text, "html.parser")
    print("Title:", soup.title.get_text(" ", strip=True) if soup.title else "(none)")
    print("Relevant links:")
    found = 0
    keywords = ("proceso", "licit", "compra", "contrat", "búsqueda", "busqueda", "ocid", "json", "csv", "swagger", "api")
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        href = urljoin(response.url, a["href"])
        if any(k in (label + " " + href).lower() for k in keywords):
            print(f"  - {label[:100] or '(sin texto)'} -> {href}")
            found += 1
            if found >= 60:
                print("  ... límite de 60 enlaces")
                break
    if not found:
        print("  (sin enlaces relevantes encontrados en HTML)")
    forms = soup.find_all("form")
    print("Forms:", len(forms))
    for i, form in enumerate(forms[:10], 1):
        print(f"  Form {i}: method={form.get('method', 'get')} action={urljoin(response.url, form.get('action', ''))}")
        for field in form.find_all(["input", "select", "textarea", "button"])[:30]:
            print(f"    field: tag={field.name} type={field.get('type','')} name={field.get('name','')} id={field.get('id','')}")

if __name__ == "__main__":
    for target in TARGETS:
        inspect(target)
