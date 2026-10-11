"""Lee el Excel ENTREGA_DE_PETROLEO (hojas BDR = entregas y BDC = cargas al estanque) y genera petroleo.json.
Se ejecuta a mano (python actualizar_petroleo.py archivo.xlsm) o desde GitHub Actions (secreto DROPBOX_URL_PETROLEO)."""
import io, json, os, sys, urllib.request, datetime
from openpyxl import load_workbook

URL = os.environ.get("DROPBOX_URL_PETROLEO", "").strip()
SALIDA = "petroleo.json"
MESES = ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO","JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"]

def descargar(url):
    if not url: sys.exit("Falta el secreto DROPBOX_URL_PETROLEO.")
    url = url.replace("dl=0", "dl=1")
    if "dropbox.com" in url and "dl=1" not in url: url += ("&" if "?" in url else "?") + "dl=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r: return r.read()

def fecha(v):
    if isinstance(v, datetime.datetime): v = v.date()
    if isinstance(v, datetime.date) and v.year >= 2000: return v.isoformat()
    return None

def txt(v): return " ".join(str(v or "").upper().split())

def leer(contenido):
    wb = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    for h in ("BDR", "BDC"):
        if h not in wb.sheetnames: sys.exit(f"No se encontró la hoja {h}.")
    dic = {"maq": [], "sol": [], "cc": [], "enc": []}
    def ix(k, v):
        v = txt(v) or "SIN DATO"
        if v not in dic[k]: dic[k].append(v)
        return dic[k].index(v)
    entregas, corregidas, prev = [], [], None
    # BDR desde la fila 6: C fecha, D máquina, E solicitante, F litros, G encargado, H centro de costo, I mes, J año, K destino
    for i, r in enumerate(wb["BDR"].iter_rows(min_row=6, min_col=3, max_col=11, values_only=True), start=6):
        if all(v is None for v in r): continue
        try: lit = float(r[3])
        except (TypeError, ValueError): continue
        f = fecha(r[0])
        if f is None and not txt(r[1]): continue   # fila de total u otra fila sin máquina
        if f is None:
            # fecha mal escrita: se usa la fecha del registro anterior si coincide el mes/año declarado
            f = prev
            corregidas.append(i)
            if f is None: continue
        prev = f
        dest = 1 if txt(r[8]).startswith("EXTERN") else 0
        entregas.append([f, ix("maq", r[1]), ix("sol", r[2]), round(lit, 1), ix("cc", r[5]), dest, ix("enc", r[4])])
    cargas = []
    # BDC desde la fila 6: C fecha, D mes, E solicitante, F litros
    for r in wb["BDC"].iter_rows(min_row=6, min_col=3, max_col=6, values_only=True):
        f = fecha(r[0])
        try: lit = float(r[3])
        except (TypeError, ValueError): continue
        if f is None: continue
        cargas.append([f, round(lit, 1), ix("sol", r[2])])
    return entregas, cargas, dic, corregidas

def main(contenido=None):
    entregas, cargas, dic, corr = leer(contenido or descargar(URL))
    if len(entregas) < 20: sys.exit(f"Muy pocos registros ({len(entregas)}): no se actualiza.")
    entregas.sort(key=lambda x: x[0]); cargas.sort(key=lambda x: x[0])
    datos = {"actualizado": max(e[0] for e in entregas), "entregas": entregas, "cargas": cargas, "corregidas": corr, **dic}
    nuevo = json.dumps(datos, separators=(",", ":"), ensure_ascii=False)
    viejo = open(SALIDA, encoding="utf-8").read() if os.path.exists(SALIDA) else ""
    if nuevo == viejo: print("Sin cambios."); return
    open(SALIDA, "w", encoding="utf-8").write(nuevo)
    print(f"petroleo.json: {len(entregas)} entregas, {len(cargas)} cargas, {len(dic['maq'])} máquinas; filas con fecha corregida: {corr}")

if __name__ == "__main__":
    main(open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else None)
