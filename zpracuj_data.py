"""Zpracování přehledů MV ČR „Cizinci s povoleným pobytem“ do tabulek po okresech.

Vstup:  data/YYYY-MM Cizinci s povoleným pobytem.xls(x)   (stahni_data.py, měsíční soubory od 12/2012)
        ciselniky/cnumnuts.csv  – okresy a kraje (volby.gov.cz, stahni_data.py)
        ciselniky/staty.csv     – sjednocení názvů států napříč lety + kód ISO 3166
Výstup: vystup/cizinci_okresy_staty.csv a .xlsx – jeden řádek = rok × okres × státní příslušnost
        vystup/cizinci_okresy.csv a .xlsx       – jeden řádek = rok × okres
        vystup/cizinci_mesicne.csv a .xlsx      – jeden řádek = měsíc × státní příslušnost (za celou ČR)
        vystup/cizinci_staty.csv a .xlsx        – jeden řádek = rok × státní příslušnost (za celou ČR, od 2007;
                                                  2007–2011 ze starších přehledů, viz historie.py)
        vystup/kontrola_souctu.csv              – součty každého souboru proti součtům MV
        vystup/staty_nesparovane.csv            – názvy států, které nejsou v ciselniky/staty.csv

Soubor MV je jedna široká tabulka: řádky = státní příslušnost × druh pobytu
(trvalý, přechodný, od 10/2024 i dočasná ochrana), sloupce = okres × (muži, ženy, celkem).

Použití:
    python zpracuj_data.py              # zpracuje stažené soubory
    python zpracuj_data.py --stahnout   # nejdřív stáhne, co chybí (stahni_data.py), pak zpracuje

Zdrojové soubory se hledají ve složce data/ v repozitáři, nebo ve složce
z proměnné prostředí CIZINCI_DATA.
"""
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CIZINCI_DATA") or ROOT / "data")
CISELNIKY = ROOT / "ciselniky"
VYSTUP = ROOT / "vystup"

PRVNI_MESIC = date(2012, 11, 30)  # od 11/2012 mají soubory členění okres × stát; dřív jiný formát (historie.py)
ZACATEK_DO = date(2022, 3, 1)  # dočasná ochrana (válka na Ukrajině)

# EU, EHP a Švýcarsko – volný pohyb osob. Chorvatsko od 1. 7. 2013, Spojené království do 31. 12. 2020
# (do konce přechodného období po brexitu).
EU = {"AUT", "BEL", "BGR", "CYP", "DEU", "DNK", "ESP", "EST", "FIN", "FRA", "GRC", "HUN", "IRL",
      "ITA", "LTU", "LUX", "LVA", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "SWE"}
EHP_CH = {"ISL", "NOR", "LIE", "CHE"}
EU_OD = {"HRV": date(2013, 7, 1)}
EU_DO = {"GBR": date(2020, 12, 31)}

# PŘECHODNÝ / PŘECHODNĚ, TRVALÝ / TRVALE, DOČASNÁ OCHRANA (od 2024)
DRUHY = {"prechodn": "prechodny", "trval": "trvaly", "docasna ochrana": "docasna_ochrana"}


def druh_pobytu(text):
    k = klic(text)
    return next((d for zacatek, d in DRUHY.items() if k.startswith(zacatek)), None)


class StrukturaError(Exception):
    """Soubor MV má strukturu, kterou parser nezná (nový formát, přejmenované sloupce …)."""


def bez_diakritiky(text):
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c))


def norm(text):
    if pd.isna(text):
        return ""
    text = unicodedata.normalize("NFC", str(text)).lower()
    text = re.sub(r"[‐-―]", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def klic(text):
    """Pro hlavičky a popisky: malými písmeny, bez diakritiky."""
    return bez_diakritiky(norm(text))


def klic_statu(text):
    """Názvy států se v letech liší mezerami za tečkou a čárkou – mezery se ignorují."""
    return re.sub(r"\s", "", norm(text))


def nacti_excel(cesta):
    engine = "openpyxl" if cesta.read_bytes()[:2] == b"PK" else "xlrd"
    return pd.ExcelFile(cesta, engine=engine)


def popis_struktury(cesta, radku=12, sloupcu=12):
    """Listy a začátek každého listu – do chybové zprávy (issue), aby šlo parser rychle upravit."""
    try:
        xl = nacti_excel(cesta)
    except Exception as e:  # noqa: BLE001 – i nečitelný soubor chceme popsat
        return f"  soubor nejde otevřít: {e}"
    casti = [f"  soubor: {cesta.name}", f"  listy: {xl.sheet_names}"]
    for list_ in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=list_, header=None, nrows=radku)
        casti.append(f"  --- list '{list_}' ({df.shape[1]} sloupců), prvních {radku} řádků:")
        for i, r in df.iterrows():
            bunky = [str(x).strip() for x in r.iloc[:sloupcu] if pd.notna(x) and str(x).strip()]
            if bunky:
                casti.append(f"    {i}: " + " | ".join(bunky)[:220])
    return "\n".join(casti)


