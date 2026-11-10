"""Sestaví web pro GitHub Pages do složky _site/.

Úvodní stránka s popisem a odkazy ke stažení, přehled kontrol a samotná CSV (+ xlsx).
Spouští ho workflow .github/workflows/pages.yml, lokálně:
    python web.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import kontrola

ROOT = Path(__file__).resolve().parent
VYSTUP = ROOT / "vystup"
WEB = ROOT / "_site"
REPO = "https://github.com/opendatabrno/cizinci"
ZDROJ = "https://mv.gov.cz/cizinci-s-povolenym-pobytem-2"

SADY = [
    ("cizinci_okresy.csv", "Cizinci v okresech",
     "Všech 77 okresů ČR, jeden řádek = okres × rok (stav k 31. 12.). Klíč rok + kod_okresu."),
    ("cizinci_okresy_staty.csv", "Cizinci v okresech podle státní příslušnosti",
     "Jeden řádek = okres × státní příslušnost × rok (stav k 31. 12.). Klíč rok + kod_okresu + kod_statu."),
    ("cizinci_staty.csv", "Cizinci v ČR podle státní příslušnosti od 2007",
     "Celá ČR, jeden řádek = stát × rok (stav k 31. 12.), 2007–2011 ze starších přehledů bez okresů. "
     "Klíč rok + kod_statu."),
    ("cizinci_mesicne.csv", "Cizinci v ČR po měsících",
     "Celá ČR podle státní příslušnosti, jeden řádek = měsíc × stát, od 1/2007 (chybí 10/2010). "
     "Klíč stav_k + kod_statu."),
]

SLOUPCE = [
    ("rok, stav_k", "rok a den, ke kterému MV počty uvádí (roční sady 31. 12., měsíční řada poslední den měsíce)"),
    ("mesic", "jen měsíční řada: měsíc 1–12"),
    ("kod_okresu, okres, kod_kraje, kraj", "okresní sady: kód LAU 1 / NUTS 3 a název; okres „nezjištěno“ = MV "
                                           "nepřiřadilo adresu, kódy jsou prázdné"),
    ("kod_statu, statni_prislusnost", "kód ISO 3166-1 alpha-3 (zvláštní: XKX Kosovo, XXA bez státní příslušnosti, "
                                      "XXB/XXC uprchlíci, XXX neuvedeno) a sjednocený název"),
    ("skupina", "„EU, EHP, Švýcarsko“, nebo „třetí země“ – podle členství ke dni stav_k"),
    ("cizinci_celkem, cizinci_muzi, cizinci_zeny", "cizinci s povoleným pobytem (muži a ženy do 5/2008 nejsou)"),
    ("cizinci_trvaly_pobyt, cizinci_prechodny_pobyt", "podle druhu pobytu (součet = cizinci_celkem); přechodný "
                                                      "pobyt zahrnuje i dočasnou ochranu"),
    ("cizinci_docasna_ochrana", "z toho dočasná ochrana: do 2021 nula, 2022–2023 prázdné (MV ji neuvádí zvlášť), "
                                "od 2024 počet (v měsíční řadě prázdné 3/2022–9/2024)"),
    ("cizinci_eu_ehp_ch, cizinci_treti_zeme", "jen tabulka okresů: rozdělení cizinci_celkem podle skupiny států"),
]


def velikost(cesta):
    mb = cesta.stat().st_size / 1_000_000
    return f"{mb:.1f} MB".replace(".", ",")


def main():
    if not (VYSTUP / "kontrola_souctu.csv").exists():
        print("Chybí výstupy ve vystup/ – nejdřív spusť zpracuj_data.py")
        return 1
    kontrola.main()
    shutil.rmtree(WEB, ignore_errors=True)
    WEB.mkdir()
    shutil.copy(VYSTUP / "kontrola.html", WEB / "kontrola.html")

    karty = []
    for soubor, nazev, popis in SADY:
        cesta = VYSTUP / soubor
        shutil.copy(cesta, WEB / soubor)
        # xlsx se v repozitáři neukládá, vzniká tady z CSV
        d = pd.read_csv(cesta, dtype={"cizinci_docasna_ochrana": "Int64", "kod_okresu": str})
        xlsx = WEB / cesta.with_suffix(".xlsx").name
        d.to_excel(xlsx, index=False, freeze_panes=(1, 0))
        obdobi = (f"{d.stav_k.min()[:7]} až {d.stav_k.max()[:7]}" if "mesic" in d
                  else f"{d.rok.min()}–{d.rok.max()}")
        karty.append(
            f'<div class="karta ok"><h3>{nazev}</h3><p>{popis}</p>'
            f'<p class="meta">{obdobi} · {kontrola.cislo(len(d))} řádků</p>'
            f'<div class="tlacitka"><a class="tlacitko" href="{soubor}" download>CSV · {velikost(cesta)}</a>'
            f'<a class="tlacitko druhe" href="{xlsx.name}" download>Excel · {velikost(xlsx)}</a></div></div>')
    sloupce = "".join(f"<tr><td><code>{s}</code></td><td>{p}</td></tr>" for s, p in SLOUPCE)
    stav = (VYSTUP / "kontrola_stav.txt").read_text(encoding="utf-8").strip()

    stranka = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cizinci v ČR</title><style>{kontrola.CSS}
.meta{{font-size:13px;margin-top:8px!important}}
.tlacitko{{display:inline-block;margin-top:12px;padding:7px 14px;border-radius:8px;background:var(--accent);
color:var(--panel);text-decoration:none;font-weight:600;font-size:14px}}
.tlacitko:hover{{filter:brightness(1.1)}}
.tlacitka{{display:flex;gap:8px;flex-wrap:wrap}}
.tlacitko.druhe{{background:transparent;color:var(--accent);box-shadow:inset 0 0 0 1.5px var(--accent)}}
a{{color:var(--info)}}
.odkazy{{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;align-items:center}}
</style></head><body><main>
<header><h1>Cizinci s povoleným pobytem v ČR</h1>
<p>Počty cizinců s povoleným pobytem po okresech a podle státní příslušnosti ze souborů Ministerstva vnitra ČR,
roční sady vždy k 31. prosinci, měsíční řada za celou ČR.</p>
<div class="odkazy">{kontrola.odznak(stav)}<a href="kontrola.html">Přehled kontrol</a>
<a href="{REPO}">Zdrojový kód a dokumentace</a></div></header>

<h2>Datové sady</h2>
<section class="karty">{''.join(karty)}</section>

<h2>Sloupce</h2>
<p class="popis">Kategorie se sčítají: muži + ženy = celkem, trvalý + přechodný pobyt = celkem,
EU/EHP/Švýcarsko + třetí země = celkem. Dočasná ochrana je část přechodného pobytu, nepřičítat.
Řádky tří sad nesčítej dohromady: jde o různé pohledy na stejné osoby.</p>
<div class="tab-obal"><table><thead><tr><th>Sloupec</th><th>Význam</th></tr></thead>
<tbody>{sloupce}</tbody></table></div>

<h2>Na co si dát pozor</h2>
<div class="panel"><ul>
<li>Jde o evidenci MV (cizinci s platným povolením k trvalému nebo přechodnému pobytu, u občanů EU
přechodný pobyt přihlášený u MV), ne o počet obyvatel ČSÚ.</li>
<li>Od 3/2022 jsou mezi cizinci lidé s dočasnou ochranou (skok o ~450 tis.). Do září 2024 je MV vede
v přechodném pobytu bez rozlišení, od října 2024 zvlášť (sloupec <code>cizinci_docasna_ochrana</code>).</li>
<li>Od 2021 patří občané Spojeného království mezi třetí země (brexit).</li>
<li>Roky 2007–2010 jsou z PDF Služby cizinecké policie, kde se místo přechodného pobytu píše „dlouhodobý“
pobyt; jde o stejnou kategorii. Říjen 2010 v měsíční řadě chybí (policie ho zveřejnila jen jako .doc).</li>
<li>V prosinci 2011 přibylo 30 tis. přechodných pobytů občanů třetích zemí (+7 %). Skok je už v souboru MV.</li>
<li>Okres je podle aktuální adresy pobytu. U cizinců bez určené adresy je okres „nezjištěno“.</li>
</ul></div>

<footer>Zdroj: <a href="{ZDROJ}">MV ČR – Cizinci s povoleným pobytem</a> ·
aktualizováno {datetime.now():%d. %m. %Y}</footer>
</main></body></html>"""
    (WEB / "index.html").write_text(stranka, encoding="utf-8")
    print(f"Web: {WEB}")


if __name__ == "__main__":
    sys.exit(main())
