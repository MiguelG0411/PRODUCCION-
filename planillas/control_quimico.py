"""CONTROL-QUIMICO-2025.xlsm.
Hoja BD (soluciones, 4 muestras al día): C solución, D fecha; Cu, H+ y pH a las 07:00 (F-H), 11:00 (I-K),
15:00 (L-N) y 19:00 (O-Q). Soluciones: PLS, ILS LIX, REF LIX, REF SX 1/2 y ELECTROLITO 1/2 (tren 1 y tren 2).
Hoja BDP (pilas, 2 muestras al día): C pila, D fecha; G Cu y H H+ a las 07:00, K riego, L destino,
N Cu y O H+ a las 19:00. Pilas P (mineral) y R (ripio); la Mega Pila no se considera.
Los promedios los calcula la app con las muestras que existan (no se usan las columnas de promedio del Excel)."""
from .comun import libro, hoja, filas, fecha, num, txt, minimo

SOLUCIONES = ["PLS", "ILS LIX", "REF LIX", "REF SX 1", "REF SX 2", "ELECTROLITO 1", "ELECTROLITO 2"]


def r2(x):
    return round(x, 3) if x is not None else None


def leer(contenido):
    wb = libro(contenido)
    sol = {}
    for _, r in filas(hoja(wb, "BD"), 3, 17, desde_fila=5):
        f, it = fecha(r[1]), txt(r[0])
        if f is None or it not in SOLUCIONES: continue
        cu = [r2(num(r[i])) for i in (3, 6, 9, 12)]
        h = [r2(num(r[i])) for i in (4, 7, 10, 13)]
        ph = [r2(num(r[i])) for i in (5, 8, 11, 14)]
        if all(x is None for x in cu + h): continue
        sol.setdefault(f, {})[it] = [cu, h, ph]
    minimo(len(sol), 20, "días de control de soluciones")
    pilas = {}
    for _, r in filas(hoja(wb, "BDP"), 3, 15, desde_fila=5):
        f, p = fecha(r[1]), txt(r[0])
        if f is None or not p or p[0] not in "PR" or p.startswith("MEGA"): continue
        cu7, h7, cu19, h19 = (r2(num(r[i])) for i in (4, 5, 11, 12))
        riego, dest = txt(r[8]) or None, txt(r[9]) or None
        if cu7 is None and cu19 is None and h7 is None and h19 is None: continue
        pilas.setdefault(p, {})[f] = [cu7, cu19, h7, h19, riego, dest]
    return {"actualizado": max(sol), "soluciones": dict(sorted(sol.items())),
            "pilas": {k: [[f] + v for f, v in sorted(d.items())] for k, d in sorted(pilas.items())}}
