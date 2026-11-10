"""Měsíce 1/2007–10/2012: cizinci s povoleným pobytem za celou ČR podle státní příslušnosti.

Starší přehledy nemají členění okres × stát, jen státy za celou ČR:
  - 1/2007–12/2010: měsíční PDF Služby cizinecké policie (archiv.policie.gov.cz), tabulka
    „Státní příslušnost | Trvalý | Dlouhodobý | Celkem“ a od 6/2008 i podle pohlaví
    (10/2010 je jen ve formátu .doc a v řadě chybí);
  - 1/2011–10/2012: xls MV, list „Ktg_STP_pohlaví“ (přechodný a trvalý pobyt podle pohlaví).

Dlouhodobý pobyt v PDF odpovídá přechodnému pobytu v pozdějších souborech MV.

Text z PDF má tři problémy, které tady řeší:
  - 2007–2008 mají vlastní kódování několika písmen (Č, ě, ř …), názvy států se proto párují
    podle „kostry“ – jen písmena a–z bez diakritiky (ciselniky/staty.csv musí dávat jednoznačné kostry);
  - prázdné buňky v textu chybí, čísla se do sloupců rozmisťují tak, aby platilo
    muži + ženy = celkem a trvalý + dlouhodobý = celkem; při víc možnostech rozhodnou mezery
    a součty sloupců;
  - v několika řádcích je místo číslice nečitelný znak nebo číslo chybí; takový řádek se doplní
    z druhé tabulky téhož měsíce (podle druhu pobytu ↔ podle pohlaví).
Výsledek se ověřuje proti řádku „Celkový součet“ v každé tabulce.
"""
import calendar
import itertools
import re
import unicodedata
from datetime import date

import pandas as pd

# od 11/2012 jsou xls MV v novém formátu (okres × stát) a čte je zpracuj_data.py
POSLEDNI_XLS = date(2012, 11, 1)


class HistorieError(Exception):
    pass


def kostra(text):
    """Jen písmena a–z, která v textu jsou bez diakritiky; písmena s diakritikou se vynechají
    (v PDF 2007–2008 jsou nahrazená jinými znaky, např. Æ místo á)."""
    text = unicodedata.normalize("NFC", str(text)).lower()
    return re.sub(r"[^a-z]", "", text)


def mapa_kostry(staty_csv):
    """{kostra názvu: (kod_statu, statni_prislusnost)}; kolize kódů je chyba číselníku."""
    s = pd.read_csv(staty_csv, dtype=str, keep_default_na=False)
    mapa = {}
    for r in s.itertuples():
        for nazev in (r.nazev_mv, r.statni_prislusnost):
            k = kostra(nazev)
            if k in mapa and mapa[k][0] != r.kod_statu:
                raise HistorieError(f"kostra {k!r} odpovídá dvěma státům: {mapa[k]} a {r.kod_statu}")
            mapa[k] = (r.kod_statu, r.statni_prislusnost)
    return mapa


# --- PDF ---------------------------------------------------------------------

RADEK = re.compile(r"^(?P<nazev>.*?[^\d\s].*?)(?P<cisla>(?:\s+\d+)+)\s*$")


def radky_pdf(cesta):
    import logging

    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # varování o fontech
    return [r for strana in pypdf.PdfReader(cesta).pages for r in strana.extract_text().splitlines()]


def tokeny(cisla):
    """'   3 3   3 6' -> [(mezera před číslem, číslo), …]"""
    return [(len(m.group(1)), int(m.group(2))) for m in re.finditer(r"(\s+)(\d+)", cisla)]


def rozmisti(tok, sloty, podminky, odhad_mezery):
    """Všechna rozmístění čísel do slotů (se zachováním pořadí), která splní podmínky.

    Vrací nejlepší podle shody chybějících slotů s délkou mezer, nebo None.
    """
    vse = moznosti(tok, sloty, podminky, odhad_mezery)
    return vse[0] if vse else None


def moznosti(tok, sloty, podminky, odhad_mezery):
    """Jako rozmisti, ale vrací všechna různá rozmístění seřazená od nejlepšího."""
    reseni = []
    for pozice in itertools.combinations(range(sloty), len(tok)):
        hodnoty = [0] * sloty
        for p, (_, v) in zip(pozice, tok):
            hodnoty[p] = v
        if not all(f(hodnoty) for f in podminky):
            continue
        skore = 0
        predchozi = -1
        for p, (mezera, _) in zip(pozice, tok):
            skore += abs((p - predchozi - 1) - odhad_mezery(mezera))
            predchozi = p
        reseni.append((skore, hodnoty))
    reseni.sort(key=lambda x: x[0])
    vysledek = []
    for _, h in reseni:
        if h not in vysledek:
            vysledek.append(h)
    return vysledek


