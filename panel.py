"""Panel de gestión (CMR) de Minera Anita: ingreso con Google y rutas protegidas.

Seguridad:
- Solo entran las cuentas de Google listadas en la variable PANEL_USUARIOS (los correos nunca van al repositorio).
- Google firma un "token" con el correo; el servidor verifica la firma, el destinatario (GOOGLE_CLIENT_ID),
  la vigencia, que el correo esté verificado y un número de un solo uso (nonce) contra repeticiones.
- La sesión es una cookie firmada (SECRET_KEY), solo HTTP, segura en Render, que vence tras PANEL_MINUTOS
  sin uso (30 por omisión) y como máximo a las 12 horas.
- Si un correo se quita de PANEL_USUARIOS, esa persona pierde el acceso en su siguiente clic.
- Muchos intentos fallidos desde una misma dirección se bloquean por 10 minutos.
- Cada ingreso, salida, sesión vencida e intento rechazado queda en el registro de accesos.

Variables de entorno:
    GOOGLE_CLIENT_ID   identificador del cliente OAuth de Google (no es secreto)
    SECRET_KEY         clave larga al azar para firmar las sesiones
    PANEL_USUARIOS     correo|Nombre|rol separados por ";"   (rol: admin o usuario)
    PANEL_MINUTOS      minutos sin uso antes de cerrar la sesión (opcional, 30)
    PROTEGER_APP       1 = la app antigua (/) también exige ingresar al panel (opcional)
"""
import collections, datetime, functools, logging, os, secrets, threading, time

from flask import Blueprint, Response, abort, jsonify, redirect, request, send_from_directory, session

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(RAIZ, "panel_web")
EN_RENDER = bool(os.environ.get("RENDER"))
MAX_HORAS = 12
log = logging.getLogger("produccion")

bp = Blueprint("panel", __name__)
_accesos = collections.deque(maxlen=500)
_fallos = collections.defaultdict(list)
_lock = threading.Lock()


def minutos():
    try:
        return max(5, min(240, int(os.environ.get("PANEL_MINUTOS", "30"))))
    except ValueError:
        return 30


def usuarios():
    """{correo: {"nombre":..., "rol":...}} desde PANEL_USUARIOS."""
    out = {}
    for item in os.environ.get("PANEL_USUARIOS", "").replace("\n", ";").split(";"):
        partes = [p.strip() for p in item.split("|")]
        if not partes or "@" not in partes[0]:
            continue
        correo = partes[0].lower()
        nombre = partes[1] if len(partes) > 1 and partes[1] else correo.split("@")[0]
        rol = "admin" if len(partes) > 2 and partes[2].lower().startswith("admin") else "usuario"
        out[correo] = {"nombre": nombre, "rol": rol}
    return out


def _ip():
    return request.remote_addr or "?"


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def registrar(evento, correo="", nombre="", detalle=""):
    e = {"hora": _ahora(), "evento": evento, "correo": correo, "nombre": nombre, "ip": _ip(), "detalle": detalle}
    with _lock:
        _accesos.appendleft(e)
    log.info("PANEL %s %s %s %s", evento, correo or "-", e["ip"], detalle)


def _bloqueado():
    t = time.time()
    with _lock:
        f = _fallos[_ip()] = [x for x in _fallos[_ip()] if t - x < 600]
        return len(f) >= 10


def _fallo():
    with _lock:
        _fallos[_ip()].append(time.time())


def usuario_actual():
    """Devuelve el usuario de la sesión vigente o None (y limpia la sesión vencida o revocada)."""
    correo = session.get("correo")
    if not correo:
        return None
    t = time.time()
    u = usuarios().get(correo)
    vencida = t - session.get("ultimo", 0) > minutos() * 60 or t - session.get("inicio", 0) > MAX_HORAS * 3600
    if not u or vencida:
        registrar("sesión vencida" if u else "acceso revocado", correo, session.get("nombre", ""))
        session.clear()
        return None
    if t - session.get("ultimo", 0) > 30:   # no reescribir la cookie en cada pedido
        session["ultimo"] = int(t)
    return {"correo": correo, "nombre": u["nombre"], "rol": u["rol"]}


