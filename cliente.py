# infoDesk — Cliente de escritorio para Windows
# Conecta al servidor Reverb (protocolo Pusher) y muestra notificaciones emergentes.

import configparser
import json
import logging
import os
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import requests
import websocket

# Importaciones con manejo de error para compatibilidad con PyInstaller
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_DISPONIBLE = True
except ImportError:
    TRAY_DISPONIBLE = False

# ─── Valores compilados dentro del exe (no visibles en config.ini) ─────────────
_API_TOKEN        = 'jTUVBzOdG8wrQKWOyHwR3pPsaBVjQmY2xf1EKV6Iuv1vjKHsgAKVYBmZeO8BlJPI'
_SERVIDOR_APP_KEY = 'iKW9AMGcfqiXRIOp5S5jkICZZEOTTwcDEGSq1OX9XqByciFK1JODFBICAQpjocbr'
_SERVIDOR_PORT   = '8080'
_SERVIDOR_SCHEME = 'ws'
_API_PORT        = '8000'

# ─── Rutas ─────────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_PATH  = BASE_DIR / 'config.ini'
LOG_PATH     = BASE_DIR / 'mensadesk.log'
BANDEJA_PATH = BASE_DIR / 'bandeja.json'

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('mensadesk')

# ─── Leer configuración ────────────────────────────────────────────────────────
config = configparser.ConfigParser()
if CONFIG_PATH.exists():
    config.read(str(CONFIG_PATH), encoding='utf-8-sig')
if not config.sections() and getattr(sys, 'frozen', False):
    _bundle_cfg = Path(sys._MEIPASS) / 'config.ini'
    if _bundle_cfg.exists():
        config.read(str(_bundle_cfg), encoding='utf-8')

SERVIDOR_HOST  = config.get('servidor', 'host',        fallback='').strip()
API_PORT       = config.get('servidor', 'api_port',    fallback=_API_PORT).strip()
REVERB_PORT    = config.get('servidor', 'reverb_port', fallback=_SERVIDOR_PORT).strip()

def _construir_api_url(host: str, port: str) -> str:
    if port == '443':
        return f'https://{host}'
    if port == '80':
        return f'http://{host}'
    return f'http://{host}:{port}'

API_URL = _construir_api_url(SERVIDOR_HOST, API_PORT)


def _leer_campo_pc(path: Path, campo: str) -> str:
    """Lee un campo de la sección [pc] del config.ini."""
    try:
        texto  = path.read_text(encoding='utf-8-sig')
        en_pc  = False
        for linea in texto.splitlines():
            l = linea.strip()
            if l.lower() == '[pc]':
                en_pc = True
                continue
            if en_pc:
                if l.startswith('['): break
                if l.startswith(';') or l.startswith('#') or not l: continue
                if '=' in l:
                    clave, _, valor = l.partition('=')
                    if clave.strip().lower() == campo:
                        return valor.strip()
    except Exception:
        pass
    return ''


PC_NOMBRE = _leer_campo_pc(CONFIG_PATH, 'nombre')
if not PC_NOMBRE and getattr(sys, 'frozen', False):
    PC_NOMBRE = _leer_campo_pc(Path(sys._MEIPASS) / 'config.ini', 'nombre')
if not PC_NOMBRE:
    PC_NOMBRE = socket.gethostname()

WS_URL = f"{_SERVIDOR_SCHEME}://{SERVIDOR_HOST}:{REVERB_PORT}/app/{_SERVIDOR_APP_KEY}"

# ─── Estado global ─────────────────────────────────────────────────────────────
_ultimo_mensaje  = None
_cola_mensajes   = []
_cola_lock       = threading.Lock()
_ws_conn         = None
_tray_icon       = None
_app_corriendo   = True

VERSION_ACTUAL = '1.0.0'

log.info(f"infoDesk iniciado | PC: {PC_NOMBRE} | WS: {WS_URL} | v{VERSION_ACTUAL}")


# ─── Setup de primer arranque ──────────────────────────────────────────────────
def _necesita_configuracion() -> bool:
    """Solo en .exe: retorna True si host sigue siendo localhost."""
    if not getattr(sys, 'frozen', False):
        return False
    return SERVIDOR_HOST in ('localhost', '127.0.0.1', '')


