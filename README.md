# Cizinci s povoleným pobytem v ČR

Počty cizinců s povoleným pobytem po okresech a podle státní příslušnosti za roky 2012–2025,
vždy k 31. prosinci, za celou ČR podle státní příslušnosti od roku 2007 a k tomu měsíční řada
za celou ČR od ledna 2007. Zdrojem jsou měsíční přehledy Ministerstva vnitra ČR „Cizinci s povoleným
pobytem“, za roky 2007–2010 přehledy Služby cizinecké policie.

- **Web s daty ke stažení:** https://opendatabrno.github.io/cizinci/
- **Zdroj MV:** [aktuální rok](https://mv.gov.cz/cizinci-s-povolenym-pobytem-2) ·
  [archiv 2008–2025](https://archiv.mv.gov.cz/clanek/cizinci-s-povolenym-pobytem.aspx) ·
  [Služba cizinecké policie 2007–2010](https://archiv.policie.gov.cz/clanek/statistiky-885151.aspx)
- Sesterská sada: [obyvatelé obcí](https://github.com/opendatabrno/obyvatele) (informativní počty obyvatel MV)

**Obsah:** [Datové sady](#datové-sady) · [Sloupce](#sloupce) · [Na co si dát pozor](#na-co-si-dát-pozor) ·
[Aktualizace dat](#aktualizace-dat) · [Kontroly](#kontroly) · [Soubory v repozitáři](#soubory-v-repozitáři) ·
[Jak se data zpracovávají](#jak-se-data-zpracovávají)

---

## Datové sady

| Soubor | Co obsahuje | Jeden řádek | Klíč |
|---|---|---|---|
| [`vystup/cizinci_okresy.csv`](vystup/cizinci_okresy.csv) | všech 77 okresů ČR + řádek „nezjištěno“ | okres × rok | `rok` + `kod_okresu` |
| [`vystup/cizinci_okresy_staty.csv`](vystup/cizinci_okresy_staty.csv) | okresy podle státní příslušnosti (~6 tis. řádků za rok) | okres × stát × rok | `rok` + `kod_okresu` + `kod_statu` |
| [`vystup/cizinci_staty.csv`](vystup/cizinci_staty.csv) | celá ČR podle státní příslušnosti od roku 2007 | stát × rok | `rok` + `kod_statu` |
| [`vystup/cizinci_mesicne.csv`](vystup/cizinci_mesicne.csv) | celá ČR podle státní příslušnosti, každý měsíc od 1/2007 (chybí 10/2010) | stát × měsíc | `stav_k` + `kod_statu` |

- Roční sady jsou ze souborů se stavem k 31. 12. Rok, za který MV prosincový soubor ještě nevydalo,
  v nich není (stav k 31. 12. 2026 přibude koncem ledna 2027). Aktuální vývoj ukazuje měsíční řada.
- Formát: CSV, UTF-8 (s BOM, aby šel otevřít v Excelu), oddělovač čárka. Na [webu](https://opendatabrno.github.io/cizinci/)
  jsou sady ke stažení i jako Excel (`.xlsx`), lokálně vzniká `.xlsx` při zpracování.
- Kódy okresů a krajů jsou kódy NUTS/LAU ČSÚ (`CZ0642` = Brno-město), takže se dají spojit s dalšími daty,
  např. s okresy v sadě [obyvatelé obcí](https://github.com/opendatabrno/obyvatele).
- Státy mají kód ISO 3166-1 alpha-3, názvy jsou sjednocené napříč lety (MV je několikrát změnilo).
- **Řádky různých sad nesčítej dohromady.** Jsou to různé pohledy na stejné osoby: tabulka okresů je součet
  tabulky okres × stát přes státy; tabulka států od 2012 i měsíční řada za prosinec jsou součet téže
  tabulky přes okresy.
- Roky 2007–2011 jsou jen za celou ČR (`cizinci_staty.csv` k 31. 12., `cizinci_mesicne.csv` po měsících):
  starší přehledy nemají členění okres × stát. Měsíční řada se ze starších přehledů skládá do 10/2012,
  od 11/2012 je součtem souborů okres × stát.

## Sloupce

| Sloupec | Význam | Sady |
|---|---|---|
| `rok` | rok | všechny |
| `mesic` | měsíc 1–12 | měsíční |
| `stav_k` | den, ke kterému MV počty uvádí (poslední den měsíce, v ročních sadách vždy 31. 12.) | všechny |
| `kod_okresu`, `okres` | kód a název okresu; Praha = `CZ0100`. Řádek `nezjištěno` s prázdným kódem = cizinci, kterým MV nepřiřadilo adresu | okresní |
| `kod_kraje`, `kraj` | kraj, kam okres patří | okresní |
| `kod_statu`, `statni_prislusnost` | kód ISO 3166-1 alpha-3 a sjednocený název státu (zvláštní kódy viz níže) | okres × stát, státy, měsíční |
| `skupina` | `EU, EHP, Švýcarsko`, nebo `třetí země`, podle členství ke dni `stav_k` | okres × stát, státy, měsíční |
| `cizinci_celkem`, `cizinci_muzi`, `cizinci_zeny` | cizinci s povoleným pobytem; muži a ženy prázdné do 5/2008 (zdroj je neuvádí), v tabulce států tedy za rok 2007 | všechny |
| `cizinci_trvaly_pobyt`, `cizinci_prechodny_pobyt` | podle druhu pobytu; přechodný pobyt zahrnuje i dočasnou ochranu | všechny |
| `cizinci_docasna_ochrana` | z toho dočasná ochrana: do února 2022 `0`, od března 2022 do září 2024 prázdné (MV ji vedlo v přechodném pobytu bez rozlišení), od října 2024 počet. V ročních sadách: do 2021 `0`, 2022–2023 prázdné, od 2024 počet | všechny |
| `cizinci_eu_ehp_ch`, `cizinci_treti_zeme` | rozdělení `cizinci_celkem` podle skupiny států | okresy |

**Jak se sloupce sčítají:**

```
cizinci_celkem = cizinci_muzi + cizinci_zeny                             (kromě jedné chyby MV v 8/2015)
cizinci_celkem = cizinci_trvaly_pobyt + cizinci_prechodny_pobyt
cizinci_celkem = cizinci_eu_ehp_ch + cizinci_treti_zeme                 (tabulka okresů)
cizinci_docasna_ochrana ⊂ cizinci_prechodny_pobyt                       (podmnožina, nepřičítat)

cizinci_okresy         = cizinci_okresy_staty sečtené přes kod_statu     (pro každý rok a okres)
cizinci_mesicne, 12/RRRR = cizinci_staty                                (pro každý rok a stát)
cizinci_staty, od 2012   = cizinci_okresy_staty sečtené přes okresy      (pro každý rok a stát)
```

Součet všech okresů včetně řádku `nezjištěno` dává za rok celkový počet cizinců podle MV.

**Zvláštní kódy států:** `XKX` Kosovo, `XXA` osoba bez státní příslušnosti, `XXB` uprchlík podle úmluvy,
`XXC` uprchlík ostatní, `XXX` neuvedeno nebo neznámo, `UNO` Organizace spojených národů, `GBN`/`GBD` britská zámořská národnost/území,
`SUN` Společenství nezávislých států, `YUG` Svazová republika Jugoslávie, `SCG` Srbsko a Černá Hora
(MV tyto historické příslušnosti stále eviduje u lidí s dlouhodobým pobytem).

## Na co si dát pozor

- **Nejde o počet obyvatel ČSÚ.** Je to evidence MV: cizinci s platným povolením k trvalému pobytu,
  s dlouhodobým vízem nebo pobytem nad 90 dní a občané EU, EHP a Švýcarska s pobytem přihlášeným u MV.
- **Dočasná ochrana (od března 2022):** v roce 2022 přibylo ~450 tis. lidí. V souborech do září 2024 jsou
  v přechodném pobytu bez rozlišení, od října 2024 má MV samostatný druh pobytu „dočasná ochrana“. Tady se
  vždy přičítá k přechodnému pobytu, aby řada byla souvislá, a zvlášť je ve sloupci `cizinci_docasna_ochrana`.
  Pro srovnání v čase bez dočasné ochrany použij od 2024 `cizinci_celkem − cizinci_docasna_ochrana`,
  pro 2022–2023 je potřeba jiný zdroj (týdenní statistiky MV k válce na Ukrajině).
- **Brexit:** Spojené království je ve skupině `EU, EHP, Švýcarsko` do roku 2020 (konec přechodného období),
  od 2021 mezi třetími zeměmi. Chorvatsko je v EU od 1. 7. 2013 (stav k 31. 12. 2012 = třetí země).
- **Okres** je podle aktuální adresy pobytu. Cizinci bez určené adresy jsou v řádku `nezjištěno`
  (0,7–3,9 tis. osob za rok).
- **1/2007–10/2012** jsou jen za celou ČR (`cizinci_staty.csv`, `cizinci_mesicne.csv`). 2007–2010 jsou
  z měsíčních PDF Služby cizinecké policie, kde se přechodnému pobytu říká „dlouhodobý“ pobyt (stejná
  kategorie). PDF ztrácejí při čtení prázdné buňky a část diakritiky, v několika řádcích je místo číslice
  nečitelný znak. Parser proto čísla rozmisťuje tak, aby platilo muži + ženy = celkem a trvalý + dlouhodobý
  = celkem, poškozený řádek doplní z druhé tabulky téhož měsíce (podle pohlaví ↔ podle druhu pobytu)
  a každý měsíc ověřuje proti řádku „Celkový součet“ (viz `historie.py`). **Říjen 2010 chybí**: policie ho
  zveřejnila jen ve formátu .doc. 1/2011–10/2012 jsou ze souborů MV, které mají státy a okresy jen zvlášť.
  Mezi 2009 a 2011 počet klesal (hospodářská krize).
- **Prosinec 2011:** přechodných pobytů občanů třetích zemí přibylo za měsíc 30 tis. (+7 %). Skok je už
  v souboru MV, nejspíš jde o změnu evidence, ne o skutečný příchod.
- **Měsíční řada** ukazuje věci, které roční čísla skryjí: březnový pokles každý rok (průměrně −16 tis.,
  končí platnost povolení), příchod lidí s dočasnou ochranou v březnu 2022 (+250 tis. za měsíc) a pokles
  v březnu 2023 (−121 tis., neprodloužená dočasná ochrana). Měsíce aktuálního roku jsou k dispozici
  dřív než prosincový soubor.

## Aktualizace dat

Workflow [`.github/workflows/aktualizace.yml`](.github/workflows/aktualizace.yml) v lednu a únoru běží denně,
zbytek roku každé pondělí. Stáhne nové soubory MV, zpracuje je a změny pošle jako **pull request**.
V textu pull requestu je souhrn kontrol, celý přehled kontrol je přiložený jako artefakt běhu.

- Když nový soubor MV nejde přečíst (změnil se formát), workflow založí **issue** se štítkem
  `zmena-struktury` a popisem souboru (listy, první řádky), aby šlo parser rychle upravit.
- Po sloučení pull requestu workflow [`pages.yml`](.github/workflows/pages.yml) přestaví web.
- Zdrojové Excely nejsou v repozitáři. V GitHub Actions se drží v cache, stahují se jen nové.

**Lokálně** (Python 3.12+):

```bash
pip install -r requirements.txt
python zpracuj_data.py --stahnout   # stáhne, co chybí, a vytvoří vystup/*.csv, *.xlsx a kontrola.html
```

Jde to i po krocích: `python stahni_data.py` stáhne soubory MV a policie (~170 souborů, ~60 MB) a číselník okresů,
`python zpracuj_data.py` je zpracuje (~4 min) a `python web.py` sestaví web do `_site/`.

Zdrojové soubory se ukládají do složky `data/`. Jinou složku nastavíš proměnnou prostředí `CIZINCI_DATA`,
např. `CIZINCI_DATA="C:/Data/Cizinci" python zpracuj_data.py`.

## Kontroly

`zpracuj_data.py` na konci vytvoří přehled [`vystup/kontrola.html`](https://opendatabrno.github.io/cizinci/kontrola.html)
(na webu i jako artefakt pull requestu). Kontroluje:

| Kontrola | Co znamená chyba |
|---|---|
| **Součty proti MV** – za každý soubor: součet všech okresů a států = řádky CELKEM v souboru MV, zvlášť pro celkem, trvalý, přechodný pobyt a dočasnou ochranu | parser něco vynechal nebo započetl dvakrát |
| **Roční řada** – žádný rok nechybí, meziroční změna do 15 % mimo známé zlomy (2021, 2022, 2024) | chybí soubor nebo je načtený špatně |
| **Názvy států** – každý název státu ze souboru je v `ciselniky/staty.csv` | MV použilo nový název, doplň ho do číselníku |
| **Měsíční řada** – žádný měsíc nechybí (kromě 10/2010, který ve zdroji není), změna do 5 % za měsíc mimo 12/2011, 3–4/2022 a 3/2023 | chybí soubor nebo je načtený špatně |
| **ČR podle států od 2007**: žádný rok nechybí, od 2012 se tabulka rovná součtu okresů, 2007–2011 (a každý měsíc do 10/2012) sedí na „Celkový součet“ ve zdroji (parser jinak skončí chybou) | chybí soubor nebo je PDF přečtené špatně |
| **Nesoulad v souborech MV** – muži + ženy = celkem, součet okresů = celkový součet | jen informace: chyba je už ve zdroji (8/2015 jedna buňka, 6/2023 dva okresy), data se přebírají beze změny |

Strukturu souboru hlídá parser: když nenajde hlavičku `STP | DRUH POBYTU`, bloky sloupců
`muži | ženy | okres celkem` pro všechny okresy, známý druh pobytu nebo známý okres, skončí chybou
`StrukturaError` s popisem souboru (z ní vzniká issue).

## Soubory v repozitáři

| Soubor | Účel |
|---|---|
| `stahni_data.py` | stažení souborů MV (archiv pevným seznamem prosinců + hledání ostatních měsíců, aktuální rok hledáním na stránkách MV), měsíčních PDF policie 2007–2010, xls MV 2011–2012 a číselníku okresů |
| `zpracuj_data.py` | načtení souborů, sjednocení kategorií, výstupní tabulky, kontrola součtů |
| `historie.py` | měsíce 1/2007–10/2012 za celou ČR: čtení PDF policie a xls MV 2011–2012 |
| `kontrola.py` | HTML přehled kontrol a souhrn pro pull request |
| `web.py` | web pro GitHub Pages (`_site/`) |
| `ciselniky/staty.csv` | sjednocení názvů států: název podle MV nebo policie → sjednocený název a kód ISO; ručně udržovaný |
| `ciselniky/cnumnuts.csv` | okresy a kraje s kódy NUTS/LAU (volby.gov.cz), stahuje `stahni_data.py` |
| `vystup/*.csv` | datové sady, `kontrola_souctu.csv` (jeden řádek = jeden soubor MV) a `kontrola_staty.csv` (součty tabulky států za rok) |

## Jak se data zpracovávají

Každý soubor MV je jeden list s širokou tabulkou:

- **řádky** = státní příslušnost × druh pobytu (`PŘECHODNÝ`/`PŘECHODNĚ`, `TRVALE`, od 2024 `DOČASNÁ OCHRANA`),
  název státu je jen na prvním řádku státu;
- **sloupce** = okres × (muži, ženy, okres celkem), na konci okres `NULL*` (nezjištěno) a `CELKOVÝ SOUČET`;
- na konci tabulky řádky `CELKEM` za jednotlivé druhy pobytu a za všechno.

Postup:

1. Parser najde hlavičku a bloky sloupců podle popisků (ne podle pozice, některé měsíční soubory mají sloupce
   navíc nebo chybějící název okresu) a převede tabulku na dlouhý tvar stát × druh × okres.
2. Okresy se spárují podle názvu s číselníkem NUTS (`Hlavní město Praha` → Praha `CZ0100`), neznámý okres je chyba.
3. Názvy států se sjednotí přes `ciselniky/staty.csv` (např. `Ruská federace` → `Rusko`, `Velká Británie` →
   `Spojené království`, `Makedonie,býv.jug.rep.` → `Severní Makedonie`). Porovnává se bez mezer, protože
   MV v názvech mění mezery za tečkou a čárkou.
4. Druhy pobytu se převedou na sloupce: trvalý, přechodný (+ dočasná ochrana), dočasná ochrana.
5. Ze souborů k 31. 12. vzniknou roční sady, ze všech souborů měsíční řada za ČR. Tabulka států za ČR
   se od 2012 sečte z okresů a doplní o roky 2007–2011 ze starších přehledů (`historie.py`), měsíční řada
   stejně o měsíce 1/2007–10/2012.
6. Součty se porovnají s řádky CELKEM v souboru MV (`vystup/kontrola_souctu.csv`) a vznikne přehled kontrol.

## Licence

Kód: MIT (viz [LICENSE](LICENSE)). Data: zdrojem je Ministerstvo vnitra ČR.
