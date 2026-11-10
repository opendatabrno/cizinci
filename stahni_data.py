"""Stažení měsíčních přehledů MV ČR „Cizinci s povoleným pobytem“ (od 12/2012).

Ukládá do složky data/ (nebo do složky z proměnné prostředí CIZINCI_DATA) pod jednotnými názvy:
    YYYY-MM Cizinci s povoleným pobytem.xlsx   (do 2016 .xls)
Už stažené soubory přeskočí (pokud nepoužiješ --prepsat).

Zdroje:
  - archiv MV (2012–2025): prosincové soubory pevně podle seznamu níže, ostatní měsíce
    se hledají na stránkách jednotlivých roků v archivu
  - aktuální stránky MV „Cizinci s povoleným pobytem – přehled za rok YYYY“: odkazy se hledají
    automaticky podle data „31-12-YYYY“, takže v dalších letech stačí skript jen spustit
  - starší přehledy jen za celou ČR: 2007–2010 měsíční PDF Služby cizinecké policie
    (archiv.policie.gov.cz), 1/2011–11/2012 xls MV – pro tabulku cizinci_staty.csv a měsíční řadu
  - číselník okresů a krajů (volby.gov.cz) -> ciselniky/cnumnuts.csv

Roční datové sady se skládají z prosincových souborů (stav k 31. 12.), měsíční řada ze všech.

Použití:
    python stahni_data.py             # soubory, které chybí
    python stahni_data.py --prepsat   # stáhnout znovu
"""
import argparse
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CIZINCI_DATA") or ROOT / "data")
CISELNIKY = ROOT / "ciselniky"

ARCHIV = "https://archiv.mv.gov.cz/soubor/"
ARCHIV_STRANKA = "https://archiv.mv.gov.cz/clanek/cizinci-s-povolenym-pobytem.aspx"
ROZCESTNIK = "https://mv.gov.cz/cizinci-s-povolenym-pobytem-2"
PREHLED_ROKU = "https://mv.gov.cz/cizinci-s-povolenym-pobytem---prehled-za-rok-{rok}"
VOLBY = "https://volby.gov.cz/opendata/ps2025/csv_od/"
PRVNI_ROK = 2012