def odhad_mezery(mezera):
    """Kolik prázdných buněk asi představuje mezera (jedna buňka ≈ 3 mezery navíc)."""
    return 0 if mezera <= 2 else round((mezera - 1) / 3 + 0.01)


def je_hlavicka(k, predchozi):
    """Hlavička tabulky podle státní příslušnosti (ne podle krajů, okresů a útvarů policie).

    „Státní příslušnost“ bývá na stejném řádku jako Trvalý | Dlouhodobý, nebo o řádek či dva výš.
    """
    if not ("trval" in k and "dlouhodob" in k):
        return False
    if any(x in k for x in ("kraj", "okres", "tvar", "policie", "editelstv", "inspektor")):
        return False
    return "nost" in k or any("nost" in p for p in predchozi)


def tabulky_pdf(radky):
    """Najde tabulku podle druhu pobytu a tabulku podle pohlaví: [(typ, [(řádek, předchozí text)], součet)]."""
    vysledek, aktualni, typ, text = [], None, None, ""
    predchozi = []
    for r in radky:
        k = kostra(r)
        if je_hlavicka(k, predchozi[-2:]):
            typ = "pohlavi" if "celkov" in k else "druh"
            aktualni, text = [], ""
            predchozi = []
            continue
        predchozi.append(k)
        if aktualni is None:
            continue
        if k.startswith("mu") and "celkem" in k:  # podhlavička Muž | Žena | Celkem
            continue
        if k.startswith("celkov") or (k == "celkem" and RADEK.match(r)):
            vysledek.append((typ, aktualni, [int(x) for x in re.findall(r"\d+", r)]))
            aktualni = None
            continue
        # řádek s čísly; poslední číslo může být poškozené (nečitelný znak místo číslice)
        if RADEK.match(r) or re.search(r"[^\d\s]\s+\d+\s+\S", r):
            aktualni.append((r, text))
            text = ""
        elif k:
            text = r.strip()  # název státu zalomený na víc řádků: začátek je na řádku bez čísel
    return vysledek


def oprav_podle_souctu(hodnoty, varianty, soucet, sloupcu):
    """Nejednoznačné řádky (např. jediná osoba – muž, nebo žena?): když součty sloupců nesedí,
    zkusí se jiné rozmístění u jednoho, případně dvou takových řádků."""
    def sloupce():
        return [sum(v[i] for v in hodnoty.values()) for i in range(sloupcu)]
    if sloupce() == soucet:
        return True
    klice = list(varianty)
    for n in (1, 2):
        for vyber in itertools.combinations(klice, n):
            puvodni = {k: hodnoty[k] for k in vyber}
            for kombinace in itertools.product(*(varianty[k] for k in vyber)):
                for k, v in zip(vyber, kombinace):
                    hodnoty[k] = v
                if sloupce() == soucet:
                    return True
            hodnoty.update(puvodni)
    return False