def stav_k_ze_souboru(cesta):
    """Název souboru YYYY-MM … -> poslední den měsíce."""
    rok, mesic = int(cesta.name[:4]), int(cesta.name[5:7])
    return (pd.Timestamp(rok, mesic, 1) + pd.offsets.MonthEnd(0)).date()


# --- čtení jednoho souboru MV ------------------------------------------------

def nacti_prehled(cesta):
    """Přečte soubor MV. Vrací (data, soucty_mv).

    data:  dlouhá tabulka stat_mv, druh, okres_mv, muzi, zeny, celkem, celkem_cr (sloupec CELKOVÝ SOUČET)
    soucty_mv: {druh nebo 'celkem': {okres_mv nebo 'CR': počet}} z řádků CELKEM na konci tabulky
    """
    xl = nacti_excel(cesta)
    if len(xl.sheet_names) != 1:
        raise StrukturaError(f"čekal jsem jeden list, jsou {xl.sheet_names}")
    df = pd.read_excel(xl, sheet_name=0, header=None)

    hlavicka = next((r for r in range(min(15, len(df))) if klic(df.iat[r, 0]) == "stp"), None)
    if hlavicka is None or klic(df.iat[hlavicka, 1]) != "druh pobytu":
        raise StrukturaError("nenašel jsem hlavičku 'STP | DRUH POBYTU' v prvním sloupci")
    okresy = df.iloc[hlavicka]
    pod = df.iloc[hlavicka + 1].map(klic)

    # bloky sloupců okresů: začínají sloupcem „muži“, pak „ženy“ a „(okres) celkem“; některé měsíční
    # soubory mají navíc prázdné nebo pomocné sloupce (např. „x“), ty se přeskočí
    bloky = []  # (okres_mv, sloupec mužů, sloupec žen, sloupec celkem)
    starty = [j for j in range(2, df.shape[1]) if pod.iat[j] == "muzi"]
    for n, j in enumerate(starty):
        konec = starty[n + 1] if n + 1 < len(starty) else df.shape[1]
        jz = next((c for c in range(j + 1, konec) if pod.iat[c] == "zeny"), None)
        jc = next((c for c in range(j + 1, konec) if pod.iat[c] in ("okres celkem", "celkem")), None)
        if jz is None or jc is None:
            raise StrukturaError(f"blok od sloupce {j} ({okresy.iat[j]!r}): {pod.iloc[j:konec].tolist()}")
        jmena = [x for x in okresy.iloc[j:konec] if pd.notna(x) and str(x).strip()]
        if len(jmena) > 1:
            raise StrukturaError(f"blok od sloupce {j} má víc názvů okresů: {jmena}")
        # některé soubory (např. 1/2013) nemají u sloupce nezjištěného okresu název
        bloky.append((str(jmena[0]).strip() if jmena else "NULL*", j, jz, jc))
    if not bloky or klic(bloky[-1][0]) != "celkovy soucet":
        raise StrukturaError("poslední blok sloupců není CELKOVÝ SOUČET")
    *bloky, (_, _, _, j_cr) = bloky
    if len(bloky) < 70:
        raise StrukturaError(f"jen {len(bloky)} okresů v hlavičce")

    telo = df.iloc[hlavicka + 2:]
    stat = telo[0].where(telo[1].notna()).ffill()
    radky, soucty = [], {}
    for i in range(len(telo)):
        popis, druh = telo.iat[i, 0], telo.iat[i, 1]
        if pd.notna(druh):
            d = druh_pobytu(druh)
            if d is None:
                raise StrukturaError(f"neznámý druh pobytu {druh!r} (řádek {hlavicka + 2 + i})")
            radky.append((i, stat.iat[i], d))
        elif pd.notna(popis):
            k = klic(popis)
            if k.startswith("pozn"):
                continue
            k = k.replace("celkem", "").replace("celkovy soucet", "").strip()
            druh_souctu = "celkem" if not k else druh_pobytu(k)
            if druh_souctu is None:
                raise StrukturaError(f"neznámý řádek {popis!r} (řádek {hlavicka + 2 + i})")
            hodnoty = pd.to_numeric(telo.iloc[i, [jc for *_, jc in bloky] + [j_cr]], errors="coerce")
            soucty[druh_souctu] = dict(zip([o for o, *_ in bloky] + ["CR"], hodnoty.fillna(0).astype(int)))
    if "celkem" not in soucty:
        raise StrukturaError("chybí řádek CELKEM / CELKOVÝ SOUČET")

    idx = [i for i, _, _ in radky]
    casti = []
    for okres, jm, jz, jc in bloky:
        hodnoty = telo.iloc[idx, [jm, jz, jc]].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
        casti.append(pd.DataFrame({
            "stat_mv": [s for _, s, _ in radky], "druh": [d for _, _, d in radky], "okres_mv": okres,
            "muzi": hodnoty.iloc[:, 0].values, "zeny": hodnoty.iloc[:, 1].values,
            "celkem": hodnoty.iloc[:, 2].values,
        }))
    data = pd.concat(casti, ignore_index=True)
    cr = pd.to_numeric(telo.iloc[idx, j_cr], errors="coerce").fillna(0).astype(int).values
    data["celkem_cr"] = list(cr) * len(bloky)
    data["stat_mv"] = data.stat_mv.astype(str).str.strip()
    return data, soucty


