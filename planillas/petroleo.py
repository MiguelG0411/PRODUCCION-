"""ENTREGA-DE-PETROLEO-2026.xlsm.
Hoja BDR (despachos): C fecha, D máquina, E solicitante, F litros, G encargado, H centro de costos, K destino.
Hoja BDC (recargas del camión): C fecha, E solicitante, F litros cargados.
Destino: PLANTA = consumo interno (0), EXTERNO = prestado a proveedores (1), otro o vacío = sin destino (2)."""
from .comun import libro, hoja, filas, fecha, num, txt, minimo

DESTINOS = {"PLANTA": 0, "EXTERNO": 1}


def leer(contenido):
    wb = libro(contenido)
    bdr, bdc = hoja(wb, "BDR"), hoja(wb, "BDC")
    dic = {"maq": [], "sol": [], "cc": [], "enc": []}
    def ix(k, v):
        v = txt(v) or "SIN DATO"
        if v not in dic[k]: dic[k].append(v)
        return dic[k].index(v)
    entregas, otros = [], {}
    for i, r in filas(bdr, 3, 11):
        f, lit = fecha(r[0]), num(r[3])
        if f is None or lit is None: continue
        dest = DESTINOS.get("".join(str(r[8] or "").split()).upper(), 2)   # sin distinguir mayúsculas ni espacios
        if dest == 2: otros.setdefault(txt(r[8]) or "(vacío)", []).append(i)
        entregas.append([f, ix("maq", r[1]), ix("sol", r[2]), round(lit, 1), ix("cc", r[5]), dest, ix("enc", r[4])])
    cargas = []
    for _, r in filas(bdc, 3, 6):
        f, lit = fecha(r[0]), num(r[3])
        if f is None or lit is None: continue
        cargas.append([f, round(lit, 1), ix("sol", r[2])])
    minimo(len(entregas), 20, "despachos de petróleo")
    entregas.sort(key=lambda x: x[0]); cargas.sort(key=lambda x: x[0])
    return {"actualizado": entregas[-1][0], "entregas": entregas, "cargas": cargas,
            "sinDestino": [[k, v] for k, v in otros.items()], **dic}