# rok -> soubor v archivu MV se stavem k 31. 12. (2024: revidovaná verze)
ARCHIV_PROSINEC = {
    2012: "pobyty-2012-stav-k-31-12-2012-xls",
    2013: "stav-k-31-12-2013-xls",
    2014: "12-2014-tab-internet-stav-k-31-12-2014-xls",
    2015: "12-2015-tab-internet-stav-k-31-12-2015-xls",
    2016: "12-2016-tab-internet-stav-k-31-12-2016-xls",
    2017: "12-2017-tab-internet-stav-k-31-12-2017-xlsx",
    2018: "12-2018-tab-internet-stav-k-31-12-2018-xlsx",
    2019: "12-2019-tab-internet-stav-k-31-12-2019-xlsx",
    2020: "12-2020-tab-internet-stav-k-31-12-2020-xlsx",
    2021: "12-2021-tab-internet-stav-k-31-12-2021-xlsx",
    2022: "12-2022-tab-internet-stav-k-31-12-2022-xlsx",
    2023: "12-2023-tab-internet-stav-k-31-12-2023-xlsx",
    2024: "12-2024-tab-internet-stav-k-31-12-2024-revize-xlsx",
    2025: "12-2025-tab-internet-stav-k-31-12-2025-xlsx",
}
# starší přehledy jen za celou ČR (bez okresů) pro tabulku cizinci_staty.csv a měsíční řadu před 12/2012:
# 2007–2010 PDF Služby cizinecké policie (10/2010 je jen .doc, vynechává se), 1/2011–11/2012 xls MV
POLICIE = "https://archiv.policie.gov.cz/soubor/"
POLICIE_MESICE = {
    "2007-01": "tudu-01-2007-pdf",
    "2007-02": "tudu-02-2007-pdf",
    "2007-03": "tudu-03-2007-pdf",
    "2007-04": "tudu-04-2007-pdf",
    "2007-05": "tudu-05-2007-pdf",
    "2007-06": "tudu-06-2007-pdf",
    "2007-07": "tudu-07-2007-pdf",
    "2007-08": "tudu-08-2007-pdf",
    "2007-09": "tudu-09-2007-pdf",
    "2007-10": "tudu-10-2007-pdf",
    "2007-11": "tudu-11-2007-pdf",
    "2007-12": "tudu-12-2007-pdf",
    "2008-01": "tudu-01-2008-pdf",
    "2008-02": "tudu-02-2008-pdf",
    "2008-03": "tudu-03-2008-pdf",
    "2008-04": "tudu-04-2008-pdf",
    "2008-05": "tudu-05-2008-pdf",
    "2008-06": "cizinci-s-povolenym-pobytem-300608-pdf",
    "2008-07": "tudu-07-2008-pdf",
    "2008-08": "tudu-082008-pdf",
    "2008-09": "sluzba-cizinecke-policie-galerie-soubory-tudu-09-2008-pdf",
    "2008-10": "sluzba-cizinecke-policie-galerie-soubory-tudu-10-2008-pdf",
    "2008-11": "tudu-11-2008-pdf",
    "2008-12": "tudu-12-08-pdf",
    "2009-01": "tudu-01-2009-pdf",
    "2009-02": "tudu-02-2009-pdf",
    "2009-03": "tudu-03-2009-pdf",
    "2009-04": "tudu-04-2009-pdf",
    "2009-05": "tudu-05-2009-pdf",
    "2009-06": "tudu-06-2009-pdf",
    "2009-07": "tudu-07-2009-pdf",
    "2009-08": "tudu-08-2009-pdf",
    "2009-09": "tudu-9-2009-pdf",
    "2009-10": "tudu-10-2009-pdf",
    "2009-11": "tudu-11-2009-pdf",
    "2009-12": "www-tudu-12-2009-nove-pdf",
    "2010-01": "01-2010-tdu-pdf",
    "2010-02": "tdu-02-2010-pdf",
    "2010-03": "tdu-03-2010-pdf",
    "2010-04": "tdu-04-2010-pdf",
    "2010-05": "tdu-05-2010-pdf",
    "2010-06": "sluzba-cizinecke-policie-galerie-soubory-tudu-06-2010-pdf",
    "2010-07": "sluzba-cizinecke-policie-galerie-soubory-tdu-07-2010-pdf",
    "2010-08": "sluzba-cizinecke-policie-galerie-soubory-tudu-8-2010-1-pdf",
    "2010-09": "tudu-9-2010-pdf",
    "2010-11": "tdu-11-2010-pdf",
    "2010-12": "tdu-12-2010-pdf",
}
ARCHIV_STARSI = {
    "2011-01": "2011-01-pobyty-xls",
    "2011-02": "2011-02-pobyty-xls",
    "2011-03": "03-2011-pobyty-xls",
    "2011-04": "04-2011-pobyty-xls",
    "2011-05": "2011-05-celkovy-prehled-xls",
    "2011-06": "internet-tdu-stavk06-2011-xls",
    "2011-07": "internet-tdu-stavk07-2011-xls",
    "2011-08": "internet-tdu-stavk08-2011-3-xls",
    "2011-09": "internet-tdu-stavk09-2011-xls",
    "2011-10": "internet-tdu-stavk10-2011-xls",
    "2011-11": "internet-tdu-stavk11-2011-xls",
    "2011-12": "internet-tdu-stavk-12-2011-xls",
    "2012-01": "internet-tdu-stavk01-2012-xls",
    "2012-02": "internet-tdu-stavk02-2012-xls",
    "2012-03": "internet-tdu-stavk03-2012-xls",
    "2012-04": "internet-tdu-stavk04-2012-xls",
    "2012-05": "internet-tdu-stavk05-2012-xls",
    "2012-06": "internet-tdu-stavk-06-2012-xls",
    "2012-07": "internet-tdu-stavk-07-2012-1-xls",
    "2012-08": "internet-tdu-stavk-08-2012-xls",
    "2012-09": "internet-tdu-stavk-09-2012-xls",
    "2012-10": "internet-tdu-stavk-10-2012-xls",
    "2012-11": "stav-k-30-11-2012-xls",
}
# stránky roků v archivu MV: parametr q = base64("chnum=N"), rok 2025 má N = 2, každý starší o 1 víc
ARCHIV_CHNUM_2025 = 2

HLAVICKY = {"User-Agent": "Mozilla/5.0 (data-cizinci)"}


def cil(rok, mesic, pripona):
    return DATA / f"{rok}-{mesic:02d} Cizinci s povoleným pobytem.{pripona}"


def get(url, pokusu=4):
    """GET s opakováním – archiv MV občas místo stránky vrátí chybovou stránku."""
    for i in range(pokusu):
        try:
            r = requests.get(url, headers=HLAVICKY, timeout=90)
            if r.ok and "Požadovaná stránka není dostupná" not in r.text[:5000]:
                return r
        except requests.RequestException:
            if i == pokusu - 1:
                raise
        time.sleep(3 * (i + 1))
    r.raise_for_status()
    raise RuntimeError(f"{url} vrací chybovou stránku")


def uloz(url, rok, mesic, prepsat):
    existujici = [p for p in DATA.glob(f"{rok}-{mesic:02d} Cizinci s povoleným pobytem.*")]
    if existujici and not prepsat:
        return False
    r = get(url)
    if r.content[:2] not in (b"PK", b"\xd0\xcf"):
        raise RuntimeError(f"{url} nevrátil Excel soubor")
    pripona = "xlsx" if r.content[:2] == b"PK" else "xls"
    for p in existujici:
        p.unlink()
    cil(rok, mesic, pripona).write_bytes(r.content)
    print(f"  staženo {rok}-{mesic:02d} ({len(r.content) // 1024} kB)")
    return True