def _mostrar_setup_inicial():
    """Ventana de configuración inicial — se muestra una sola vez."""
    global SERVIDOR_HOST, API_URL, PC_NOMBRE, WS_URL

    root_setup = tk.Tk()
    root_setup.title('infoDesk — Configuración inicial')
    root_setup.geometry('560x420')
    root_setup.resizable(False, False)
    root_setup.configure(bg='#FFFFFF')
    root_setup.update_idletasks()
    sw = root_setup.winfo_screenwidth()
    sh = root_setup.winfo_screenheight()
    root_setup.geometry(f'560x420+{(sw-560)//2}+{(sh-420)//2}')
    root_setup.attributes('-topmost', True)
    root_setup.protocol('WM_DELETE_WINDOW', lambda: None)  # No se puede cerrar sin guardar

    # Header
    header = tk.Frame(root_setup, bg='#1D6A3A', height=64)
    header.pack(fill='x')
    header.pack_propagate(False)
    tk.Label(header, text='⚙  Configuración inicial — infoDesk',
             bg='#1D6A3A', fg='white',
             font=('Segoe UI', 11, 'bold')).pack(side='left', padx=18, pady=18)

    # Formulario
    form = tk.Frame(root_setup, bg='#FFFFFF', padx=28, pady=18)
    form.pack(fill='both', expand=True)

    def fila(row, etiqueta, placeholder=''):
        tk.Label(form, text=etiqueta, bg='#FFFFFF',
                 font=('Segoe UI', 10), anchor='w').grid(row=row, column=0, sticky='w', pady=8)
        var   = tk.StringVar()
        entry = tk.Entry(form, textvariable=var, font=('Segoe UI', 10),
                         width=26, relief='solid', bd=1)
        entry.grid(row=row, column=1, padx=12, pady=8)
        if placeholder:
            entry.insert(0, placeholder)
            entry.config(fg='#999')
            entry.bind('<FocusIn>',  lambda e: (entry.delete(0, 'end'), entry.config(fg='#000'))
                       if entry.get() == placeholder else None)
        return var, entry

    ip_var,      ip_entry      = fila(0, 'IP o dominio de infoAdmin:')
    puerto_var,  puerto_entry  = fila(1, 'Puerto de infoAdmin:', _API_PORT)
    reverb_var,  reverb_entry  = fila(2, 'Puerto de Reverb:',   _SERVIDOR_PORT)
    nombre_var,  nombre_entry  = fila(3, 'Nombre de esta PC:',  socket.gethostname())
    ip_entry.focus()

    tk.Label(form, text='Dejá el nombre en blanco para usar el nombre del equipo.',
             bg='#FFFFFF', fg='#94A3B8',
             font=('Segoe UI', 8)).grid(row=4, column=1, sticky='w', padx=12)

    err_lbl = tk.Label(form, text='', bg='#FFFFFF', fg='#B71C1C',
                       font=('Segoe UI', 9))
    err_lbl.grid(row=5, column=0, columnspan=2, pady=4)

    def guardar():
        global SERVIDOR_HOST, API_PORT, REVERB_PORT, API_URL, PC_NOMBRE, WS_URL

        ip     = ip_var.get().strip()
        puerto = puerto_var.get().strip() or _API_PORT
        reverb = reverb_var.get().strip() or _SERVIDOR_PORT
        nombre = nombre_var.get().strip()
        if nombre == socket.gethostname() and nombre_entry.cget('fg') == '#999':
            nombre = ''

        if not ip:
            err_lbl.config(text='La IP del servidor es obligatoria.')
            return

        if not config.has_section('servidor'):
            config.add_section('servidor')
        if not config.has_section('pc'):
            config.add_section('pc')

        config.set('servidor', 'host',        ip)
        config.set('servidor', 'api_port',    puerto)
        config.set('servidor', 'reverb_port', reverb)
        config.set('pc',       'nombre',      nombre)

        with open(str(CONFIG_PATH), 'w', encoding='utf-8') as f:
            config.write(f)

        SERVIDOR_HOST = ip
        API_PORT      = puerto
        REVERB_PORT   = reverb
        API_URL       = _construir_api_url(ip, puerto)
        PC_NOMBRE     = nombre or socket.gethostname()
        WS_URL        = f"{_SERVIDOR_SCHEME}://{ip}:{reverb}/app/{_SERVIDOR_APP_KEY}"

        log.info(f"Configuración guardada: host={ip}, api={puerto}, reverb={reverb}, pc={PC_NOMBRE}")
        root_setup.destroy()

    # Botón
    btn_frame = tk.Frame(root_setup, bg='#F0F4F8', pady=12)
    btn_frame.pack(fill='x', side='bottom')
    tk.Button(btn_frame, text='  Guardar y continuar  ',
              bg='#1D6A3A', fg='white', font=('Segoe UI', 10, 'bold'),
              relief='flat', cursor='hand2', padx=20, pady=8,
              command=guardar).pack()

    root_setup.mainloop()