def nacti_pdf(cesta, kostry):
    tab = {typ: (r, s) for typ, r, s in tabulky_pdf(radky_pdf(cesta))}
    if not tab:
        raise HistorieError(f"{cesta.name}: nenašel jsem tabulku podle státní příslušnosti")

    def nazev_radku(nazev, text):
        nazev = nazev.strip()
        if kostra(nazev) not in kostry and text and kostra(text + " " + nazev) in kostry:
            nazev = text + " " + nazev
        if kostra(nazev) not in kostry:
            raise HistorieError(f"{cesta.name}: stát {nazev!r} (kostra {kostra(nazev)!r}) není v ciselniky/staty.csv")
        return kostra(nazev), nazev

    # řádky se mezi tabulkami párují podle kostry původního názvu; některé státy jsou v PDF pod
    # dvěma názvy (např. Zaire a Kongo, demokratická republika) a sčítají se až nakonec
    nazvy = {}

    def precti(typ, sloty, podminky):
        """Vrátí (hodnoty, varianty, poškozené): u poškozených řádků (v PDF místo číslic znaky \x01)
        jsou jen čísla před poškozeným místem; doplní se z druhé tabulky."""
        hodnoty, varianty, poskozene = {}, {}, {}
        for radek, text in tab[typ][0]:
            # „uprchlík dle konvence 1951“: rok úmluvy patří k názvu
            r = re.sub(r"(konvence)\s+1951\b", r"\1", radek)
            # (ve 2007–2008 jsou nečitelné znaky i v názvech států místo písmen s diakritikou)
            m = re.match(r"(.*?[^\d\s])(\s+\d.*)$", r)
            posk = re.search(r"[^\d\s]", m.group(2)) if m else None
            if posk:
                k, nazev = nazev_radku(m.group(1), text)
                poskozene[k] = [int(x) for x in re.findall(r"\d+", m.group(2)[:posk.start()])]
            else:
                m = RADEK.match(r)
                k, nazev = nazev_radku(m.group("nazev"), text)
                vse = moznosti(tokeny(m.group("cisla")), sloty, podminky(k), odhad_mezery)
                if not vse:
                    poskozene[k] = None  # čísla v řádku nesedí – zkusí se doplnit z druhé tabulky
                else:
                    hodnoty[k] = vse[0]
                    if len(vse) > 1:
                        varianty[k] = vse[1:]
            if k in nazvy and nazvy[k][0] == typ:
                raise HistorieError(f"{cesta.name}: řádek {nazev!r} dvakrát")
            nazvy[k] = (typ, nazev, radek)
        return hodnoty, varianty, poskozene

    def zkontroluj(typ, hodnoty, varianty, sloty):
        if not oprav_podle_souctu(hodnoty, varianty, tab[typ][1], sloty):
            sloupce = [sum(v[i] for v in hodnoty.values()) for i in range(sloty)]
            raise HistorieError(f"{cesta.name}: součty sloupců {sloupce} ≠ Celkový součet {tab[typ][1]}")

    # tabulka podle pohlaví má víc čísel na řádek, a tedy méně nejednoznačností – čte se první
    pohlavi, var_p, posk_p = {}, {}, {}
    if "pohlavi" in tab:
        pohlavi, var_p, posk_p = precti("pohlavi", 7, lambda k: [
            lambda v: v[0] + v[1] == v[2], lambda v: v[3] + v[4] == v[5], lambda v: v[2] + v[5] == v[6]])
        if not posk_p:
            zkontroluj("pohlavi", pohlavi, var_p, 7)
            var_p = {}
    if "druh" in tab:
        def podminky_druh(k):
            p = pohlavi.get(k)
            if p is None:
                return [lambda v: v[0] + v[1] == v[2]]
            return [lambda v, p=p: (v[0], v[1], v[2]) == (p[2], p[5], p[6])]
        druh, var_d, posk_d = precti("druh", 3, podminky_druh)
        for k in posk_d:
            if k not in pohlavi:
                raise HistorieError(f"{cesta.name}: řádek {nazvy[k][2]!r} nesedí a nejde doplnit")
            p = pohlavi[k]
            druh[k] = [p[2], p[5], p[6]]
        zkontroluj("druh", druh, var_d, 3)
        if pohlavi or posk_p:
            if set(pohlavi) | set(posk_p) != set(druh):
                raise HistorieError(f"{cesta.name}: tabulky podle druhu a podle pohlaví mají jiné státy: "
                                    f"{sorted((set(pohlavi) | set(posk_p)) ^ set(druh))}")
    else:  # některé měsíce mají jen tabulku podle pohlaví
        druh = {}
    # poškozené řádky tabulky podle pohlaví: známá čísla na začátku + Celkem z tabulky podle druhu
    for k, zacatek in posk_p.items():
        if k not in druh or zacatek is None or len(zacatek) < 4:
            raise HistorieError(f"{cesta.name}: řádek {nazvy[k][2]!r} nesedí a nejde doplnit")
        t, d, c = druh[k]
        mt, zt, ct, md = zacatek[:4]
        v = [mt, zt, ct, md, d - md, d, c]
        if mt + zt != ct or ct != t or md > d:
            raise HistorieError(f"{cesta.name}: řádek {nazvy[k][2]!r} nesedí ani po doplnění")
        pohlavi[k] = v
    if posk_p:
        zkontroluj("pohlavi", pohlavi, var_p, 7)
    if not druh:
        druh = {k: [p[2], p[5], p[6]] for k, p in pohlavi.items()}

    out = {}
    for k, (t, d, c) in druh.items():
        p = pohlavi.get(k)
        radek = out.setdefault(kostry[k], {"cizinci_celkem": 0, "cizinci_muzi": 0, "cizinci_zeny": 0,
                                           "cizinci_trvaly_pobyt": 0, "cizinci_prechodny_pobyt": 0})
        radek["cizinci_celkem"] += c
        radek["cizinci_trvaly_pobyt"] += t
        radek["cizinci_prechodny_pobyt"] += d
        radek["cizinci_muzi"] += p[0] + p[3] if p else 0
        radek["cizinci_zeny"] += p[1] + p[4] if p else 0
    vysledek = []
    for (kod_statu, jmeno), r in out.items():
        if not pohlavi:  # do 5/2008 bez členění podle pohlaví
            r["cizinci_muzi"] = r["cizinci_zeny"] = pd.NA
        vysledek.append({"kod_statu": kod_statu, "statni_prislusnost": jmeno, **r})
    return vysledek