def nacti(cesta):
    """nacti_prehled + převod jakékoli chyby na StrukturaError s popisem souboru."""
    try:
        return nacti_prehled(cesta)
    except Exception as e:
        raise StrukturaError(f"{cesta.name}: nerozpoznaná struktura ({type(e).__name__}: {e})\n"
                             f"{popis_struktury(cesta)}") from e


# --- číselníky ---------------------------------------------------------------

def nacti_okresy():
    """{normalizovaný název okresu: (kod_okresu, okres, kod_kraje, kraj)} z číselníku NUTS volby.gov.cz."""
    cesta = CISELNIKY / "cnumnuts.csv"
    if not cesta.exists():
        raise SystemExit("Chybí ciselniky/cnumnuts.csv – spusť nejdřív stahni_data.py")
    n = pd.read_csv(cesta, dtype=str, encoding="utf-8")
    kraje = n[n.NUTS.str.len() == 5].set_index("NUTS").NAZEVNUTS
    okresy = n[n.NUTS.str.match(r"CZ0\w{3}$")]
    mapa = {}
    for r in okresy.itertuples():
        mapa[klic(r.NAZEVNUTS)] = (r.NUTS, r.NAZEVNUTS, r.NUTS[:5], kraje[r.NUTS[:5]])
    mapa["hlavni mesto praha"] = mapa["praha"]
    return mapa


def nacti_staty():
    s = pd.read_csv(CISELNIKY / "staty.csv", dtype=str, encoding="utf-8", keep_default_na=False)
    return {klic_statu(r.nazev_mv): (r.kod_statu, r.statni_prislusnost) for r in s.itertuples()}


def skupina(kod, stav_k):
    if kod in EU_OD:
        clen = stav_k >= EU_OD[kod]
    elif kod in EU_DO:
        clen = stav_k <= EU_DO[kod]
    else:
        clen = kod in EU or kod in EHP_CH
    return "EU, EHP, Švýcarsko" if clen else "třetí země"


# --- zpracování --------------------------------------------------------------

CISLA = ["cizinci_celkem", "cizinci_muzi", "cizinci_zeny",
         "cizinci_trvaly_pobyt", "cizinci_prechodny_pobyt", "cizinci_docasna_ochrana"]
POPIS = ["rok", "stav_k", "kod_okresu", "okres", "kod_kraje", "kraj"]