# ─── Headers API ───────────────────────────────────────────────────────────────
def _api_headers() -> dict:
    return {'Content-Type': 'application/json', 'X-Api-Token': _API_TOKEN}


# ─── Registro en el servidor ───────────────────────────────────────────────────
def registrar_pc():
    try:
        ip = socket.gethostbyname(socket.gethostname())
        requests.post(
            f"{API_URL}/api/registro",
            json={'nombre': PC_NOMBRE, 'ip': ip,
                  'grupo': _leer_campo_pc(CONFIG_PATH, 'grupo')},
            headers=_api_headers(),
            timeout=5,
        )
        log.info(f"Registrado en servidor: {PC_NOMBRE} ({ip})")
    except Exception as e:
        log.warning(f"Error al registrar PC: {e}")


def heartbeat_loop():
    while _app_corriendo:
        registrar_pc()
        time.sleep(30)


# ─── Confirmación de lectura ───────────────────────────────────────────────────
def enviar_confirmacion(mensaje_id: int, accion: str):
    try:
        ip = socket.gethostbyname(socket.gethostname())
        requests.post(
            f"{API_URL}/api/confirmacion",
            json={'mensaje_id': mensaje_id, 'pc_nombre': PC_NOMBRE,
                  'pc_ip': ip, 'accion': accion},
            headers=_api_headers(),
            timeout=5,
        )
        log.info(f"Confirmación enviada: mensaje #{mensaje_id} — {accion}")
    except Exception as e:
        log.warning(f"Error al enviar confirmación: {e}")


# ─── WebSocket Pusher Protocol ─────────────────────────────────────────────────
def on_open(ws):
    log.info("WebSocket conectado")


def on_message(ws, message):
    global _ultimo_mensaje
    try:
        payload = json.loads(message)
        evento  = payload.get('event', '')

        if evento == 'pusher:connection_established':
            ws.send(json.dumps({'event': 'pusher:subscribe',
                                'data':  {'channel': 'mensajes'}}))
            log.info("Suscrito al canal 'mensajes'")
            registrar_pc()

        elif evento == 'pusher:ping':
            ws.send(json.dumps({'event': 'pusher:pong', 'data': {}}))

        elif evento == 'mensaje.enviado':
            raw   = payload.get('data', '{}')
            datos = json.loads(raw) if isinstance(raw, str) else raw

            # Filtrar por grupo destino
            grupo_destino = datos.get('grupo_destino')
            if grupo_destino:
                pc_grupo = _leer_campo_pc(CONFIG_PATH, 'grupo')
                if pc_grupo != grupo_destino:
                    log.info(f"Mensaje ignorado (grupo {grupo_destino}, esta PC: '{pc_grupo}')")
                    return

            log.info(f"Mensaje recibido: {datos.get('titulo', '')}")
            _ultimo_mensaje = datos
            mostrar_notificacion_thread(datos)

    except Exception as e:
        log.error(f"Error al procesar mensaje: {e}")


def on_error(ws, error):
    log.error(f"WebSocket error: {error}")


def on_close(ws, code, msg):
    log.info(f"WebSocket desconectado (código {code})")


def iniciar_websocket():
    global _ws_conn, _app_corriendo
    while _app_corriendo:
        try:
            log.info(f"Conectando a {WS_URL}...")
            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            _ws_conn = ws
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            log.error(f"Error al conectar WebSocket: {e}")
        if _app_corriendo:
            log.info("Reintentando conexión en 10 segundos...")
            time.sleep(10)


# ─── Notificaciones ────────────────────────────────────────────────────────────
def guardar_en_bandeja(datos: dict):
    try:
        import datetime, json as _json
        bandeja = []
        if BANDEJA_PATH.exists():
            try:
                bandeja = _json.loads(BANDEJA_PATH.read_text(encoding='utf-8'))
            except Exception:
                bandeja = []
        entrada = dict(datos)
        entrada['_fecha_local'] = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        entrada.setdefault('_leido', False)
        bandeja.insert(0, entrada)
        bandeja = bandeja[:100]
        BANDEJA_PATH.write_text(
            _json.dumps(bandeja, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    except Exception as e:
        log.warning(f"Error guardando en bandeja: {e}")


def mostrar_notificacion_thread(datos: dict):
    guardar_en_bandeja(datos)
    with _cola_lock:
        _cola_mensajes.append(datos)


_cola_bandeja      = []
_cola_bandeja_lock = threading.Lock()


def mostrar_ultimo_mensaje():
    if _ultimo_mensaje:
        with _cola_lock:
            _cola_mensajes.append(_ultimo_mensaje)


def abrir_bandeja():
    with _cola_bandeja_lock:
        _cola_bandeja.append(True)


# ─── Tray ──────────────────────────────────────────────────────────────────────
def crear_icono_imagen():
    img = Image.new('RGBA', (64, 64), color=(29, 106, 58, 255))
    d   = ImageDraw.Draw(img)
    d.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 200))
    return img


