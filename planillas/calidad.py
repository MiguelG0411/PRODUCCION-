"""CONTROL DE CALIDAD, hojas BD (lotes = pallets) y BDS (salidas). 1 lote = 1 pallet.
BD desde la fila 6: A lote, B fecha, C pH, D acidez libre, E % insoluble, F % cobre, G % humedad, H pureza,
    I aspecto físico, J olor, K flotación, L categoría, M responsable, N lavado, O secado, P turno, T estado.
BDS desde la fila 4: C lote, D fecha salida, E camión, F conductor, G fecha ingreso, H tonelaje, I días de almacenamiento."""
from .comun import libro, hoja, filas, fecha, num, minimo


def leer(contenido):
    wb = libro(contenido)
    bd, bds = hoja(wb, "BD"), hoja(wb, "BDS")
    dic = {"ops": [], "asp": [], "olor": [], "flot": []}
    def ix(k, v):
        v = " ".join(str(v or "").upper().split()) or "SIN DATO"
        if v not in dic[k]: dic[k].append(v)
        return dic[k].index(v)
    def nf(v):
        x = num(v)
        return round(x, 4) if x is not None else None
    lotes = []
    for _, f in filas(bd, 1, 20, desde_fila=6):
        lote, fch = f[0], fecha(f[1])
        if lote is None or fch is None: continue
        try: lote = int(lote)
        except (TypeError, ValueError): continue
        try: cat = int(f[11])
        except (TypeError, ValueError): cat = 0
        est = 1 if str(f[19] or "").strip().upper() == "ALMACENADO" else 0
        turno = str(f[15] or "").strip().upper()[:1]
        lotes.append([lote, fch, cat, est, nf(f[2]), nf(f[3]), nf(f[4]), nf(f[5]), nf(f[6]), nf(f[7]),
                      ix("asp", f[8]), ix("olor", f[9]), ix("flot", f[10]), ix("ops", f[12]), turno, nf(f[13]), nf(f[14])])
    salidas = []
    for _, f in filas(bds, 3, 9, desde_fila=4):
        lote, fch, cam, cond, _fing, ton, dias = f
        fch = fecha(fch)
        if fch is None: continue
        try: lote = int(lote)
        except (TypeError, ValueError): lote = 0  # SIN LOTE
        ton = num(ton)
        try: dias = int(dias)
        except (TypeError, ValueError): dias = None
        salidas.append([lote, fch, str(cam or "").strip().upper(), " ".join(str(cond or "").upper().split()),
                        round(ton, 3) if ton is not None else None, dias])
    minimo(len(lotes), 50, "lotes de control de calidad")
    lotes.sort(key=lambda x: (x[1], x[0])); salidas.sort(key=lambda x: x[1])
    return {"tonPallet": 1.25, "actualizado": max(l[1] for l in lotes), "lotes": lotes, "salidas": salidas, **dic}
