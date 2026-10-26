"""RECUPERACION-2026.xlsm, hoja BDR: C fecha, E y F sacos, G producción del día en kilos."""
from .comun import libro, hoja, filas, fecha, num, minimo

KG_SACO = 25


def ent(v):
    x = num(v)
    return int(round(x)) if x is not None else 0


def leer(contenido):
    dias = {}
    for _, r in filas(hoja(libro(contenido), "BDR"), 3, 7):
        f = fecha(r[0])
        if f is None: continue
        kg = num(r[4]) or 0
        a = dias.get(f, [0, 0, 0])   # si un día viene repetido, se suman
        dias[f] = [a[0] + ent(r[2]), a[1] + ent(r[3]), round(a[2] + kg, 1)]
    minimo(len(dias), 10, "días de producción")
    return dias


def combinar(dias, historico):
    """Años anteriores fijos (historico_produccion.json) + lo leído de la planilla del año en curso."""
    todo = {**historico, **dias}
    return {"kgSaco": KG_SACO, "actualizado": max(dias), "dias": dict(sorted(todo.items()))}
