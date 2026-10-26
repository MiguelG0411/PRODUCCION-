"""Ácido.
CONTROL-DE-ACIDO-2024.xlsm, hoja BDR: C fecha, E-I nivel de los estanques TK1..TK5.
CONTROL-ACIDO-HEXAGON-2026.xlsm, hoja BDR: encabezados en la fila 5; C fecha de llegada, F toneladas.

Toneladas de cada estanque = nivel x 11,2. Excepción: TK3 desde el 27-02-2026 = nivel x 20.
Consumo del día = ácido total de ayer + toneladas llegadas ese día - ácido total de hoy."""
from .comun import libro, hoja, filas, fecha, num, minimo

CAMBIO_TK3 = "2026-02-26"
MAX_LECTURA = 3.5   # una lectura mayor se interpreta como coma olvidada (ej. 70 -> 0,70)


def factor(tk, fecha):
    """Ecuación nivel -> toneladas de cada estanque. Es la única copia: la app recibe las toneladas ya calculadas."""
    return 20.0 if (tk == 3 and fecha > CAMBIO_TK3) else 11.2


def leer_niveles(contenido):
    lect, comas = {}, []
    for i, r in filas(hoja(libro(contenido), "BDR"), 3, 9):
        f = fecha(r[0])
        if f is None or f in lect: continue   # las lecturas nuevas van arriba: si una fecha se repite vale la de más arriba
        t = []
        for j, v in enumerate(r[2:7]):
            x = num(v)
            if x is not None and x > MAX_LECTURA:
                comas.append([i, j + 1, x]); x = round(x / 100, 3)
            t.append(x)
        if all(x is None for x in t): continue
        lect[f] = t
    minimo(len(lect), 20, "lecturas de estanques")
    return {"lecturas": sorted(lect.items()), "comas": comas}


def leer_llegadas(contenido):
    ll = []
    for _, r in filas(hoja(libro(contenido), "BDR"), 3, 6, desde_fila=6):
        f, t = fecha(r[0]), num(r[3])
        if f is None or t is None: continue
        ll.append([f, round(t, 3)])
    minimo(len(ll), 1, "llegadas de ácido")
    ll.sort(key=lambda x: x[0])   # las llegadas nuevas se anotan arriba
    return ll


def combinar(niveles, llegadas):
    """Une las lecturas de los estanques con las llegadas.
    Cada día: [fecha, consumo, baja de cada TK, toneladas llegadas, toneladas en cada TK, ácido total]."""
    llegadas = llegadas or []
    dias, faltan = [], []
    ult, k = [None] * 5, 0
    # llegadas anteriores a la primera lectura no se pueden asociar a un consumo
    while niveles and k < len(llegadas) and llegadas[k][0] <= niveles["lecturas"][0][0]:
        k += 1
    for n, (f, t) in enumerate(niveles["lecturas"] if niveles else []):
        ant = list(ult)
        for j in range(5):
            if t[j] is None:
                if ult[j] is not None: faltan.append([f, j + 1])   # sin lectura: se usa la última conocida
            else:
                ult[j] = t[j]
        fac = [factor(j + 1, f) for j in range(5)]
        nivel = [round(ult[j] * fac[j], 2) if ult[j] is not None else None for j in range(5)]
        total = round(sum(x or 0 for x in nivel), 2)
        lleg = 0.0
        if n == 0:
            lleg = sum(x[1] for x in llegadas if x[0] == f)
        else:
            while k < len(llegadas) and llegadas[k][0] <= f:   # llegadas entre la lectura anterior y esta
                lleg += llegadas[k][1]; k += 1
        # La diferencia de cada TK se calcula con el factor del día, así el cambio de fórmula del TK3
        # no aparece como consumo. Los traspasos entre estanques se anulan en la suma.
        dif = [(ant[j] - ult[j]) * fac[j] if (n and ant[j] is not None and ult[j] is not None) else 0.0 for j in range(5)]
        cons = round(sum(dif) + lleg, 3) if n else 0.0
        dias.append([f, cons, [round(max(d, 0), 3) for d in dif], round(lleg, 3), nivel, total])
    ultima = dias[-1][0] if dias else ""
    return {
        "actualizado": ultima,
        "dias": dias,
        "llegadas": llegadas,
        "factores": [factor(j + 1, ultima) for j in range(5)],
        "avisos": {"comas": niveles["comas"] if niveles else [], "faltan": faltan},
    }