def requiere_sesion(api=True):
    def deco(fn):
        @functools.wraps(fn)
        def envoltura(*a, **k):
            if not usuario_actual():
                if api:
                    return jsonify({"error": "sesion"}), 401
                return redirect("/panel")
            return fn(*a, **k)
        return envoltura
    return deco


def _mismo_origen():
    """Los POST solo se aceptan desde el propio sitio (protección contra pedidos falsificados)."""
    o = request.headers.get("Origin") or request.headers.get("Referer") or ""
    return o.startswith(request.host_url.rstrip("/")) or o.startswith(request.host_url.replace("http://", "https://").rstrip("/"))


def _html(nombre, csp, extra=None):
    with open(os.path.join(DIR, nombre), encoding="utf-8") as fh:
        html = fh.read()
    nonce = secrets.token_urlsafe(16)
    for k, v in {"NONCE": nonce, **(extra or {})}.items():
        html = html.replace("{{" + k + "}}", v)
    r = Response(html, mimetype="text/html")
    r.headers["Content-Security-Policy"] = csp.replace("{n}", nonce)
    r.headers["Cache-Control"] = "no-store"
    return r


GSI = "https://accounts.google.com/gsi/"
CSP_BASE = ("default-src 'self'; base-uri 'none'; object-src 'none'; form-action 'self'; frame-ancestors 'none'; "
            "img-src 'self' data: https://*.googleusercontent.com; font-src https://fonts.gstatic.com; ")


@bp.after_app_request
def cabeceras(r):
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if EN_RENDER:
        r.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.path.startswith("/panel"):
        r.headers.setdefault("Cache-Control", "no-store")
    return r


