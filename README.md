# OpenCassa

Moduláris, Python és `tkinter` alapú pont-of-sale (POS) alkalmazás négy különálló munkafüllel (`Termékek`, `Egyszerű kassza`, `Gyári kassza`, `Egyéb & Settings`), JSON-alapú adatkezeléssel, sorszámozott nyugtagenerálással és hardveres integrációkkal.

## Projektstruktúra

- `main.py` — Az alkalmazás belépési pontja és főablaka (`UniversalPosApp`), amely összeköti a füleket, a hardveres eseményeket és az érintőképernyős / beállítási frissítéseket.
- `store.py` — Adatmodellek (`Product`, `CustomFee`, `Settings`), JSON-alapú perzisztencia (`StoreManager`), nyugtakészítés, képtárkezelés és hardveres vezérlés (`HardwareManager`).
- `tab_products.py` — Termékkatalógus-kezelő fül: új termékek felvétele, képválasztás saját fájlból vagy `simpleicons` képtárból, opcionális vonalkód-beolvasás és `*` karaktertiltás a termékkódban.
- `tab_simple_pos.py` — Érintésbarát / vizuális kassza: termék- és kiszerelésgombok, soronkénti törlés (`🗑️`), beállított egyedi díj gomb, készpénzes/kártyás fizetés és nyugtaelőnézet.
- `tab_factory_pos.py` — Gyári / billentyűzetvezérelt kassza: kód/vonalkód beolvasás, `KOD*MENNYISEG` (pl. `T001*3`) szorzó, `↑`/`↓` léptetés, `Backspace` törlés és `F2`–`F5` / `Esc` gyorsbillentyűk.
- `tab_settings.py` — Eszköz- és kasszabeállítások: kasszafiók, vonalkódolvasó, bankkártya-terminál, érintőképernyős mód és az egyszeri egyedi díj (`+<név>`, Ft) konfigurálása.

## Főbb funkciók

### 1. Termékek (`Termékek`)
- **Kötelező és opcionális mezők**: a **Név**, a **Termékkód** (`*` karakter nélkül) és az **Ár (Ft)** kötelező; a **Vonalkód** nem kötelező.
- **Képválasztás**: a *Kép kiválasztása...* gombbal választhatsz saját képfájlt a gépről, vagy megnyithatod a kereshető, előnézetes képtárat a `simpleicons` mappából. A kiválasztott képek a `product_images/` mappába másolódnak.
- **Vonalkód-beolvasás**: támogatható kamerával, USB-HID vagy soros (COM) olvasóval a beállított hardverkonfigurációtól függően.

### 2. Egyszerű kassza (`Egyszerű kassza`)
- Kattintható/érinthető termékkártyák alap- és opcionális kiszerelési árral.
- Minden kosár- és díjsor mellett külön `🗑️` gombbal törölhető az adott tétel.
- Egykattintásos gomb a Beállításokban megadott egyedi díj (`+<név>`) hozzáadásához.
- Készpénzes vagy kártyás fizetés, automatikus sorszámozott nyugtamentéssel (`receipts/`).

### 3. Gyári kassza (`Gyári kassza`)
- Gyors kód- és vonalkódbevitel (`Kód / Vonalkód` mező vagy USB-HID / COM / kamera).
- **Mennyiségszorzó (`KOD*MENNYISEG`)**: például `T001*3` esetén a rendszer 3 darabbal veszi fel a terméket.
- **Gyorsbillentyűk**:
  - `Enter`: tétel / szorzott tétel hozzáadása
  - `↑` / `↓`: kijelölés léptetése a listában
  - `Backspace`: kijelölt tétel vagy díj törlése
  - `F2`: fizetési mód — Készpénz
  - `F3`: fizetési mód — Kártya
  - `F4`: fizetés és nyugtamentés
  - `F5`: a Beállításokban elmentett egyedi díj hozzáadása
  - `Esc`: aktuális tétellista és díjak törlése

### 4. Egyéb & Settings (`Egyéb & Settings`)
- **Hardverek**: kasszafiók állapota, vonalkódolvasó (`USB-HID (Wireless/Wired)`, `SERIAL (COM)`, `CAMERA`), bankkártya-terminál (`SIM / AUTO`, `SERIAL (COM)`, `TCP / LAN`) és eszközteszt.
- **Kassza és felület**: kassza neve, nyelv (`hu` / `en`), érintőképernyős mód (`touch_mode`), valamint az **egyedi díj neve és ára**, amelyet egyszerre itt állíthatsz be, és a kasszákban gombbal (illetve a gyári kasszában `F5`-tel) vehetsz fel a vásárláshoz.

## Adatok és mappák

A futás során az alábbi fájlok és mappák jönnek létre / kerülnek felhasználásra:
- `store_data.json` — termékek, beállítások és a következő nyugtaszám (`next_receipt_number`).
- `receipts/` — sorszámozott `.txt` nyugták (`nyugta_000001_ÉÉÉÉHHNN_ÓÓPPMP.txt`).
- `product_images/` — a termékekhez importált képek másolatai.
- `simpleicons/` — opcionális képtár mappa előre összerakott termékképekkel/ikonokkal.

## Telepítés és futtatás

Alapfunkciókhoz a Python szabványos könyvtára (`tkinter`, `json`, `socket`, `threading`, `dataclasses`) elegendő. Opcionális kép-, vonalkód-, kamera-, PDF- és soros port-támogatáshoz telepíthetők a kiegészítő csomagok:

```bash
pip install pillow pyserial opencv-python pyzbar pypdfium2 numpy
```

Indítás:

```bash
python main.py
```