def salir_app(icon, item=None):
    global _app_corriendo
    _app_corriendo = False
    if _ws_conn:
        try: _ws_conn.close()
        except Exception: pass
    if icon:
        icon.stop()
    os._exit(0)


def _get_resource_path(filename: str) -> Path:
    externo = BASE_DIR / filename
    if externo.exists():
        return externo
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / filename
    return BASE_DIR / filename


def iniciar_tray():
    global _tray_icon
    if not TRAY_DISPONIBLE:
        log.warning("pystray/PIL no disponible — icono de bandeja desactivado")
        return
    try:
        ico_path = _get_resource_path('icono.ico')
        img = Image.open(str(ico_path)).convert('RGBA') if ico_path.exists() else crear_icono_imagen()
        menu = pystray.Menu(
            pystray.MenuItem('Ver último mensaje',  lambda icon, item: mostrar_ultimo_mensaje()),
            pystray.MenuItem('Bandeja de mensajes', lambda icon, item: abrir_bandeja()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Salir', salir_app),
        )
        _tray_icon = pystray.Icon('infoDesk', img, 'infoDesk', menu)
        _tray_icon.run()
    except Exception as e:
        log.error(f"Error en tray: {e}")


# ─── Auto-update ───────────────────────────────────────────────────────────────
def verificar_actualizacion():
    if not getattr(sys, 'frozen', False):
        return
    try:
        r = requests.get(f"{API_URL}/api/version", timeout=10)
        if r.status_code != 200:
            return
        data             = r.json()
        version_servidor = data.get('version', '0.0.0')
        if version_servidor <= VERSION_ACTUAL:
            return

        log.info(f"Nueva versión disponible: {version_servidor} (actual: {VERSION_ACTUAL})")
        url_descarga = data.get('url')
        if not url_descarga:
            return

        exe_actual = Path(sys.executable)
        exe_nuevo  = exe_actual.parent / 'infoDesk_nuevo.exe'
        bat_update = exe_actual.parent / '_update.bat'

        r2 = requests.get(url_descarga, timeout=120, stream=True)
        r2.raise_for_status()
        with open(exe_nuevo, 'wb') as f:
            for chunk in r2.iter_content(chunk_size=8192):
                f.write(chunk)

        bat_update.write_text(
            f'@echo off\ntimeout /t 2 /nobreak >nul\n'
            f'move /Y "{exe_nuevo}" "{exe_actual}"\n'
            f'start "" "{exe_actual}"\ndel "%~f0"\n'
        )
        import subprocess
        subprocess.Popen(['cmd', '/c', str(bat_update)],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(1)
        os._exit(0)
    except Exception as e:
        log.warning(f"Error al verificar actualización: {e}")


# ─── Inicio automático con Windows ────────────────────────────────────────────
def registrar_inicio_windows():
    if not getattr(sys, 'frozen', False):
        return
    try:
        import winreg
        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(clave, 'infoDesk', 0, winreg.REG_SZ, sys.executable)
        winreg.CloseKey(clave)
        log.info("Registrado en inicio automático de Windows")
    except Exception as e:
        log.warning(f"No se pudo registrar en inicio automático: {e}")


# ─── Punto de entrada ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    registrar_inicio_windows()

    # Primer arranque: pedir IP del servidor si sigue en localhost
    if _necesita_configuracion():
        _mostrar_setup_inicial()

    hilo_update = threading.Thread(target=verificar_actualizacion, daemon=True)
    hilo_update.start()

    hilo_ws = threading.Thread(target=iniciar_websocket, daemon=True)
    hilo_ws.start()

    hilo_hb = threading.Thread(target=heartbeat_loop, daemon=True)
    hilo_hb.start()

    from ventana import iniciar_ventana_loop
    iniciar_ventana_loop(
        cola_mensajes=_cola_mensajes,
        cola_lock=_cola_lock,
        cola_bandeja=_cola_bandeja,
        cola_bandeja_lock=_cola_bandeja_lock,
        bandeja_path=BANDEJA_PATH,
        pc_nombre=PC_NOMBRE,
        api_url=API_URL,
        enviar_confirmacion_fn=enviar_confirmacion,
        tray_fn=iniciar_tray,
    )