def zpracuj_soubor(cesta, okresy, staty):
    """Jeden soubor MV -> (tabulka okres × stát, řádek kontroly, nespárované státy)."""
    stav_k = stav_k_ze_souboru(cesta)
    data, soucty = nacti(cesta)

    nezname = sorted({o for o in data.okres_mv.unique() if o != "NULL*" and klic(o) not in okresy})
    if nezname:
        raise StrukturaError(f"{cesta.name}: neznámé okresy {nezname}\n{popis_struktury(cesta)}")
    nezjisteno = ("", "nezjištěno", "", "")
    info = data.okres_mv.map(lambda o: nezjisteno if o == "NULL*" else okresy[klic(o)])
    for i, c in enumerate(["kod_okresu", "okres", "kod_kraje", "kraj"]):
        data[c] = info.str[i]

    stat = data.stat_mv.map(lambda s: staty.get(klic_statu(s), ("", s)))
    data["kod_statu"], data["statni_prislusnost"] = stat.str[0], stat.str[1]
    nesparovane = sorted(data.loc[data.kod_statu == "", "stat_mv"].unique())

    klice = ["kod_okresu", "okres", "kod_kraje", "kraj", "kod_statu", "statni_prislusnost"]
    p = data.pivot_table(index=klice, columns="druh", values=["muzi", "zeny", "celkem"],
                         aggfunc="sum", fill_value=0)
    p.columns = [f"{h}_{d}" for h, d in p.columns]
    p = p.reset_index()
    for d in ("trvaly", "prechodny", "docasna_ochrana"):
        for h in ("muzi", "zeny", "celkem"):
            if f"{h}_{d}" not in p:
                p[f"{h}_{d}"] = 0
    ma_do = "docasna_ochrana" in set(data.druh)
    t = p[klice].copy()
    t["cizinci_trvaly_pobyt"] = p.celkem_trvaly
    # dočasná ochrana je pobyt přechodného typu: do 2023 ji MV vedlo v přechodném pobytu,
    # od 2024 zvlášť – sčítá se do přechodného, aby řada byla souvislá
    t["cizinci_prechodny_pobyt"] = p.celkem_prechodny + p.celkem_docasna_ochrana
    t["cizinci_docasna_ochrana"] = (p.celkem_docasna_ochrana if ma_do
                                    else (pd.NA if stav_k >= ZACATEK_DO else 0))
    t["cizinci_muzi"] = p[[c for c in p.columns if c.startswith("muzi_")]].sum(axis=1)
    t["cizinci_zeny"] = p[[c for c in p.columns if c.startswith("zeny_")]].sum(axis=1)
    t["cizinci_celkem"] = t.cizinci_trvaly_pobyt + t.cizinci_prechodny_pobyt
    t = t[t.cizinci_celkem > 0].copy()
    t["skupina"] = t.kod_statu.map(lambda k: skupina(k, stav_k))
    t.insert(0, "stav_k", stav_k.isoformat())
    t.insert(0, "rok", stav_k.year)

    # kontrola proti součtům MV
    def soucet(druh):
        return soucty.get(druh, {}).get("CR")
    k = {
        "rok": stav_k.year, "mesic": stav_k.month, "stav_k": stav_k.isoformat(), "soubor": cesta.name,
        "mv_celkem": soucet("celkem"), "mv_trvaly": soucet("trvaly"),
        "mv_prechodny": soucet("prechodny"), "mv_docasna_ochrana": soucet("docasna_ochrana"),
        "cizinci_celkem": int(t.cizinci_celkem.sum()),
        "cizinci_trvaly_pobyt": int(t.cizinci_trvaly_pobyt.sum()),
        "cizinci_prechodny_pobyt": int(t.cizinci_prechodny_pobyt.sum()),
        "cizinci_docasna_ochrana": int(t.cizinci_docasna_ochrana.sum()) if ma_do else None,
        "cizinci_eu_ehp_ch": int(t.loc[t.skupina != "třetí země", "cizinci_celkem"].sum()),
        "cizinci_nezjisteny_okres": int(t.loc[t.kod_okresu == "", "cizinci_celkem"].sum()),
        "cizinci_nesparovany_stat": int(t.loc[t.kod_statu == "", "cizinci_celkem"].sum()),
        # buňky, kde muži + ženy ≠ celkem, a řádky, kde součet okresů ≠ CELKOVÝ SOUČET
        "bunky_muzi_zeny_nesedi": int((data.muzi + data.zeny != data.celkem).sum()),
        "radky_soucet_okresu_nesedi": int(
            (data.groupby(["stat_mv", "druh"], sort=False).agg(s=("celkem", "sum"), cr=("celkem_cr", "first"))
             .pipe(lambda g: g.s != g.cr)).sum()),
        "okresy_soucet_nesedi": int(sum(
            data[data.okres_mv == o].celkem.sum() != v for o, v in soucty["celkem"].items() if o != "CR")),
    }
    mv_prechodny = (k["mv_prechodny"] or 0) + (k["mv_docasna_ochrana"] or 0)
    k["rozdil"] = (k["mv_celkem"] - k["cizinci_celkem"]) + (k["mv_trvaly"] - k["cizinci_trvaly_pobyt"]) \
        + (mv_prechodny - k["cizinci_prechodny_pobyt"])
    neparovane = [{"stav_k": stav_k.isoformat(), "nazev_mv": s,
                   "cizinci_celkem": int(t.loc[t.statni_prislusnost == s, "cizinci_celkem"].sum())}
                  for s in nesparovane]
    return t, k, neparovane


