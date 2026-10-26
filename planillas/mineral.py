"""INGRESO-MINERAL-2026.xlsm.
Hoja BD: C lote, D fecha, E peso, F mina, K ley, L consumo, O fecha de chancado, P pila de destino, T valor del lote.
Estado de cada lote: chancado si tiene fecha de chancado; stock pile si tiene ley y no está chancado; si no, disponible.
Hoja INFORME DE PILAS desde X14: tarifas ENAMI (X fecha, AB base, AC escala, AD ácido)."""
from .comun import libro, hoja, filas, fecha, num, txt, minimo


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
    tarifas = []
    if "INFORME DE PILAS" in wb.sheetnames:
        for _, r in filas(wb["INFORME DE PILAS"], 24, 30, desde_fila=14):
            f = fecha(r[0])
            if f is None or num(r[4]) is None: continue
            tarifas.append([f[:7], num(r[4]), num(r[5]) or 0, num(r[6]) or 0])
    lotes.sort(key=lambda x: (x[1], str(x[0])))
    pilas.sort(key=lambda x: (x[1], x[2], str(x[0])))
    return {"actualizado": max(l[1] for l in lotes), "minas": minas, "lotes": lotes, "pilas": pilas, "tarifas": sorted(tarifas)}
