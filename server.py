"""Servidor de la app de producción.
Descarga las planillas desde los links de Dropbox (variables de entorno) una vez al iniciar y después
solo cuando el usuario presiona "Actualizar". Los datos quedan en memoria: no se escriben archivos.
Si una planilla falla se mantienen sus datos anteriores y se informa el error en /api/estado.

Ejecutar con un solo proceso para que todos vean los mismos datos:
    gunicorn server:app --workers 1 --threads 8 --timeout 120"""
import datetime, gzip, json, logging, os, threading, time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, Response, abort, jsonify, request, send_from_directory

from planillas import acido, calidad, mineral, petroleo, recuperacion
from planillas.comun import ErrorPlanilla, descargar

RAIZ = os.path.dirname(os.path.abspath(__file__))
ESPERA_MIN = 20   # segundos mínimos entre dos actualizaciones

# clave: (variable de entorno, nombre que ve el usuario, lector)
FUENTES = {
    "recuperacion": ("DROPBOX_URL_RECUPERACION", "Recuperación", recuperacion.leer),
    "acido": ("DROPBOX_URL_ACIDO", "Control de ácido", acido.leer_niveles),
    "cargasAcido": ("DROPBOX_URL_CARGASACIDO", "Llegadas de ácido", acido.leer_llegadas),
    "petroleo": ("DROPBOX_URL_PETROLEO", "Entrega de petróleo", petroleo.leer),
    "mineral": ("DROPBOX_URL_MINERAL", "Ingreso de mineral", mineral.leer),
    "calidad": ("DROPBOX_URL_CALIDAD", "Control de calidad", calidad.leer),
}

log = logging.getLogger("produccion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

with open(os.path.join(RAIZ, "historico_produccion.json"), encoding="utf-8") as fh:
    HISTORICO = json.load(fh)

_lock = threading.Lock()
_lock_lectura = threading.Lock()
_crudo = {}                                     # lo último leído bien de cada planilla
_fuentes = {k: {"nombre": v[1], "ok": None, "error": None, "hora": None, "fase": None} for k, v in FUENTES.items()}
_estado = {"cargando": False, "actualizado": None, "inicio": 0.0}
_paquete = {"json": b"", "gz": b""}


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _leer_una(clave):
    env, _, lector = FUENTES[clave]
    url = os.environ.get(env, "").strip()
    if not url:
        raise ErrorPlanilla(f"Falta la variable de entorno {env}.")
    f = _fuentes[clave]
    try:
        t0 = time.time(); f["fase"] = "descargando"
        contenido = descargar(url)
        log.info("Planilla %s: descargada (%.1f MB) en %.1f s", clave, len(contenido) / 1e6, time.time() - t0)
        f["fase"] = "esperando"
        with _lock_lectura:   # se lee una planilla a la vez para no pasar el límite de memoria del servidor
            t1 = time.time(); f["fase"] = "leyendo"
            datos = lector(contenido)
        del contenido
        log.info("Planilla %s: leída en %.1f s", clave, time.time() - t1)
        return datos
    except ErrorPlanilla:
        raise
    except Exception as e:   # red, archivo dañado, etc.: el mensaje no debe incluir el link
        msg = str(e).replace(url, "<link>")
        raise ErrorPlanilla(f"No se pudo leer la planilla ({type(e).__name__}: {msg[:200]}).") from None


def _armar():
    """Arma la respuesta de /api/datos con lo último leído bien de cada planilla."""
    c = _crudo
    datos = {
        "produccion": recuperacion.combinar(c["recuperacion"], HISTORICO) if "recuperacion" in c
                      else {"kgSaco": recuperacion.KG_SACO, "actualizado": None, "dias": dict(HISTORICO)},
        "acido": acido.combinar(c["acido"], c.get("cargasAcido")) if "acido" in c else None,
        "petroleo": c.get("petroleo"),
        "mineral": c.get("mineral"),
        "calidad": c.get("calidad"),
    }
    if datos["acido"] is None and "cargasAcido" in c:
        datos["acido"] = {"actualizado": "", "dias": [], "llegadas": c["cargasAcido"], "factores": [], "avisos": {}}
    js = json.dumps(datos, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    _paquete["json"], _paquete["gz"] = js, gzip.compress(js, 6)


def _meta():
    return {"cargando": _estado["cargando"], "actualizado": _estado["actualizado"], "inicio": _estado["inicio"], "fuentes": _fuentes}


def actualizar():
    """Descarga las planillas en paralelo. Cada una que falle conserva sus datos anteriores."""
    t0 = time.time()
    for f in _fuentes.values(): f["fase"] = "esperando"
    with ThreadPoolExecutor(max_workers=len(FUENTES)) as ex:
        futuros = {k: ex.submit(_leer_una, k) for k in FUENTES}
        for k, fut in futuros.items():
            try:
                _crudo[k] = fut.result()
                _fuentes[k].update(ok=True, error=None, hora=ahora(), fase="lista")
            except Exception as e:
                _fuentes[k].update(ok=False, error=str(e), fase="error")
                log.warning("Planilla %s: %s", k, e)
    try:
        _armar()
    except Exception:
        log.exception("Error al armar los datos")
    _estado["actualizado"] = ahora()
    _estado["cargando"] = False   # recién ahora, para que la app no pida los datos antes de que estén listos
    log.info("Actualización terminada en %.1f s", time.time() - t0)


def iniciar_actualizacion():
    """Lanza la actualización en segundo plano. Devuelve False si ya hay una en curso o fue hace muy poco."""
    with _lock:
        if _estado["cargando"] or time.time() - _estado["inicio"] < ESPERA_MIN:
            return False
        _estado["cargando"], _estado["inicio"] = True, time.time()
    threading.Thread(target=actualizar, daemon=True).start()
    return True


app = Flask(__name__, static_folder=None)


@app.get("/")
def inicio():
    return send_from_directory(RAIZ, "index.html")


@app.get("/<path:ruta>")
def estaticos(ruta):
    # Solo se publican los archivos de la app (nunca el código ni otros archivos del servidor)
    if ruta in ("index.html", "sw.js", "manifest.json") or (ruta.startswith("icons/") and ruta.endswith(".png")):
        return send_from_directory(RAIZ, ruta)
    abort(404)


@app.get("/api/datos")
def api_datos():
    gz = "gzip" in request.headers.get("Accept-Encoding", "")
    r = Response(_paquete["gz"] if gz else _paquete["json"], mimetype="application/json")
    if gz: r.headers["Content-Encoding"] = "gzip"
    r.headers["Vary"] = "Accept-Encoding"
    r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/api/estado")
def api_estado():
    r = jsonify(_meta())
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/actualizar")
def api_actualizar():
    iniciar_actualizacion()
    return jsonify(_meta()), 202


_pid = None


@app.before_request
def _arrancar():
    """Descarga inicial en el proceso que atiende las visitas.
    Render lanza gunicorn con --preload: el módulo se importa en un proceso y luego se copia a otro,
    y los hilos no se copian. Por eso la descarga no parte al importar sino aquí, una vez por proceso
    (la primera visita es la revisión de salud que Render hace apenas arranca el servidor)."""
    global _pid
    if _pid == os.getpid(): return
    with _lock:
        if _pid == os.getpid(): return
        _pid = os.getpid()
        _estado.update(cargando=False, inicio=0.0)   # estado copiado de otro proceso: se reinicia
    iniciar_actualizacion()


_armar()   # deja disponible al menos el histórico mientras descarga

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