def souhrn_okresu(t):
    g = t.assign(
        cizinci_eu_ehp_ch=t.cizinci_celkem.where(t.skupina != "třetí země", 0),
        cizinci_treti_zeme=t.cizinci_celkem.where(t.skupina == "třetí země", 0),
    ).groupby(POPIS, dropna=False)
    o = g[CISLA[:-1] + ["cizinci_eu_ehp_ch", "cizinci_treti_zeme"]].sum()
    # min_count: když dočasná ochrana v roce není známá (2022–2023), zůstane prázdná
    o["cizinci_docasna_ochrana"] = g.cizinci_docasna_ochrana.sum(min_count=1)
    o = o.reset_index()
    return o[POPIS + CISLA + ["cizinci_eu_ehp_ch", "cizinci_treti_zeme"]]


def serad(t, klice):
    # řádek „nezjištěno“ (bez kódu okresu) na konec roku
    return t.assign(_bez=t.kod_okresu.eq("")).sort_values(["rok", "_bez"] + klice).drop(columns="_bez")


def uloz(t, jmeno):
    t.to_csv(VYSTUP / f"{jmeno}.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    t.to_excel(VYSTUP / f"{jmeno}.xlsx", index=False, freeze_panes=(1, 0))


def soubory():
    """{stav_k: cesta} všech stažených souborů od 11/2012 (dřív jiný formát)."""
    out = {}
    for p in DATA.glob("????-?? Cizinci s povoleným pobytem.xls*"):
        stav_k = stav_k_ze_souboru(p)
        if stav_k >= PRVNI_MESIC:
            out[stav_k] = p
    return dict(sorted(out.items()))


def historie_cr():
    """{stav_k: tabulka ČR × stát} za měsíce 1/2007–10/2012 ze starších přehledů (historie.py)."""
    import historie
    try:
        hist = historie.nacti_historii(DATA, CISELNIKY / "staty.csv", klic_statu, nacti_staty())
    except historie.HistorieError as e:
        raise StrukturaError(f"starší přehledy 2007–2012: {e}") from e
    out = {}
    for stav_k, radky in hist.items():
        h = pd.DataFrame(radky)
        h = h.groupby(["kod_statu", "statni_prislusnost"], as_index=False).sum(min_count=1)
        h.insert(0, "stav_k", stav_k.isoformat())
        h.insert(0, "rok", stav_k.year)
        h["skupina"] = h.kod_statu.map(lambda k: skupina(k, stav_k))
        h["cizinci_docasna_ochrana"] = 0
        out[stav_k] = h
    return out


def po_statech(t):
    """Součet přes okresy: ČR × stát."""
    g = t.groupby(["rok", "stav_k", "kod_statu", "statni_prislusnost", "skupina"], dropna=False)
    m = g[CISLA[:-1]].sum(min_count=1)
    m["cizinci_docasna_ochrana"] = g.cizinci_docasna_ochrana.sum(min_count=1)
    return m.reset_index()


def mesicni_rada(tabulky, hist):
    """Měsíční řada za ČR podle státní příslušnosti: 1/2007–10/2012 ze starších přehledů,
    od 11/2012 součet souborů okres × stát."""
    m = pd.concat(list(hist.values()) + [po_statech(t) for t in tabulky], ignore_index=True)
    m.insert(2, "mesic", pd.to_datetime(m.stav_k).dt.month)
    for c in CISLA:
        m[c] = m[c].astype("Int64")
    return m.sort_values(["stav_k", "kod_statu", "statni_prislusnost"])[
        ["rok", "mesic", "stav_k", "kod_statu", "statni_prislusnost", "skupina"] + CISLA]


def staty_cr(detail, hist):
    """Celá ČR podle státní příslušnosti k 31. 12. za roky 2007–2025: 2007–2011 ze starších
    přehledů (historie.py), od 2012 součet tabulky okres × stát přes okresy."""
    casti = [h for s, h in hist.items() if s.month == 12] + [po_statech(detail)]
    t = pd.concat(casti, ignore_index=True)
    for c in CISLA:
        t[c] = t[c].astype("Int64")
    kontrola = t.groupby("rok")[CISLA[:5]].sum(min_count=1).reset_index()
    kontrola["zdroj"] = kontrola.rok.map(lambda r: "policie (PDF)" if r <= 2010 else "MV")
    return (t.sort_values(["rok", "kod_statu", "statni_prislusnost"])[
        ["rok", "stav_k", "kod_statu", "statni_prislusnost", "skupina"] + CISLA], kontrola)


def main():
    if "--stahnout" in sys.argv[1:]:
        import stahni_data
        stahni_data.main([])
    VYSTUP.mkdir(exist_ok=True)
    (VYSTUP / "chyba_struktury.txt").unlink(missing_ok=True)

    vstupy = soubory()
    if not any(s.month == 12 for s in vstupy):
        print(f"Ve složce {DATA} nejsou prosincové soubory MV – spusť nejdřív stahni_data.py")
        return 1
    okresy, staty = nacti_okresy(), nacti_staty()

    tabulky, kontrola, nesparovane = {}, [], []
    for stav_k, cesta in vstupy.items():
        t, k, n = zpracuj_soubor(cesta, okresy, staty)
        tabulky[stav_k] = t
        kontrola.append(k)
        nesparovane += n
        print(f"  {stav_k}: {k['cizinci_celkem']:>10,}".replace(",", " ") + ("" if not k["rozdil"] else "  NESEDÍ"))

    # roční sady: stav k 31. 12.
    detail = pd.concat([t for s, t in tabulky.items() if s.month == 12], ignore_index=True)
    detail["cizinci_docasna_ochrana"] = detail.cizinci_docasna_ochrana.astype("Int64")
    detail = serad(detail, ["kod_okresu", "kod_statu", "statni_prislusnost"])
    detail = detail[POPIS + ["kod_statu", "statni_prislusnost", "skupina"] + CISLA]
    okresni = serad(souhrn_okresu(detail), ["kod_okresu"])
    okresni["cizinci_docasna_ochrana"] = okresni.cizinci_docasna_ochrana.astype("Int64")
    hist = historie_cr()
    mesicne = mesicni_rada(tabulky.values(), hist)
    staty_rocne, kontrola_staty = staty_cr(detail, hist)

    uloz(detail, "cizinci_okresy_staty")
    uloz(staty_rocne, "cizinci_staty")
    kontrola_staty.to_csv(VYSTUP / "kontrola_staty.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    uloz(okresni, "cizinci_okresy")
    uloz(mesicne, "cizinci_mesicne")
    kontrola = pd.DataFrame(kontrola)
    for c in ("mv_trvaly", "mv_prechodny", "mv_docasna_ochrana", "cizinci_docasna_ochrana"):
        kontrola[c] = kontrola[c].astype("Int64")
    kontrola.to_csv(VYSTUP / "kontrola_souctu.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    cesta_n = VYSTUP / "staty_nesparovane.csv"
    if nesparovane:
        pd.DataFrame(nesparovane).to_csv(cesta_n, index=False, encoding="utf-8-sig", lineterminator="\n")
    else:
        cesta_n.unlink(missing_ok=True)

    rocni = kontrola[kontrola.mesic == 12]
    print(rocni[["rok", "mv_celkem", "cizinci_celkem", "rozdil", "cizinci_docasna_ochrana",
                 "cizinci_nesparovany_stat"]].to_string(index=False))
    print(f"Hotovo: {len(detail)} řádků okres × stát, {len(okresni)} řádků okres, "
          f"{len(mesicne)} řádků měsíční řady, {len(staty_rocne)} řádků ČR × stát "
          f"({staty_rocne.rok.min()}–{staty_rocne.rok.max()}) -> {VYSTUP}")

    import kontrola as kontrola_html
    kontrola_html.main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StrukturaError as e:
        # GitHub Actions z tohoto souboru založí issue
        VYSTUP.mkdir(exist_ok=True)
        (VYSTUP / "chyba_struktury.txt").write_text(str(e), encoding="utf-8")
        print(f"CHYBA STRUKTURY: {e}", file=sys.stderr)
        sys.exit(2)
