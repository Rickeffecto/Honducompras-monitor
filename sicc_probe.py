#!/usr/bin/env python3
"""Read-only connectivity test for the user-supplied official HonduCompras SICC URL."""
import requests
from bs4 import BeautifulSoup

URLS = [
    "http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx",
    "https://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HonduComprasMonitor/0.4; read-only diagnostic)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = (10, 20)


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    successes = 0
    for url in URLS:
        print("\n" + "=" * 88)
        print("TEST URL:", url)
        try:
            response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            print("HTTP STATUS:", response.status_code)
            print("FINAL URL:", response.url)
            print("REDIRECTS:", len(response.history))
            for item in response.history:
                print("  ", item.status_code, item.url, "->", item.headers.get("Location", ""))
            print("CONTENT TYPE:", response.headers.get("content-type", "(unknown)"))
            print("BODY BYTES:", len(response.content))
            if response.status_code < 400 and "html" in response.headers.get("content-type", "").lower():
                soup = BeautifulSoup(response.text, "html.parser")
                print("PAGE TITLE:", soup.title.get_text(" ", strip=True) if soup.title else "(no title)")
                forms = soup.find_all("form")
                print("FORM COUNT:", len(forms))
                for index, form in enumerate(forms[:10], start=1):
                    print(f"FORM {index}: method={form.get('method', 'get')} action={form.get('action', '')}")
                    for field in form.find_all(["input", "select", "textarea", "button"])[:30]:
                        print("  FIELD:", field.name, "name=", field.get("name", ""), "type=", field.get("type", ""), "id=", field.get("id", ""), "text=", field.get_text(" ", strip=True)[:80])
                print("BODY PREVIEW:", soup.get_text(" ", strip=True)[:1200])
                successes += 1
            else:
                print("BODY PREVIEW:", response.text[:700].replace("\n", " "))
        except requests.RequestException as exc:
            print("REQUEST ERROR:", type(exc).__name__, str(exc)[:600])

    print("\n" + "=" * 88)
    print(f"RESULT: {successes}/{len(URLS)} URL variants returned usable HTML.")
    print("Read-only diagnostic only: it does not submit search forms or send Telegram notifications.")


if __name__ == "__main__":
    main()