@bp.get("/panel")
def panel():
    u = usuario_actual()
    if u:
        return _html("panel.html", CSP_BASE + "script-src 'self' 'nonce-{n}'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                     "connect-src 'self'; frame-src 'self'")
    session["nonce"] = secrets.token_urlsafe(24)
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    dev = "" if EN_RENDER or not os.environ.get("PANEL_DEV_CORREO") else "1"
    r = _html("ingreso.html", CSP_BASE + f"script-src 'self' 'nonce-{{n}}' {GSI}client; style-src 'self' 'unsafe-inline' {GSI}style "
              f"https://fonts.googleapis.com; connect-src 'self' {GSI}; frame-src {GSI}",
              {"CLIENT_ID": cid, "GNONCE": session["nonce"], "DEV": dev})
    r.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return r


@bp.post("/panel/ingresar")
def ingresar():
    if not _mismo_origen() or not request.is_json:
        abort(403)
    if _bloqueado():
        registrar("bloqueado", detalle="demasiados intentos")
        return jsonify({"error": "Demasiados intentos. Espera 10 minutos."}), 429
    datos = request.get_json(silent=True) or {}
    nonce = session.pop("nonce", None)
    correo, nombre_g = None, ""
    if datos.get("dev") and not EN_RENDER and os.environ.get("PANEL_DEV_CORREO"):
        correo = os.environ["PANEL_DEV_CORREO"].lower()   # solo para pruebas en el computador, nunca en Render
    else:
        cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        if not cid:
            return jsonify({"error": "Falta configurar GOOGLE_CLIENT_ID en el servidor."}), 500
        try:
            from google.auth.transport import requests as greq
            from google.oauth2 import id_token
            info = id_token.verify_oauth2_token(str(datos.get("credential", "")), greq.Request(), cid)
        except Exception as e:
            _fallo(); registrar("rechazado", detalle="token inválido: " + type(e).__name__)
            return jsonify({"error": "No se pudo validar la cuenta de Google."}), 401
        if not nonce or info.get("nonce") != nonce:
            _fallo(); registrar("rechazado", info.get("email", ""), detalle="nonce")
            return jsonify({"error": "La página de ingreso venció. Recarga e intenta de nuevo."}), 401
        if not info.get("email_verified"):
            _fallo(); registrar("rechazado", info.get("email", ""), detalle="correo no verificado")
            return jsonify({"error": "La cuenta de Google no tiene el correo verificado."}), 403
        correo, nombre_g = info["email"].lower(), info.get("name", "")
    u = usuarios().get(correo)
    if not u:
        _fallo(); registrar("rechazado", correo, nombre_g, "cuenta no autorizada")
        return jsonify({"error": "Esta cuenta no está autorizada para entrar al panel."}), 403
    session.clear()
    session.permanent = True
    t = int(time.time())
    session.update(correo=correo, nombre=u["nombre"], inicio=t, ultimo=t)
    registrar("ingreso", correo, u["nombre"])
    return jsonify({"ok": True})


@bp.post("/panel/salir")
def salir():
    if not _mismo_origen():
        abort(403)
    if session.get("correo"):
        registrar("salida", session["correo"], session.get("nombre", ""))
    session.clear()
    return jsonify({"ok": True})


@bp.get("/panel/api/yo")
@requiere_sesion()
def yo():
    u = usuario_actual()
    return jsonify({**u, "minutos": minutos(), "vence": session.get("ultimo", 0) + minutos() * 60})


@bp.get("/panel/api/accesos")
@requiere_sesion()
def accesos():
    u = usuario_actual()
    if u["rol"] != "admin":
        abort(403)
    with _lock:
        lista = list(_accesos)
    return jsonify({"usuarios": [{"correo": c, **v} for c, v in usuarios().items()], "accesos": lista, "minutos": minutos()})


@bp.get("/panel/<path:ruta>")
@requiere_sesion(api=False)
def archivos(ruta):
    if ruta in ("panel.js", "panel.css") or (ruta.startswith("img/") and ruta.endswith((".png", ".svg"))):
        return send_from_directory(DIR, ruta)
    abort(404)


def registrar_app(app, api_datos, api_estado, api_actualizar, inicio):
    """Publica la app de producción dentro del panel (/panel/app/) protegida por la sesión."""
    @app.get("/panel/app/")
    @requiere_sesion(api=False)
    def p_app():
        return inicio()

    @app.get("/panel/app/<path:ruta>")
    def p_app_archivos(ruta):
        if not usuario_actual():
            return (jsonify({"error": "sesion"}), 401) if ruta.startswith("api/") else redirect("/panel")
        if ruta == "api/datos":
            return api_datos()
        if ruta == "api/estado":
            return api_estado()
        if ruta.startswith("icons/") and ruta.endswith(".png"):
            return send_from_directory(RAIZ, ruta)
        abort(404)

    @app.post("/panel/app/api/actualizar")
    @requiere_sesion()
    def p_app_actualizar():
        if not _mismo_origen():
            abort(403)
        return api_actualizar()

    if os.environ.get("PROTEGER_APP") == "1":
        @app.before_request
        def _proteger():
            p = request.path
            if p == "/" or p.startswith("/api/") or p == "/index.html":
                if not usuario_actual():
                    return (jsonify({"error": "sesion"}), 401) if p.startswith("/api/") else redirect("/panel")


def configurar(app):
    clave = os.environ.get("SECRET_KEY", "")
    if len(clave) < 32:
        log.warning("SECRET_KEY no está configurada (o es corta): se usa una clave temporal; las sesiones se cierran al reiniciar.")
        clave = secrets.token_hex(32)
    app.secret_key = clave
    app.config.update(
        SESSION_COOKIE_NAME="panel_sesion",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=EN_RENDER,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=MAX_HORAS),
    )
    from werkzeug.middleware.proxy_fix import ProxyFix
    if EN_RENDER:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.register_blueprint(bp)
