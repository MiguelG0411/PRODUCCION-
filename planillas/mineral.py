"""INGRESO-MINERAL-2026.xlsm.
Hoja BD: C lote, D fecha, E peso, F mina, K ley, L consumo, O fecha de chancado, P pila de destino, T valor del lote.
Estado de cada lote: chancado si tiene fecha de chancado; stock pile si tiene ley y no está chancado; si no, disponible.
Hoja INFORME DE PILAS desde X14: tarifas ENAMI (X fecha, AB base, AC escala, AD ácido).
Hoja INFORME DE PILAS desde la fila 15: ripio dispuesto en pilas de lixiviación (AG mes y año, AH toneladas, AI ley %).
El ripio ya está en pilas: no cuenta como mineral disponible, pero aporta cobre a la producción (recuperación)."""
import re
from openpyxl.utils.datetime import from_excel
from .comun import libro, hoja, filas, fecha, num, txt, minimo

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def mes_anio(v):
    """Mes y año como 'AAAA-MM'. Acepta fecha, número de fecha de Excel o texto ('ENERO 2026', 'ene-26', '01/2026')."""
    f = fecha(v)
    if f: return f[:7]
    x = num(v)
    if x is not None and 30000 < x < 80000:
        return fecha(from_excel(x))[:7]
    t = txt(v).replace("SETIEMBRE", "SEPTIEMBRE")
    if not t: return None
    m = re.fullmatch(r"(\d{4})[-/. ](\d{1,2})", t)
    if m: a, n = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{1,2})[-/. ](\d{2}|\d{4})", t) or re.fullmatch(r"([A-ZÁÉÍÓÚ]+)[-/. ]*(?:DE[ ]+|DEL[ ]+)?(\d{2}|\d{4})", t)
        if not m: return None
        n = int(m.group(1)) if m.group(1).isdigit() else (MESES.index(m.group(1)[:3]) + 1 if m.group(1)[:3] in MESES else 0)
        a = int(m.group(2)); a += 2000 if a < 100 else 0
    return f"{a:04d}-{n:02d}" if 1 <= n <= 12 and 2000 <= a <= 2100 else None


def leer(contenido):
    wb = libro(contenido)
    minas, idx, lotes, pilas = [], {}, [], []
    for _, r in filas(hoja(wb, "BD"), 3, 20):
        fch, peso = fecha(r[1]), num(r[2])
        if fch is None or peso is None or r[0] is None: continue
        try: lote = int(r[0])
        except (TypeError, ValueError): lote = str(r[0]).strip()   # ej. "RECHAZO 16"
        mina = txt(r[3]) or "SIN MINA"
        if mina not in idx: idx[mina] = len(minas); minas.append(mina)
        ley, cons = num(r[8]) or 0, num(r[9]) or 0
        fch_ch = fecha(r[12])
        est = 1 if fch_ch else (2 if ley > 0 else 0)   # 1 chancado, 2 stock pile, 0 disponible
        lotes.append([lote, fch, round(peso, 2), idx[mina], ley, cons, est])
        if fch_ch:
            valor = num(r[17])
            pilas.append([lote, fch_ch, txt(r[13]) or "SIN PILA", idx[mina], round(peso, 2), ley, cons, round(valor) if valor else 0])
    minimo(len(lotes), 50, "lotes de mineral")
    tarifas, ripio = [], {}
    if "INFORME DE PILAS" in wb.sheetnames:
        for _, r in filas(wb["INFORME DE PILAS"], 33, 35, desde_fila=15):
            m, t, ley = mes_anio(r[0]), num(r[1]), num(r[2])
            if m is None or not t: continue
            o = ripio.setdefault(m, [0.0, 0.0])   # toneladas y cobre fino, para la ley ponderada si un mes se repite
            o[0] += t; o[1] += t * (ley or 0)
        for _, r in filas(wb["INFORME DE PILAS"], 24, 30, desde_fila=14):
            f = fecha(r[0])
            if f is None or num(r[4]) is None: continue
            tarifas.append([f[:7], num(r[4]), num(r[5]) or 0, num(r[6]) or 0])
    lotes.sort(key=lambda x: (x[1], str(x[0])))
    pilas.sort(key=lambda x: (x[1], x[2], str(x[0])))
    return {"actualizado": max(l[1] for l in lotes), "minas": minas, "lotes": lotes, "pilas": pilas, "tarifas": sorted(tarifas),
            "ripio": [[m, round(o[0], 2), round(o[1] / o[0], 4)] for m, o in sorted(ripio.items())]}