# --- xls 2011 ----------------------------------------------------------------

def ascii_klic(text):
    """Bez diakritiky, jen a–z (xls má diakritiku v pořádku)."""
    text = unicodedata.normalize("NFKD", str(text)).lower()
    return re.sub(r"[^a-z]", "", text)


def nacti_xls_2011(cesta, kostry, klic_statu, staty):
    xl = pd.ExcelFile(cesta, engine="xlrd")
    list_ = next(s for s in xl.sheet_names if ascii_klic(s) == "ktgstppohlavi")
    df = pd.read_excel(xl, sheet_name=list_, header=None)
    hlavicka = next(i for i in range(10) if ascii_klic(df.iat[i, 1]).startswith("prechodn"))
    if not (ascii_klic(df.iat[hlavicka, 4]).startswith("trval")
            and [ascii_klic(x) for x in df.iloc[hlavicka + 1, 1:7]] == ["muz", "zena", "celkem"] * 2):
        raise HistorieError(f"{cesta.name}: neznámá hlavička listu {list_}")
    out, soucet = [], None
    for r in df.iloc[hlavicka + 2:].itertuples(index=False):
        if pd.isna(r[0]):
            continue
        cisla = [int(x) if pd.notna(x) else 0 for x in r[1:8]]
        if ascii_klic(r[0]).startswith("celkov"):
            soucet = cisla
            break
        kod, jmeno = staty.get(klic_statu(r[0])) or kostry.get(kostra(r[0]), (None, None))
        if kod is None:
            raise HistorieError(f"{cesta.name}: stát {r[0]!r} není v ciselniky/staty.csv")
        out.append({"kod_statu": kod, "statni_prislusnost": jmeno, "cizinci_celkem": cisla[6],
                    "cizinci_muzi": cisla[0] + cisla[3], "cizinci_zeny": cisla[1] + cisla[4],
                    "cizinci_trvaly_pobyt": cisla[5], "cizinci_prechodny_pobyt": cisla[2]})
    sloupce = [sum(o[c] for o in out) for c in ("cizinci_prechodny_pobyt", "cizinci_trvaly_pobyt", "cizinci_celkem")]
    if soucet is None or sloupce != [soucet[2], soucet[5], soucet[6]]:
        raise HistorieError(f"{cesta.name}: součty {sloupce} ≠ Celkový součet {soucet}")
    return out


def stav_k(nazev):
    """'2009-05 Cizinci…' -> poslední den měsíce."""
    rok, mesic = int(nazev[:4]), int(nazev[5:7])
    return date(rok, mesic, calendar.monthrange(rok, mesic)[1])


def nacti_historii(data, staty_csv, klic_statu, staty):
    """{stav_k: [řádky]} za měsíce 1/2007–10/2012, které jsou stažené.

    1/2007–12/2010 měsíční PDF policie (10/2010 je jen ve formátu .doc a chybí),
    1/2011–10/2012 xls MV se státní příslušností bez okresů. Od 11/2012 čte zpracuj_data.py.
    """
    kostry = mapa_kostry(staty_csv)
    out = {}
    for cesta in data.glob("20??-?? Cizinci s povoleným pobytem (policie).pdf"):
        out[stav_k(cesta.name)] = nacti_pdf(cesta, kostry)
    for cesta in data.glob("201[12]-?? Cizinci s povoleným pobytem.xls"):
        s = stav_k(cesta.name)
        if s < POSLEDNI_XLS:
            out[s] = nacti_xls_2011(cesta, kostry, klic_statu, staty)
    return dict(sorted(out.items()))