def odkazy_aktualni():
    """Soubory na aktuálních stránkách MV: {(rok, měsíc): url}."""
    try:
        html = get(ROZCESTNIK).text
    except (requests.RequestException, RuntimeError):
        html = ""
    roky = {int(r) for r in re.findall(r"prehled-za-rok-(\d{4})", html)}
    roky |= set(range(2026, date.today().year + 1))
    nalezeno = {}
    for rok in sorted(roky):
        try:
            html = get(PREHLED_ROKU.format(rok=rok), pokusu=2).text
        except (requests.RequestException, RuntimeError):
            continue
        for url in set(re.findall(r'https://mv\.gov\.cz/documents/[^"\\?]+', html)):
            m = re.search(r"stavk(\d{2})-(\d{2})-(\d{4})$", url.lower())
            if m:
                nalezeno[(int(m.group(3)), int(m.group(2)))] = url + "?disposition=attachment"
    return nalezeno


def odkazy_archiv_mesicne():
    """Všechny měsíční soubory v archivu MV: {(rok, měsíc): url}."""
    import base64
    nalezeno = {}
    for rok in range(PRVNI_ROK, 2026):
        q = base64.b64encode(f"chnum={ARCHIV_CHNUM_2025 + 2025 - rok}".encode()).decode()
        html = get(f"{ARCHIV_STRANKA}?q={requests.utils.quote(q)}").text
        for slug, nazev in re.findall(r'href="soubor/([^"]+)\.aspx" title="([^"]+)"', html):
            # stav ke dni v názvu: 31-12-2025, 31.12.2016, 30.9.2018, 31_01_2023, 31-12_2017 …
            datumy = re.findall(r"(\d{1,2})[._-](\d{1,2})[._-](\d{4})", nazev)
            if datumy and int(datumy[-1][2]) == rok and nazev.lower().endswith((".xls", ".xlsx")):
                nalezeno[(rok, int(datumy[-1][1]))] = f"{ARCHIV}{slug}.aspx"
    return nalezeno


def stahni_ciselniky():
    CISELNIKY.mkdir(exist_ok=True)
    r = requests.get(VOLBY + "cnumnuts.csv", headers=HLAVICKY, timeout=60)
    r.raise_for_status()
    # volby.gov.cz posílá CRLF; v repozitáři je LF, jinak by každý běh na Linuxu hlásil změnu
    (CISELNIKY / "cnumnuts.csv").write_bytes(r.content.replace(b"\r\n", b"\n"))
    print("  číselník okresů a krajů aktualizován")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepsat", action="store_true", help="stáhnout i soubory, které už existují")
    args = ap.parse_args(argv)
    DATA.mkdir(parents=True, exist_ok=True)
    print(f"Složka dat: {DATA}")

    print("Archiv MV:")
    for rok, slug in ARCHIV_PROSINEC.items():
        uloz(f"{ARCHIV}{slug}.aspx", rok, 12, args.prepsat)
    try:
        mesice = odkazy_archiv_mesicne()
    except (requests.RequestException, RuntimeError) as e:
        print(f"  pozor: stránky roků v archivu MV nejsou dostupné ({e}), měsíční soubory se přeskočí")
        mesice = {}
    for (rok, mesic), url in sorted(mesice.items()):
        if (rok == PRVNI_ROK and mesic < 12) or (mesic == 12 and rok in ARCHIV_PROSINEC):
            continue  # do 11/2012 jiný formát souborů; prosinec je pevně výše
        uloz(url, rok, mesic, args.prepsat)

    print("Starší přehledy 2007 – 11/2012:")
    for mesic, slug in POLICIE_MESICE.items():
        cesta = DATA / f"{mesic} Cizinci s povoleným pobytem (policie).pdf"
        if cesta.exists() and not args.prepsat:
            continue
        r = get(f"{POLICIE}{slug}.aspx")
        if not r.content.startswith(b"%PDF"):
            raise RuntimeError(f"{POLICIE}{slug}.aspx nevrátil PDF")
        cesta.write_bytes(r.content)
        print(f"  staženo {cesta.name} ({len(r.content) // 1024} kB)")
    for mesic, slug in ARCHIV_STARSI.items():
        uloz(f"{ARCHIV}{slug}.aspx", int(mesic[:4]), int(mesic[5:]), args.prepsat)

    print("Aktuální stránky MV:")
    for (rok, mesic), url in sorted(odkazy_aktualni().items()):
        uloz(url, rok, mesic, args.prepsat)

    print("Číselníky:")
    stahni_ciselniky()


if __name__ == "__main__":
    sys.exit(main())
