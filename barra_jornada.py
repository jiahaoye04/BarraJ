"""
Barra de jornada 2.1.0 — barra de progreso de la jornada laboral para Windows 11.

- La barra se pinta por tramos: cada franja conserva el modo (trabajo /
  descanso) en el que estabas, con su propio estilo de color.
- El descanso NO consume jornada: la duración total se amplía con cada minuto
  de descanso y la barra se recalcula continuamente.
- Progreso real (ritmo constante) o curvado (primeras horas lentas, últimas
  rápidas) con intensidad ajustable.
- Estilos de color: plano, degradado, cambiante y en movimiento, con paletas.
- Brillo en la punta: continuo, cada X píxeles o cada N minutos (fijo o al
  azar dentro de un rango), con estela tipo cometa y fundidos suaves.
- Tema claro/oscuro para la app y, por separado, para la barra.
- Visibilidad: siempre, al pasar el ratón, o al pasar el ratón + asomar cada
  N minutos.
- Avisos de hito en burbuja sobre la punta de la barra, configurables.
- Descanso automático por inactividad (opcional y con deshacer).
- Celebraciones intercambiables y opción de seguir contando horas extra.

Dependencias:
    pip install pystray pillow

Uso:
    pythonw barra_jornada.py   (o jornada.bat)
"""

import copy
import ctypes
import json
import math
import os
import random
import sys
import threading
import time
from ctypes import wintypes
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import colorchooser, filedialog

from PIL import Image, ImageDraw, ImageFont, ImageTk
import pystray

try:
    import winreg
except ImportError:          # fuera de Windows (solo para pruebas)
    winreg = None

VERSION = "2.1.0"
NOMBRE_APP = "Barra de jornada"

# --------------------------------------------------------------------------
# Valores de fábrica
# --------------------------------------------------------------------------
DURACION_POR_DEFECTO = "8:30"
COLOR_TRABAJO_DEF = "#2f81f7"       # azul
COLOR_TRABAJO2_DEF = "#a371f7"      # violeta (segundo color de degradados)
COLOR_DESCANSO_DEF = "#2ea043"      # verde
COLOR_DESCANSO2_DEF = "#56d4dd"     # turquesa
COLOR_EXTRA_DEF = "#d29922"         # ámbar para horas extra

ALTURA_DEF = 4
ALTURA_MIN, ALTURA_MAX = 2, 8

# Progreso: "real" = ritmo constante; "curva" = primeras horas lentas.
CURVAS = {"Lineal": 1.0, "Suave": 1.35, "Media": 1.7, "Fuerte": 2.3}
ORDEN_CURVAS = ["Lineal", "Suave", "Media", "Fuerte"]
CURVA_INTENSIDAD_DEF = 1.7

ESTILOS_COLOR = {
    "plano": "Plano",
    "degradado": "Degradado",
    "cambiante": "Cambiante",
    "movimiento": "En movimiento",
}
PALETAS = {                          # nombre -> (color 1, color 2)
    "Océano": ("#2f81f7", "#39c5cf"),
    "Atardecer": ("#ff7b54", "#c13c8e"),
    "Aurora": ("#2ea043", "#a371f7"),
    "Neón": ("#ff2fd0", "#2ff6ff"),
    "Bosque": ("#1f7a4d", "#a3c24a"),
    "Fuego": ("#e5534b", "#f0b429"),
    "Lavanda": ("#8957e5", "#d2a8ff"),
    "Grafito": ("#6e7681", "#c9d1d9"),
}
PERIODO_MOVIMIENTO = 8.0            # s que tarda el degradado en dar una vuelta

VISIBILIDADES = ("siempre", "auto", "asomar", "salto")
POSICIONES_AVISO = ("cursor", "barra")
TEMAS_APP = ("sistema", "claro", "oscuro")
TEMAS_BARRA = ("app", "sistema", "claro", "oscuro", "ninguno")
MODOS_BRILLO = ("continuo", "pixeles", "minutos")
CELEBRACIONES = ("emojis", "emojis_propios", "imagen", "texto", "minimalista", "ninguna")
TIPOS_HITO = {"porcentaje": "% jornada", "trabajado": "Trabajado", "restante": "Restante"}

HITOS_DEF = [
    {"tipo": "porcentaje", "valor": "25",
     "mensaje": "Primer cuarto hecho. Buen ritmo. | 25 % fuera. Arrancada sólida."},
    {"tipo": "porcentaje", "valor": "33",
     "mensaje": "Un tercio despachado. Lo más pesado ya está rodando."},
    {"tipo": "porcentaje", "valor": "50",
     "mensaje": "Ecuador de la jornada. De aquí en adelante, cuesta abajo. | "
                "Mitad hecha. La otra mitad ya te conoce."},
    {"tipo": "porcentaje", "valor": "75",
     "mensaje": "Tres cuartos. Ya se ve la salida desde aquí."},
    {"tipo": "restante", "valor": "0:30",
     "mensaje": "Media hora y libre. Ve cerrando frentes."},
    {"tipo": "restante", "valor": "0:10",
     "mensaje": "10 minutos. Guarda, commit y respira. Sales a las {salida}."},
]

# Brillo de la punta
BRILLO_ANCHO = 56                   # px de estela detrás de la punta
BRILLO_HALO = 6                     # px de halo por delante de la punta
BRILLO_ATAQUE = 0.25                # s de encendido
BRILLO_MANTENER = 0.35              # s a plena intensidad
BRILLO_CAIDA = 1.6                  # s de apagado

# Avance por saltos: la duración crece con la raíz del tiempo acumulado, así
# un salto de 30 min dura más que uno de 5 min pero también corre más rápido.
SALTO_BASE_S = 0.6                  # duración de un salto de SALTO_REF_S
SALTO_REF_S = 300                   # 5 minutos acumulados
SALTO_MIN_S, SALTO_MAX_S = 0.25, 3.0

# False -> pegada al borde superior de la barra de tareas (recomendado).
PEGADA_AL_BORDE_FISICO = False

# Revelado automático
SEGUNDOS_ESPERA = 0.05
SEGUNDOS_PERMANENCIA = 5.0
ZONA_DETECCION = 3
PASO_ANIMACION_MS = 25

# Avance por saltos: preaviso y aparición
PREAVISO_DEF = 2                    # s con la cabeza encendida antes de saltar
RECTA_FINAL_DEF = 10                # min finales en los que se avanza sin saltos
APARICION_PREVIA_S = 2.0            # "Aparecer con cada salto": margen antes del preaviso
RESPIRACION_PERIODO = 0.9           # s por ciclo de "respiración" durante el preaviso
RESPIRACION_MINIMO = 0.65           # intensidad mínima de la respiración
ESTELA_SALTO = 1.6                  # la estela es más larga en preaviso y salto

# Burbujas de aviso
BURBUJA_ANCHO_TEXTO = 300
BURBUJA_RADIO = 12
BURBUJA_PADX, BURBUJA_PADY = 12, 8
BURBUJA_COLA = 12
BURBUJA_MARGEN_X = 110              # holgura lateral para que la colita se incline
BURBUJA_MARGEN_Y = BURBUJA_COLA + 10
BURBUJA_ZONA_MUERTA = 40            # px que puede alejarse el objetivo sin mover el cuerpo
BURBUJA_INERCIA = 0.18              # fracción de la distancia que recorre por fotograma
BURBUJA_INERCIA_V = 0.6             # en vertical sigue casi al instante
BURBUJA_SOBRE_CURSOR = 6            # la punta queda 6 px por encima del puntero…
BURBUJA_BAJO_CURSOR = 24            # …o 24 px por debajo (bajo la flecha) si no cabe arriba
INTERVALO_BURBUJA_MS = 16           # ~60 fps mientras hay burbuja
POP_MS = 160                        # entrada con rebote: 80 % -> 105 % -> 100 %
AVISO_SEG_BASE = 4.0                # duración automática: base + por palabra
AVISO_SEG_PALABRA = 0.3
AVISO_SEG_MIN, AVISO_SEG_MAX = 5.0, 10.0

# Cerrar una burbuja sacudiendo el ratón (zigzag horizontal)
ZIGZAG_CAMBIOS = 3                  # cambios de sentido necesarios…
ZIGZAG_VENTANA_S = 1.0              # …dentro de este tiempo
ZIGZAG_MIN_PX = 40                  # recorrido mínimo de cada tramo
ZIGZAG_HISTERESIS_PX = 8            # retroceso mínimo para contar un cambio de sentido
ZIGZAG_MAX_VERTICAL = 0.6           # movimiento vertical tolerado respecto al horizontal

# Celebración final
NUM_PARTICULAS = 45
EMOJIS_DEF = "🎉🎊✨🥳🎈🌟💪🛋️😴🍻👏🔥⭐🏆🙌"
RUTA_FUENTE_EMOJI = r"C:\Windows\Fonts\seguiemj.ttf"

# Intervalos
INTERVALO_LOGICA_MS = 1000
INTERVALO_ANIMACION_MS = 33         # ~30 fps con brillo activo
INTERVALO_MOVIMIENTO_MS = 50        # ~20 fps si solo se mueve el degradado
INTERVALO_HOVER_MS = 100
INTERVALO_TOPMOST_MS = 500
INTERVALO_BURBUJAS_MS = 300
INTERVALO_TEMA_S = 3.0             # sondeo del tema de Windows (como ExtractJ)
INTERVALO_PARTICULAS_MS = 33

COLOR_CLAVE = "#010203"             # color que Windows hará transparente

RUTA_ESTADO = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "barra_jornada",
    "estado.json",
)
RUTA_PREFERENCIAS = os.path.join(os.path.dirname(RUTA_ESTADO), "preferencias.json")

# Diagnóstico: crea un fichero vacío "diagnostico.on" en la carpeta de datos
# y la barra irá apuntando en "diagnostico.log" dónde coloca cada burbuja.
RUTA_DIAGNOSTICO_ON = os.path.join(os.path.dirname(RUTA_ESTADO), "diagnostico.on")
RUTA_DIAGNOSTICO_LOG = os.path.join(os.path.dirname(RUTA_ESTADO), "diagnostico.log")

# Paletas de interfaz por tema
TEMAS_UI = {
    "claro": {
        "bg": "#f3f3f3", "fg": "#1b1b1b", "campo": "#ffffff", "borde": "#c9c9c9",
        "boton": "#e4e4e4", "boton_activo": "#d4d4d4", "acento": "#0b63ce",
        "tenue": "#8a8a8a", "aviso": "#c0392b",
        "tooltip_bg": "#ffffff", "tooltip_fg": "#1b1b1b",
        "burbuja_bg": "#d9fdd3", "burbuja_fg": "#111b21", "burbuja_borde": "#b4d9ad",
        "tarjeta": "#ffffff",
    },
    "oscuro": {
        "bg": "#202020", "fg": "#e8e8e8", "campo": "#2b2b2b", "borde": "#3d3d3d",
        "boton": "#2f2f2f", "boton_activo": "#3b3b3b", "acento": "#4c9aff",
        "tenue": "#7d7d7d", "aviso": "#ff7b72",
        "tooltip_bg": "#101010", "tooltip_fg": "#f0f0f0",
        "burbuja_bg": "#005c4b", "burbuja_fg": "#e9edef", "burbuja_borde": "#00483b",
        "tarjeta": "#1f1f1f",
    },
}
FONDO_BARRA = {"claro": "#cfcfcf", "oscuro": "#1c1c1c", "ninguno": "#1c1c1c"}

FUENTE = ("Segoe UI", 9)
FUENTE_NEGRITA = ("Segoe UI", 9, "bold")

# --------------------------------------------------------------------------
# WinAPI
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.restype = ctypes.c_long
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.GetTickCount.restype = wintypes.DWORD
user32.FindWindowExW.restype = wintypes.HWND
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SW_SHOWNOACTIVATE = 4

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SPI_GETWORKAREA = 0x0030
GA_ROOT = 2
ERROR_ALREADY_EXISTS = 183

# SHQueryUserNotificationState: 1 = bloqueado / salvapantallas,
# 2 = app a pantalla completa, 3 = Direct3D a pantalla completa,
# 4 = modo presentación.
ESTADOS_OCUPADO = (1, 2, 3, 4)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _hwnd(widget: tk.Misc) -> int:
    hwnd = widget.winfo_id()
    raiz = user32.GetAncestor(hwnd, GA_ROOT)
    return raiz if raiz else hwnd


def _aplicar_estilos(hwnd: int, click_through: bool) -> None:
    estilos = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
    if click_through:
        estilos |= WS_EX_TRANSPARENT
    actual = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, actual | estilos)


CLASE_MENU = "#32768"                # clase de todos los menús contextuales clásicos


def menu_contextual_abierto() -> bool:
    """True si hay un menú contextual de Windows visible (bandeja, escritorio…)."""
    hwnd = None
    for _ in range(64):
        hwnd = user32.FindWindowExW(None, hwnd, CLASE_MENU, None)
        if not hwnd:
            return False
        if user32.IsWindowVisible(hwnd):
            return True
    return False


def _forzar_topmost(hwnd: int) -> None:
    """Sube la ventana encima de todo, salvo que haya un menú contextual abierto."""
    if menu_contextual_abierto():
        return
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def _area_trabajo() -> wintypes.RECT:
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect


def _posicion_cursor() -> tuple[int, int]:
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


MONITOR_DEFAULTTONEAREST = 2


def area_monitor(x: int, y: int) -> tuple[int, int, int, int]:
    """Área de trabajo (izq, arriba, der, abajo) del monitor que contiene (x, y)."""
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    try:
        hmon = user32.MonitorFromPoint(POINT(x, y), MONITOR_DEFAULTTONEAREST)
        if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcWork
            if r.right > r.left and r.bottom > r.top:
                return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError, ctypes.ArgumentError):
        pass
    r = _area_trabajo()
    return r.left, r.top, r.right, r.bottom


def rect_ventana(hwnd: int) -> tuple[int, int, int, int] | None:
    """Rectángulo real de una ventana en pantalla, según Windows."""
    rect = wintypes.RECT()
    try:
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)) and rect.right > rect.left:
            return rect.left, rect.top, rect.right, rect.bottom
    except (AttributeError, OSError, ctypes.ArgumentError):
        pass
    return None


MODO_DPI = "sin activar"


def activar_dpi_por_monitor() -> str:
    """
    Declara el proceso compatible con DPI por monitor (v2) ANTES de crear
    ventanas. Así Windows no reescala la barra a mapa de bits y todas las
    coordenadas (Tk, cursor, área de trabajo) son píxeles reales.
    """
    global MODO_DPI
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            MODO_DPI = "por monitor v2"
            return MODO_DPI
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            MODO_DPI = "por monitor"
            return MODO_DPI
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            MODO_DPI = "sistema"
    except (AttributeError, OSError):
        pass
    return MODO_DPI


def dpi_ventana(hwnd: int) -> int:
    try:
        return int(user32.GetDpiForWindow(hwnd)) or 96
    except (AttributeError, OSError):
        return 96


def segundos_inactivo() -> float:
    """Segundos desde la última pulsación de teclado o movimiento de ratón."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    ahora = kernel32.GetTickCount() & 0xFFFFFFFF
    return ((ahora - info.dwTime) & 0xFFFFFFFF) / 1000.0


_MUTEX = None


def es_unica_instancia() -> bool:
    """Crea un mutex con nombre; si ya existía, hay otra instancia abierta."""
    global _MUTEX
    ctypes.set_last_error(0)
    _MUTEX = kernel32.CreateMutexW(None, False, "Local\\BarraJornada_instancia_unica")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def pantalla_ocupada() -> bool:
    """True si hay una app a pantalla completa, presentación o sesión bloqueada."""
    estado = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(estado)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return estado.value in ESTADOS_OCUPADO


def barra_titulo_oscura(hwnd: int, oscura: bool) -> None:
    """
    Pide a Windows la barra de título oscura (o clara) para una ventana y fuerza
    el repintado del marco; sin eso, el cambio no se ve hasta perder el foco.
    """
    valor = ctypes.c_int(1 if oscura else 0)
    try:
        dwm = ctypes.windll.dwmapi
        for atributo in (20, 19):   # 19 en compilaciones antiguas de Windows 10
            if dwm.DwmSetWindowAttribute(
                hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor)
            ) == 0:
                break
        user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except (AttributeError, OSError):
        pass


def _leer_tema_registro(nombre: str) -> bool | None:
    """True = claro, False = oscuro, None = no se pudo leer."""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as clave:
            valor, _ = winreg.QueryValueEx(clave, nombre)
            return bool(valor)
    except OSError:
        return None


def tema_sistema_apps() -> str:
    claro = _leer_tema_registro("AppsUseLightTheme")
    return "oscuro" if claro is False else "claro"


def tema_sistema_barra_tareas() -> str:
    claro = _leer_tema_registro("SystemUsesLightTheme")
    return "claro" if claro else "oscuro"


# --------------------------------------------------------------------------
# Utilidades de texto y tiempo
# --------------------------------------------------------------------------
def parsear_hhmm(texto: str) -> tuple[int, int]:
    """Acepta '9', '9:30', '9.30' o '9,30'. Un número suelto son horas en punto."""
    limpio = texto.strip().replace(".", ":").replace(",", ":")
    if not limpio:
        raise ValueError("vacío")
    partes = limpio.split(":")
    if len(partes) == 1:
        return int(partes[0]), 0
    if len(partes) == 2:
        horas, minutos = partes
        return int(horas), int(minutos or 0)
    raise ValueError("formato no válido")


def minutos_hhmm(texto: str) -> int:
    h, m = parsear_hhmm(texto)
    if h < 0 or m < 0 or m >= 60:
        raise ValueError("fuera de rango")
    return h * 60 + m


def formatear_hhmm(minutos: int) -> str:
    return f"{minutos // 60}:{minutos % 60:02d}"


def formatear_duracion(segundos: float) -> str:
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    return f"{horas}h {resto // 60:02d}m"


def formatear_corto(segundos: float) -> str:
    """'23 min' o '1 h 05 min', para mensajes legibles."""
    minutos = max(0, int(round(segundos / 60)))
    if minutos < 60:
        return f"{minutos} min"
    h, m = divmod(minutos, 60)
    return f"{h} h" if m == 0 else f"{h} h {m:02d} min"


def separar_emojis(texto: str) -> list[str]:
    """
    Parte un texto en emojis completos: respeta selectores de variación,
    tonos de piel, uniones ZWJ (👨‍💻), teclas (1️⃣) y banderas (🇪🇸).
    """
    grupos: list[str] = []
    actual = ""
    for c in texto:
        if c.isspace():
            if actual:
                grupos.append(actual)
                actual = ""
            continue
        cp = ord(c)
        unir = bool(actual) and (
            cp in (0xFE0F, 0xFE0E, 0x200D, 0x20E3)
            or 0x1F3FB <= cp <= 0x1F3FF
            or 0xE0020 <= cp <= 0xE007F
            or actual[-1] == "\u200d"
            or (
                0x1F1E6 <= cp <= 0x1F1FF
                and len(actual) == 1
                and 0x1F1E6 <= ord(actual) <= 0x1F1FF
            )
        )
        if unir:
            actual += c
        else:
            if actual:
                grupos.append(actual)
            actual = c
    if actual:
        grupos.append(actual)
    return grupos


def clave_hito(hito: dict) -> str:
    return f"{hito['tipo']}|{hito['valor'].strip()}"


def valor_hito_valido(tipo: str, valor: str) -> bool:
    try:
        if tipo == "porcentaje":
            v = float(valor.replace(",", ".").replace("%", "").strip())
            return 0 < v <= 100
        return minutos_hhmm(valor) > 0
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Colores
# --------------------------------------------------------------------------
def color_valido(valor, por_defecto: str) -> str:
    if isinstance(valor, str) and len(valor) == 7 and valor.startswith("#"):
        try:
            int(valor[1:], 16)
            return valor.lower()
        except ValueError:
            pass
    return por_defecto


def _hex_a_rgb(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _rgb_a_hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(v))) for v in rgb))


def _mezclar_rgb(a, b, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def mezclar(c1: str, c2: str, t: float) -> str:
    return _rgb_a_hex(_mezclar_rgb(_hex_a_rgb(c1), _hex_a_rgb(c2), t))


def _a_lineal(v: int) -> float:
    return (v / 255.0) ** 2.2


def _a_srgb(v: float) -> int:
    return int(round(255.0 * max(0.0, min(1.0, v)) ** (1 / 2.2)))


def mezclar_lineal(a, b, t: float) -> tuple[int, int, int]:
    """Mezcla en luz lineal: degradados sin la 'banda sucia' del centro."""
    t = max(0.0, min(1.0, t))
    return tuple(
        _a_srgb(_a_lineal(x) + (_a_lineal(y) - _a_lineal(x)) * t) for x, y in zip(a, b)
    )


def atenuar(color: str, intensidad: float) -> str:
    """Baja brillo y algo de saturación (intensidad 0..1)."""
    if intensidad <= 0:
        return color
    r, g, b = _hex_a_rgb(color)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    s = intensidad * 0.6
    r, g, b = (v + (lum - v) * s for v in (r, g, b))
    k = 1.0 - intensidad
    return _rgb_a_hex((r * k, g * k, b * k))


def color_contraste(color: str) -> str:
    r, g, b = _hex_a_rgb(color)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def envolvente_brillo(s: float, base: float = 0.0, mantener: float = BRILLO_MANTENER) -> float:
    """Intensidad de un pulso de brillo a los `s` segundos de dispararse."""
    if s < 0:
        return 0.0
    if s < BRILLO_ATAQUE:
        return base + (1.0 - base) * math.sin(math.pi / 2 * s / BRILLO_ATAQUE)
    s -= BRILLO_ATAQUE
    if s < mantener:
        return 1.0
    s -= mantener
    if s < BRILLO_CAIDA:
        return 0.5 * (1.0 + math.cos(math.pi * s / BRILLO_CAIDA))
    return 0.0


DURACION_PULSO = BRILLO_ATAQUE + BRILLO_MANTENER + BRILLO_CAIDA


def respiracion(s: float, preaviso: float) -> float:
    """
    Factor que hace 'respirar' la cabeza blanca durante el preaviso, para que
    se note de reojo antes de que la barra salte. 1 fuera del preaviso.
    """
    if preaviso <= 0 or s <= BRILLO_ATAQUE or s >= preaviso:
        return 1.0
    fase = 2 * math.pi * (s - BRILLO_ATAQUE) / RESPIRACION_PERIODO
    medio = (1.0 + RESPIRACION_MINIMO) / 2
    return medio + (1.0 - medio) * math.cos(fase)


def duracion_aviso(texto: str, segundos_fijos: int = 0) -> float:
    """Automática: 4 s + 0,3 s por palabra, entre 5 y 10 s. O un valor fijo."""
    if segundos_fijos > 0:
        return float(segundos_fijos)
    palabras = len(texto.split())
    return max(AVISO_SEG_MIN, min(AVISO_SEG_MAX, AVISO_SEG_BASE + AVISO_SEG_PALABRA * palabras))


def escala_pop(t: float) -> float:
    """Escala de entrada con rebote: 0,8 -> 1,05 (al 60 %) -> 1,0."""
    if t >= 1.0:
        return 1.0
    if t <= 0.0:
        return 0.8
    if t < 0.6:
        return 0.8 + 0.25 * math.sin(math.pi / 2 * t / 0.6)
    return 1.05 - 0.05 * math.sin(math.pi / 2 * (t - 0.6) / 0.4)


def duracion_salto(acumulado_s: float) -> float:
    """Segundos que tarda la punta en soltar `acumulado_s` de avance retenido."""
    t = SALTO_BASE_S * math.sqrt(max(0.0, acumulado_s) / SALTO_REF_S)
    return max(SALTO_MIN_S, min(SALTO_MAX_S, t))


def suavizar_salida(u: float) -> float:
    """Ease-out cúbico: arranca rápido y frena al llegar."""
    u = max(0.0, min(1.0, u))
    return 1.0 - (1.0 - u) ** 3


# --------------------------------------------------------------------------
# Configuración: valores por defecto, validación y migración
# --------------------------------------------------------------------------
def config_por_defecto() -> dict:
    return {
        "duracion_min": minutos_hhmm(DURACION_POR_DEFECTO),
        "progreso": "real",
        "curva": None,                      # None = recomendada por horas
        "al_completar": "cerrar",
        "color_extra": COLOR_EXTRA_DEF,
        "inactividad": False,
        "inactividad_min": 10,
        "visibilidad": "siempre",
        "asomar_cada_min": 15,
        "asomar_seg": 5,
        "altura": ALTURA_DEF,
        "marcas_hora": False,
        "estilo_trabajo": {"tipo": "plano", "c1": COLOR_TRABAJO_DEF, "c2": COLOR_TRABAJO2_DEF},
        "estilo_descanso": {"tipo": "plano", "c1": COLOR_DESCANSO_DEF, "c2": COLOR_DESCANSO2_DEF},
        "brillo": True,
        "brillo_modo": "minutos",
        "brillo_px_min": 20,
        "brillo_px_max": 20,
        "brillo_min_min": 5,
        "brillo_min_max": 5,
        "saltos": False,
        "preaviso_s": PREAVISO_DEF,
        "recta_final_min": RECTA_FINAL_DEF,
        "aviso_posicion": "cursor",
        "aviso_segundos": 0,                # 0 = automática según el texto
        "tema_app": "sistema",
        "tema_barra": "app",
        "atenuacion": 15,
        "avisos": True,
        "hitos": [dict(h) for h in HITOS_DEF],
        "no_molestar": True,
        "descanso_largo": False,
        "descanso_largo_min": 20,
        "descanso_largo_msg": "Llevas {descanso} de descanso. ¿Volvemos?",
        "celebracion": "emojis",
        "emojis_propios": "🍕🎮☕🚀",
        "imagen_ruta": "",
        "texto_celebracion": "¡Jornada completada!",
        "segundos_celebracion": 10,
    }


def _entero(valor, minimo: int, maximo: int, defecto: int) -> int:
    if isinstance(valor, bool):
        return defecto
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return defecto
    return max(minimo, min(maximo, valor))


def _opcion(valor, validas, defecto):
    return valor if valor in validas else defecto


def _texto(valor, defecto: str) -> str:
    return valor if isinstance(valor, str) else defecto


def _estilo(valor, defecto: dict) -> dict:
    if not isinstance(valor, dict):
        return dict(defecto)
    return {
        "tipo": _opcion(valor.get("tipo"), ESTILOS_COLOR, defecto["tipo"]),
        "c1": color_valido(valor.get("c1"), defecto["c1"]),
        "c2": color_valido(valor.get("c2"), defecto["c2"]),
    }


def _hitos(valor, defecto: list) -> list:
    if not isinstance(valor, list):
        return [dict(h) for h in defecto]
    resultado = []
    for h in valor:
        if (
            isinstance(h, dict)
            and h.get("tipo") in TIPOS_HITO
            and isinstance(h.get("valor"), str)
            and isinstance(h.get("mensaje"), str)
        ):
            resultado.append({"tipo": h["tipo"], "valor": h["valor"], "mensaje": h["mensaje"]})
    return resultado


def normalizar_config(datos, base: dict | None = None) -> dict:
    """
    Valida un diccionario de configuración clave a clave; lo que falte o no
    sea válido se toma de `base`. Migra el formato de la v1.x.
    """
    base = copy.deepcopy(base) if base else config_por_defecto()
    if not isinstance(datos, dict):
        return base
    d = dict(datos)

    # Migración v1.x: colores planos sueltos -> estilos por modo
    if "estilo_trabajo" not in d and "color_trabajo" in d:
        d["estilo_trabajo"] = {
            "tipo": "plano", "c1": d.get("color_trabajo"), "c2": base["estilo_trabajo"]["c2"],
        }
    if "estilo_descanso" not in d and "color_descanso" in d:
        d["estilo_descanso"] = {
            "tipo": "plano", "c1": d.get("color_descanso"), "c2": base["estilo_descanso"]["c2"],
        }

    c = {}
    c["duracion_min"] = _entero(d.get("duracion_min"), 1, 24 * 60, base["duracion_min"])
    c["progreso"] = _opcion(d.get("progreso"), ("real", "curva"), base["progreso"])
    c["curva"] = d["curva"] if d.get("curva") in CURVAS else base["curva"]
    c["al_completar"] = _opcion(d.get("al_completar"), ("cerrar", "extra"), base["al_completar"])
    c["color_extra"] = color_valido(d.get("color_extra"), base["color_extra"])
    c["inactividad"] = bool(d.get("inactividad", base["inactividad"]))
    c["inactividad_min"] = _entero(d.get("inactividad_min"), 1, 240, base["inactividad_min"])
    c["visibilidad"] = _opcion(d.get("visibilidad"), VISIBILIDADES, base["visibilidad"])
    c["asomar_cada_min"] = _entero(d.get("asomar_cada_min"), 1, 240, base["asomar_cada_min"])
    c["asomar_seg"] = _entero(d.get("asomar_seg"), 1, 120, base["asomar_seg"])
    c["altura"] = _entero(d.get("altura"), ALTURA_MIN, ALTURA_MAX, base["altura"])
    c["marcas_hora"] = bool(d.get("marcas_hora", base["marcas_hora"]))
    c["estilo_trabajo"] = _estilo(d.get("estilo_trabajo"), base["estilo_trabajo"])
    c["estilo_descanso"] = _estilo(d.get("estilo_descanso"), base["estilo_descanso"])
    c["brillo"] = bool(d.get("brillo", base["brillo"]))
    c["brillo_modo"] = _opcion(d.get("brillo_modo"), MODOS_BRILLO, base["brillo_modo"])
    c["saltos"] = bool(d.get("saltos", base["saltos"]))
    c["preaviso_s"] = _entero(d.get("preaviso_s"), 0, 5, base["preaviso_s"])
    c["recta_final_min"] = _entero(d.get("recta_final_min"), 0, 120, base["recta_final_min"])
    c["aviso_posicion"] = _opcion(d.get("aviso_posicion"), POSICIONES_AVISO, base["aviso_posicion"])
    c["aviso_segundos"] = _entero(d.get("aviso_segundos"), 0, 60, base["aviso_segundos"])
    for clave, maximo in (
        ("brillo_px_min", 2000), ("brillo_px_max", 2000),
        ("brillo_min_min", 240), ("brillo_min_max", 240),
    ):
        c[clave] = _entero(d.get(clave), 1, maximo, base[clave])
    if c["brillo_px_min"] > c["brillo_px_max"]:
        c["brillo_px_min"], c["brillo_px_max"] = c["brillo_px_max"], c["brillo_px_min"]
    if c["brillo_min_min"] > c["brillo_min_max"]:
        c["brillo_min_min"], c["brillo_min_max"] = c["brillo_min_max"], c["brillo_min_min"]
    c["tema_app"] = _opcion(d.get("tema_app"), TEMAS_APP, base["tema_app"])
    c["tema_barra"] = _opcion(d.get("tema_barra"), TEMAS_BARRA, base["tema_barra"])
    c["atenuacion"] = _entero(d.get("atenuacion"), 0, 40, base["atenuacion"])
    c["avisos"] = bool(d.get("avisos", base["avisos"]))
    c["hitos"] = _hitos(d.get("hitos"), base["hitos"])
    c["no_molestar"] = bool(d.get("no_molestar", base["no_molestar"]))
    c["descanso_largo"] = bool(d.get("descanso_largo", base["descanso_largo"]))
    c["descanso_largo_min"] = _entero(
        d.get("descanso_largo_min"), 1, 480, base["descanso_largo_min"]
    )
    c["descanso_largo_msg"] = _texto(d.get("descanso_largo_msg"), base["descanso_largo_msg"])
    c["celebracion"] = _opcion(d.get("celebracion"), CELEBRACIONES, base["celebracion"])
    c["emojis_propios"] = _texto(d.get("emojis_propios"), base["emojis_propios"])
    c["imagen_ruta"] = _texto(d.get("imagen_ruta"), base["imagen_ruta"])
    c["texto_celebracion"] = _texto(d.get("texto_celebracion"), base["texto_celebracion"])
    c["segundos_celebracion"] = _entero(
        d.get("segundos_celebracion"), 2, 60, base["segundos_celebracion"]
    )
    return c


def _leer_json(ruta: str):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _escribir_json(ruta: str, datos) -> None:
    """Escritura atómica: un cierre brusco nunca deja el fichero a medias."""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.replace(temporal, ruta)
    except OSError:
        pass


def cargar_preferencias() -> dict:
    return normalizar_config(_leer_json(RUTA_PREFERENCIAS))


def guardar_preferencias(cfg: dict) -> None:
    _escribir_json(RUTA_PREFERENCIAS, dict(cfg, version=2))


def curva_recomendada(duracion_min: int) -> str:
    horas = duracion_min / 60.0
    if horas <= 6:
        return "Suave"
    if horas <= 9:
        return "Media"
    return "Fuerte"


def tema_efectivo_app(cfg: dict) -> str:
    tema = cfg["tema_app"]
    return tema_sistema_apps() if tema == "sistema" else tema


def tema_efectivo_barra(cfg: dict) -> str:
    tema = cfg["tema_barra"]
    if tema == "app":
        return tema_efectivo_app(cfg)
    if tema == "sistema":
        return tema_sistema_barra_tareas()
    return tema                     # claro / oscuro / ninguno


def estilo_para_tema(estilo: dict, tema_barra: str, atenuacion: int) -> dict:
    """En tema oscuro, los colores de la barra se atenúan un poco."""
    if tema_barra != "oscuro" or atenuacion <= 0:
        return estilo
    f = atenuacion / 100.0
    return {"tipo": estilo["tipo"], "c1": atenuar(estilo["c1"], f), "c2": atenuar(estilo["c2"], f)}


def normalizar_tramos(tramos: list) -> list:
    """Ordena y fusiona tramos consecutivos del mismo modo."""
    resultado = []
    for desde, modo in sorted(tramos, key=lambda t: t[0]):
        if resultado and resultado[-1][1] == modo:
            continue
        resultado.append((desde, modo))
    return resultado


# --------------------------------------------------------------------------
# Motor de pintado: la barra entera es UNA imagen
# --------------------------------------------------------------------------
def _construir_tira(c1: str, c2: str, n: int, periodo: int | None) -> Image.Image:
    """
    Tira de 1 px de alto. Sin periodo: degradado c1 -> c2 a lo largo de n px.
    Con periodo: ida y vuelta c1 -> c2 -> c1 cada `periodo` px (cíclica).
    """
    a, b = _hex_a_rgb(c1), _hex_a_rgb(c2)
    datos = []
    for i in range(n):
        if periodo:
            p = (i % periodo) / periodo
            t = 0.5 - 0.5 * math.cos(2 * math.pi * p)
        else:
            t = i / (n - 1) if n > 1 else 0.0
        datos.append(mezclar_lineal(a, b, t))
    img = Image.new("RGB", (n, 1))
    img.putdata(datos)
    return img


def recortar_segmentos(segmentos: list, px: int) -> list:
    """Corta los segmentos en la punta visible (para el avance por saltos)."""
    return [(x0, min(x1, px), e) for x0, x1, e in segmentos if x0 < px]


class PintorBarra:
    """Genera la imagen de la barra a partir de segmentos ya calculados."""

    def __init__(self) -> None:
        self._cache: dict[tuple, Image.Image] = {}

    def limpiar(self) -> None:
        self._cache.clear()

    def _tira(self, estilo: dict, ancho: int, progreso: float) -> Image.Image:
        tipo, c1, c2 = estilo["tipo"], estilo["c1"], estilo["c2"]
        if tipo == "cambiante":
            color = mezclar_lineal(_hex_a_rgb(c1), _hex_a_rgb(c2), progreso)
            return Image.new("RGB", (ancho, 1), color)
        clave = (tipo, c1, c2, ancho)
        tira = self._cache.get(clave)
        if tira is None:
            if len(self._cache) > 24:
                self._cache.clear()
            if tipo == "degradado":
                tira = _construir_tira(c1, c2, ancho, None)
            elif tipo == "movimiento":
                tira = _construir_tira(c1, c2, ancho * 2, ancho)
            else:
                tira = Image.new("RGB", (ancho, 1), _hex_a_rgb(c1))
            self._cache[clave] = tira
        return tira

    def pintar(
        self,
        ancho: int,
        alto: int,
        fondo: str,
        segmentos: list,
        progreso: float,
        t_anim: float,
        brillo: float,
        px_borde: int,
        marcas: list,
        estela: int = BRILLO_ANCHO,
    ) -> Image.Image:
        fila = Image.new("RGB", (ancho, 1), _hex_a_rgb(fondo))
        desplazamiento = int((t_anim / PERIODO_MOVIMIENTO) % 1.0 * ancho)

        for x0, x1, estilo in segmentos:
            x0, x1 = max(0, x0), min(ancho, x1)
            if x1 <= x0:
                continue
            tira = self._tira(estilo, ancho, progreso)
            if estilo["tipo"] == "movimiento":
                o = ancho - desplazamiento
                trozo = tira.crop((o + x0, 0, o + x1, 1))
            else:
                trozo = tira.crop((x0, 0, x1, 1))
            fila.paste(trozo, (x0, 0))

        px = fila.load()
        if marcas:
            fondo_rgb = _hex_a_rgb(fondo)
            contraste = _hex_a_rgb(color_contraste(fondo))
            for xm in marcas:
                if 0 < xm < ancho:
                    if xm < px_borde:
                        px[xm, 0] = _mezclar_rgb(px[xm, 0], fondo_rgb, 0.5)
                    else:
                        px[xm, 0] = _mezclar_rgb(px[xm, 0], contraste, 0.22)

        if brillo > 0.01 and px_borde > 0:
            self._brillo(px, ancho, px_borde, brillo, estela)

        if alto != 1:
            fila = fila.resize((ancho, alto), Image.NEAREST)
        return fila

    @staticmethod
    def _brillo(px, ancho: int, borde: int, intensidad: float, estela: int) -> None:
        """Estela tipo cometa detrás de la punta y un halo suave por delante."""
        punta = min(borde, ancho) - 1
        if punta < 0:
            return
        blanco = (255, 255, 255)
        cabeza = _mezclar_rgb(px[punta, 0], blanco, 0.7)
        for d in range(min(estela, punta + 1)):
            x = punta - d
            f = (1.0 - d / estela) ** 2.4                # curva no lineal
            px[x, 0] = _mezclar_rgb(px[x, 0], blanco, intensidad * f * 0.92)
        for d in range(1, BRILLO_HALO + 1):
            x = punta + d
            if x >= ancho:
                break
            f = (1.0 - d / (BRILLO_HALO + 1)) ** 2
            px[x, 0] = _mezclar_rgb(px[x, 0], cabeza, intensidad * f * 0.6)


# --------------------------------------------------------------------------
# Dibujo auxiliar
# --------------------------------------------------------------------------
def _puntos_redondeados(x1, y1, x2, y2, r) -> list:
    """Puntos de control de un rectángulo redondeado (polígono con smooth=True)."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def _rect_redondeado(lienzo: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    return lienzo.create_polygon(_puntos_redondeados(x1, y1, x2, y2, r), smooth=True, **kw)


def _medir_texto(lienzo: tk.Canvas, texto: str, fuente, ancho: int | None = None):
    kw = {"width": ancho} if ancho else {}
    item = lienzo.create_text(0, 0, text=texto, font=fuente, anchor="nw", **kw)
    x1, y1, x2, y2 = lienzo.bbox(item)
    lienzo.delete(item)
    return x2 - x1, y2 - y1


class _VentanaFlotante:
    """Ventana sin bordes, siempre encima, que deja pasar los clics."""

    def __init__(self, root: tk.Tk, geometria: str | None = None) -> None:
        self.root = root
        self.ventana = tk.Toplevel(root)
        self.ventana.withdraw()
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.configure(bg=COLOR_CLAVE)
        self.ventana.attributes("-transparentcolor", COLOR_CLAVE)
        if geometria:
            self.ventana.geometry(geometria)
        self.lienzo = tk.Canvas(self.ventana, bg=COLOR_CLAVE, highlightthickness=0, bd=0)
        self.lienzo.pack(fill="both", expand=True)

    def mostrar(self, geometria: str, alpha: float = 1.0, clicable: bool = False) -> None:
        self.ventana.geometry(geometria)
        try:
            self.ventana.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.ventana.deiconify()
        self.ventana.update_idletasks()
        self.hwnd = _hwnd(self.ventana)
        # Clicable: recibe el clic pero sigue sin robar el foco (WS_EX_NOACTIVATE).
        # Las zonas del color clave dejan pasar el clic igualmente.
        _aplicar_estilos(self.hwnd, click_through=not clicable)
        _forzar_topmost(self.hwnd)

    def existe(self) -> bool:
        try:
            return bool(self.ventana.winfo_exists())
        except tk.TclError:
            return False

    def fundido(self, desde: float, hasta: float, ms: int, despues=None) -> None:
        pasos = max(1, ms // 20)

        def paso(i: int = 0) -> None:
            if not self.existe():
                return
            try:
                self.ventana.attributes("-alpha", desde + (hasta - desde) * (i / pasos))
            except tk.TclError:
                return
            if i < pasos:
                self.root.after(20, paso, i + 1)
            elif despues:
                despues()

        paso()

    def destruir(self) -> None:
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass


# --------------------------------------------------------------------------
# Burbujas de aviso: junto al cursor o sobre la punta de la barra
# --------------------------------------------------------------------------
class DetectorZigzag:
    """
    Detecta una sacudida horizontal rápida del ratón (→ ← → ←). Cuenta los
    cambios de sentido con recorrido suficiente y poca componente vertical;
    con ZIGZAG_CAMBIOS dentro de ZIGZAG_VENTANA_S, la sacudida es válida.
    """

    def __init__(self) -> None:
        self.sentido = 0
        self.inicio_x = 0.0
        self.extremo_x = 0.0
        self.vertical = 0.0
        self.ultimo: tuple[int, int] | None = None
        self.cambios: list[float] = []

    def alimentar(self, x: int, y: int, t: float) -> bool:
        if self.ultimo is None:
            self.ultimo = (x, y)
            self.inicio_x = self.extremo_x = float(x)
            return False
        _, uy = self.ultimo
        self.ultimo = (x, y)
        self.vertical += abs(y - uy)

        if self.sentido == 0:
            if abs(x - self.inicio_x) >= ZIGZAG_HISTERESIS_PX:
                self.sentido = 1 if x > self.inicio_x else -1
                self.extremo_x = float(x)
            return False

        if (x - self.extremo_x) * self.sentido > 0:
            self.extremo_x = float(x)                   # sigue en el mismo sentido
        elif abs(x - self.extremo_x) >= ZIGZAG_HISTERESIS_PX:
            recorrido = abs(self.extremo_x - self.inicio_x)
            if recorrido >= ZIGZAG_MIN_PX and self.vertical <= recorrido * ZIGZAG_MAX_VERTICAL:
                self.cambios.append(t)
            else:
                self.cambios.clear()                    # un vaivén flojo rompe la serie
            self.inicio_x = self.extremo_x
            self.extremo_x = float(x)
            self.sentido = -self.sentido
            self.vertical = 0.0

        self.cambios = [c for c in self.cambios if t - c <= ZIGZAG_VENTANA_S]
        return len(self.cambios) >= ZIGZAG_CAMBIOS


class Burbuja(_VentanaFlotante):
    """
    Burbuja tipo chat que no captura clics: todo pasa a la ventana de debajo.
    El cuerpo persigue a su objetivo con inercia y una zona muerta, así que
    una sacudida rápida apenas lo mueve; la colita, en cambio, apunta al
    objetivo en tiempo real. Se cierra sola o sacudiendo el ratón.

      modo "cursor": el objetivo es el puntero; encima o, si no cabe, debajo.
      modo "barra":  el objetivo es la punta de la barra; siempre encima.
    """

    def __init__(
        self, root: tk.Tk, texto: str, tema: str, modo: str,
        objetivo, limites, segundos: float, al_cerrar, pop: bool = True,
    ) -> None:
        super().__init__(root)
        self.texto = texto
        self.modo = modo
        self.objetivo = objetivo            # () -> (x, y) en pantalla
        self.limites = limites              # (x, y) -> (izq, arriba, der, abajo)
        self.al_cerrar = al_cerrar
        self.pop = pop
        self._cerrando = False
        self._terminada = False
        self._tam_fuente: int | None = None
        self.zigzag = DetectorZigzag()
        self.punta_pantalla = (0, 0)
        self.geom: str | None = None
        t = TEMAS_UI[tema]

        tw, th = _medir_texto(self.lienzo, texto, ("Segoe UI", 10), BURBUJA_ANCHO_TEXTO)
        self.w = tw + 2 * BURBUJA_PADX
        self.h = th + 2 * BURBUJA_PADY
        self.W = self.w + 2 * BURBUJA_MARGEN_X
        self.H = self.h + 2 * BURBUJA_MARGEN_Y
        self.lienzo.configure(width=self.W, height=self.H)

        # Orden de dibujo: cuerpo, colita, "tapa" que borra el borde en la
        # unión y, encima de todo, el texto.
        self.item_cuerpo = self.lienzo.create_polygon(
            0, 0, 0, 0, 0, 0, smooth=True, fill=t["burbuja_bg"], outline=t["burbuja_borde"]
        )
        self.item_cola = self.lienzo.create_polygon(
            0, 0, 0, 0, 0, 0, fill=t["burbuja_bg"], outline=t["burbuja_borde"]
        )
        self.item_tapa = self.lienzo.create_line(0, 0, 0, 0, fill=t["burbuja_bg"], width=2)
        self.item_texto = self.lienzo.create_text(
            0, 0, text=texto, font=("Segoe UI", 10), width=BURBUJA_ANCHO_TEXTO,
            fill=t["burbuja_fg"], anchor="center", justify="left",
        )

        self.t0 = time.monotonic()
        tx, ty = self.objetivo()
        self.cx = float(tx)                 # centro del cuerpo en pantalla
        self.cy: float | None = None        # borde superior del cuerpo en pantalla
        self._actualizar(tx, ty, primera=True)
        self.mostrar(self.geom, alpha=0.0)  # click-through: no se puede pulsar
        self._ultimo_topmost = time.monotonic()
        self.fundido(0.0, 1.0, 120)
        self._bucle()
        root.after(int(segundos * 1000), self.cerrar)

    # ------------------------------------------------------------ geometría
    def _actualizar(self, tx: int, ty: int, primera: bool = False) -> None:
        izq, arriba, der, abajo = self.limites(tx, ty)
        w, h = self.w, self.h

        if self.modo == "cursor":
            encima = ty - BURBUJA_SOBRE_CURSOR - BURBUJA_COLA - h >= arriba
            punta_y = ty - BURBUJA_SOBRE_CURSOR if encima else ty + BURBUJA_BAJO_CURSOR
        else:
            encima = True
            punta_y = ty

        # Horizontal: zona muerta + inercia (el zigzag casi no mueve el cuerpo).
        if primera:
            self.cx = float(tx)
        else:
            exceso = tx - self.cx
            if abs(exceso) > BURBUJA_ZONA_MUERTA:
                destino = tx - math.copysign(BURBUJA_ZONA_MUERTA, exceso)
                self.cx += (destino - self.cx) * BURBUJA_INERCIA
        self.cx = max(izq + w / 2 + 2, min(der - w / 2 - 2, self.cx))

        # Vertical: casi al instante.
        arriba_cuerpo = punta_y - BURBUJA_COLA - h if encima else punta_y + BURBUJA_COLA
        arriba_cuerpo = max(arriba + 1, min(abajo - h - 1, arriba_cuerpo))
        if primera or self.cy is None:
            self.cy = float(arriba_cuerpo)
        else:
            self.cy += (arriba_cuerpo - self.cy) * BURBUJA_INERCIA_V

        win_x = int(round(self.cx - w / 2 - BURBUJA_MARGEN_X))
        win_y = int(round(self.cy - BURBUJA_MARGEN_Y))
        geom = f"{self.W}x{self.H}+{win_x}+{win_y}"
        if geom != self.geom:
            self.geom = geom
            if not primera:
                self.ventana.geometry(geom)

        # Cuerpo (con el "pop" de entrada) y texto.
        s = escala_pop((time.monotonic() - self.t0) * 1000 / POP_MS) if self.pop else 1.0
        bx = BURBUJA_MARGEN_X + w / 2
        by = BURBUJA_MARGEN_Y + h / 2
        x1, y1, x2, y2 = bx - w * s / 2, by - h * s / 2, bx + w * s / 2, by + h * s / 2
        r = BURBUJA_RADIO * s
        self.lienzo.coords(self.item_cuerpo, *_puntos_redondeados(x1, y1, x2, y2, r))
        tam = max(6, int(round(10 * s)))
        if tam != self._tam_fuente:
            self._tam_fuente = tam
            self.lienzo.itemconfigure(self.item_texto, font=("Segoe UI", tam))
        self.lienzo.coords(self.item_texto, bx, by)

        # Colita: la punta, en el objetivo real; la base, en el borde del cuerpo.
        px = max(2, min(self.W - 2, tx - win_x))
        py = max(1, min(self.H - 1, punta_y - win_y))
        base = max(x1 + r + 6, min(x2 - r - 6, px))
        borde_y = y2 - 1 if encima else y1 + 1
        self.lienzo.coords(self.item_cola, base - 7, borde_y, base + 7, borde_y, px, py)
        self.lienzo.coords(self.item_tapa, base - 6, borde_y, base + 6, borde_y)
        self.punta_pantalla = (win_x + px, win_y + py)

    def _bucle(self) -> None:
        if self._terminada or not self.existe():
            return
        try:
            tx, ty = self.objetivo()
            self._actualizar(tx, ty)
            ahora = time.monotonic()
            cx, cy = _posicion_cursor()
            if not self._cerrando and self.zigzag.alimentar(cx, cy, ahora):
                self.cerrar(rapido=True)
            if ahora - self._ultimo_topmost > 0.5:
                self._ultimo_topmost = ahora
                _forzar_topmost(self.hwnd)
        except tk.TclError:
            return
        self.root.after(INTERVALO_BURBUJA_MS, self._bucle)

    # --------------------------------------------------------------- cierre
    def cerrar(self, rapido: bool = False) -> None:
        """Se apaga con fundido al acabar su tiempo; con el zigzag, casi al instante."""
        if self._cerrando:
            return
        self._cerrando = True
        if self.existe():
            self.fundido(1.0, 0.0, 100 if rapido else 350, self._terminar)
        else:
            self._terminar()

    def _terminar(self) -> None:
        if self._terminada:
            return
        self._terminada = True
        self.destruir()
        self.al_cerrar()


class GestorBurbujas:
    """Cola de avisos: se muestran de uno en uno y respetan el 'no molestar'."""

    def __init__(self, app: "BarraJornada") -> None:
        self.app = app
        self.cola: list[tuple[str, float | None, bool]] = []
        self.actual: Burbuja | None = None
        self._bucle()

    def encolar(
        self, texto: str, segundos: float | None = None,
        urgente: bool = False, respetar_no_molestar: bool = True,
    ) -> None:
        if not texto.strip():
            return
        elemento = (texto, segundos, respetar_no_molestar)
        if urgente:
            self.cola.insert(0, elemento)
        else:
            self.cola.append(elemento)

    def _bucle(self) -> None:
        try:
            if self.actual is None and self.cola:
                texto, segundos, respetar = self.cola[0]
                ocupado = respetar and self.app.cfg["no_molestar"] and pantalla_ocupada()
                if not ocupado:
                    self.cola.pop(0)
                    self.actual = self._mostrar(texto, segundos)
        finally:
            self.app.root.after(INTERVALO_BURBUJAS_MS, self._bucle)

    def _mostrar(self, texto: str, segundos: float | None) -> Burbuja:
        cfg = self.app.cfg
        if segundos is None:
            segundos = duracion_aviso(texto, cfg["aviso_segundos"])
        modo = cfg["aviso_posicion"]
        if modo == "cursor":
            objetivo, limites = _posicion_cursor, area_monitor
        else:
            self.app.asomar(segundos + 1.0)
            objetivo, limites = self.app.punta_en_pantalla, self.app.limites_barra
        burbuja = Burbuja(
            self.app.root, texto, self.app.tema_ui, modo, objetivo, limites,
            segundos, self._al_cerrar,
        )
        self.app.root.after(150, lambda: self.app.diagnostico_burbuja(burbuja))
        return burbuja

    def _al_cerrar(self) -> None:
        self.actual = None


# --------------------------------------------------------------------------
# Celebraciones (módulos intercambiables)
# --------------------------------------------------------------------------
class _Lluvia(_VentanaFlotante):
    """Base de partículas a pantalla completa. Las subclases dan las imágenes."""

    TAMANOS = [28, 34, 40, 48, 56]

    def __init__(self, root: tk.Tk, segundos: float, al_terminar, sube: bool) -> None:
        super().__init__(root)
        self.al_terminar = al_terminar
        self.sube = sube
        self.ancho = user32.GetSystemMetrics(SM_CXSCREEN)
        self.alto = user32.GetSystemMetrics(SM_CYSCREEN)
        self.lienzo.configure(width=self.ancho, height=self.alto)
        self.mostrar(f"{self.ancho}x{self.alto}+0+0")
        self.cache: dict = {}
        self.particulas = [self._nueva(inicial=True) for _ in range(NUM_PARTICULAS)]
        self._animar()
        root.after(int(segundos * 1000), self._cerrar)

    def _elegir(self):
        """Devuelve (texto_alternativo, foto_o_None, tamaño)."""
        raise NotImplementedError

    def _nueva(self, inicial: bool = False) -> dict:
        alternativo, foto, tam = self._elegir()
        x = random.uniform(0, self.ancho)
        if inicial:
            y = random.uniform(0, self.alto)
        else:
            y = self.alto + tam if self.sube else -tam
        if foto is not None:
            item = self.lienzo.create_image(x, y, image=foto, anchor="center")
        else:
            item = self.lienzo.create_text(
                x, y, text=alternativo, font=("Segoe UI Emoji", tam // 2), fill="#ffd166"
            )
        return {
            "item": item, "foto": foto, "x": x, "y": y, "tam": tam,
            "vy": random.uniform(1.4, 3.6),
            "fase": random.uniform(0, 6.28),
            "amplitud": random.uniform(0.6, 2.2),
        }

    def _animar(self) -> None:
        if not self.existe():
            return
        for p in self.particulas:
            p["fase"] += 0.08
            p["y"] += -p["vy"] if self.sube else p["vy"]
            p["x"] += p["amplitud"] * math.sin(p["fase"])
            if self.sube and p["y"] < -p["tam"]:
                p["y"] = self.alto + p["tam"]
                p["x"] = random.uniform(0, self.ancho)
            elif not self.sube and p["y"] > self.alto + p["tam"]:
                p["y"] = -p["tam"]
                p["x"] = random.uniform(0, self.ancho)
            self.lienzo.coords(p["item"], p["x"], p["y"])
        _forzar_topmost(self.hwnd)
        self.root.after(INTERVALO_PARTICULAS_MS, self._animar)

    def _cerrar(self) -> None:
        self.destruir()
        self.al_terminar()


class CelebracionEmojis(_Lluvia):
    def __init__(self, root, segundos, al_terminar, emojis: list[str] | None = None):
        self.emojis = emojis or separar_emojis(EMOJIS_DEF)
        super().__init__(root, segundos, al_terminar, sube=True)

    def _elegir(self):
        tam = random.choice(self.TAMANOS)
        emoji = random.choice(self.emojis)
        clave = (emoji, tam)
        if clave not in self.cache:
            try:
                fuente = ImageFont.truetype(RUTA_FUENTE_EMOJI, tam)
                img = Image.new("RGBA", (int(tam * 1.6), int(tam * 1.6)), (0, 0, 0, 0))
                ImageDraw.Draw(img).text((tam * 0.1, 0), emoji, font=fuente, embedded_color=True)
                self.cache[clave] = ImageTk.PhotoImage(img)
            except Exception:
                self.cache[clave] = None
        return emoji, self.cache[clave], tam


class CelebracionImagen(_Lluvia):
    TAMANOS = [40, 52, 64, 80, 96]

    def __init__(self, root, segundos, al_terminar, ruta: str):
        # Se carga ANTES de crear la ventana: si falla, no queda nada abierto.
        self.base = Image.open(ruta).convert("RGBA")
        super().__init__(root, segundos, al_terminar, sube=False)

    def _elegir(self):
        tam = random.choice(self.TAMANOS)
        if tam not in self.cache:
            img = self.base.copy()
            img.thumbnail((tam, tam), Image.LANCZOS)
            # El color clave no admite semitransparencia: se binariza el alfa
            # para evitar un halo oscuro alrededor de la imagen.
            mascara = img.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
            lienzo = Image.new("RGB", img.size, _hex_a_rgb(COLOR_CLAVE))
            lienzo.paste(img.convert("RGB"), (0, 0), mascara)
            self.cache[tam] = ImageTk.PhotoImage(lienzo)
        return "🖼", self.cache[tam], tam


class CelebracionTexto(_VentanaFlotante):
    """Tarjeta centrada con el texto, fundido de entrada y salida."""

    def __init__(self, root, segundos, al_terminar, texto: str, subtitulo: str, tema: str):
        super().__init__(root)
        self.al_terminar = al_terminar
        self._saliendo = False
        self._terminada = False
        t = TEMAS_UI[tema]
        fuente1 = ("Segoe UI Semibold", 30)
        fuente2 = ("Segoe UI", 11)
        texto = texto.strip() or "¡Jornada completada!"
        w1, h1 = _medir_texto(self.lienzo, texto, fuente1, 900)
        w2, h2 = _medir_texto(self.lienzo, subtitulo, fuente2, 900)
        w = max(w1, w2) + 96
        h = h1 + h2 + 72
        self.lienzo.configure(width=w + 1, height=h + 1)
        _rect_redondeado(self.lienzo, 0, 0, w, h, 22, fill=t["tarjeta"], outline=t["borde"])
        self.lienzo.create_text(
            w // 2, 28, text=texto, font=fuente1, fill=t["fg"],
            anchor="n", width=900, justify="center",
        )
        y_linea = 28 + h1 + 10
        self.lienzo.create_rectangle(
            w // 2 - 24, y_linea, w // 2 + 24, y_linea + 3, fill=t["acento"], width=0
        )
        self.lienzo.create_text(
            w // 2, y_linea + 13, text=subtitulo, font=fuente2, fill=t["tenue"],
            anchor="n", width=900, justify="center",
        )
        ancho_p = user32.GetSystemMetrics(SM_CXSCREEN)
        alto_p = user32.GetSystemMetrics(SM_CYSCREEN)
        x = (ancho_p - w) // 2
        y = max(0, int(alto_p * 0.32) - h // 2)
        self.lienzo.configure(cursor="hand2")
        self.lienzo.bind("<Button-1>", lambda _e: self._fin())
        self.mostrar(f"{w + 1}x{h + 1}+{x}+{y}", alpha=0.0, clicable=True)
        self.fundido(0.0, 1.0, 400)
        root.after(int(max(1.0, segundos - 0.6) * 1000), self._salir)

    def _salir(self) -> None:
        if self._saliendo:
            return
        self._saliendo = True
        if self.existe():
            self.fundido(1.0, 0.0, 600, self._fin)
        else:
            self._fin()

    def _fin(self) -> None:
        """Cierre definitivo (al acabar el fundido o al hacer clic)."""
        if self._terminada:
            return
        self._terminada = True
        self.destruir()
        self.al_terminar()


# --------------------------------------------------------------------------
# Diálogo de configuración (pestañas, tema claro/oscuro y vista previa)
# --------------------------------------------------------------------------
CLAVES_VISUALES = (
    "estilo_trabajo", "estilo_descanso", "color_extra", "altura", "marcas_hora",
    "tema_barra", "tema_app", "atenuacion", "brillo", "brillo_modo", "saltos",
    "preaviso_s",
)
SIN_PALETA = "Elegir…"


class DialogoConfiguracion(tk.Toplevel):
    PESTANAS = ["General", "Barra", "Avisos", "Celebración", "Apariencia"]

    def __init__(
        self,
        padre: tk.Tk,
        inicio: str,
        cfg: dict,
        al_previsualizar=None,
        al_probar_celebracion=None,
        al_probar_aviso=None,
    ):
        super().__init__(padre)
        self.withdraw()
        self.resultado = None
        self.cfg = copy.deepcopy(cfg)
        self.al_previsualizar = al_previsualizar
        self.al_probar_celebracion = al_probar_celebracion
        self.al_probar_aviso = al_probar_aviso
        self.nombre_tema = tema_efectivo_app(cfg)
        self.t = TEMAS_UI[self.nombre_tema]
        self.estilos = {
            "trabajo": dict(cfg["estilo_trabajo"]),
            "descanso": dict(cfg["estilo_descanso"]),
        }
        self.color_extra = cfg["color_extra"]
        self.pintor = PintorBarra()
        self._ultima_visual = None
        self._foto_previa = None
        self._id_vista = None
        self.filas_hitos: list[dict] = []
        self._widgets: list[tuple] = []
        self.pestana_actual = "General"
        self._tema_sistema: str | None = None
        self._t_tema_sistema = 0.0

        self.title(f"{NOMBRE_APP} · v{VERSION}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=self.t["bg"], padx=16, pady=12)

        self._construir_pestanas()
        self._pagina_general(self.paginas["General"], inicio)
        self._pagina_barra(self.paginas["Barra"])
        self._pagina_avisos(self.paginas["Avisos"])
        self._pagina_celebracion(self.paginas["Celebración"])
        self._pagina_apariencia(self.paginas["Apariencia"])
        self._construir_pie()
        self._mostrar_pestana("General")
        self._pintar_colores()
        self._actualizar_etiqueta_curva()
        self._actualizar_etiqueta_atenuacion()
        self._refrescar_estados()

        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind_all("<MouseWheel>", self._rueda)

        self.update_idletasks()
        barra_titulo_oscura(_hwnd(self), self.nombre_tema == "oscuro")
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 5
        self.geometry(f"+{x}+{max(0, y)}")
        self.deiconify()
        self.entrada_inicio.focus_set()
        self.entrada_inicio.select_range(0, tk.END)
        self.grab_set()
        self._bucle_vista()

    # ------------------------------------------------------- widgets con tema
    def _tema(self, w, rol: str):
        """Registra un widget con su papel y le aplica los colores del tema."""
        self._widgets.append((w, rol))
        self._colorear(w, rol)
        return w

    def _colorear(self, w, rol: str) -> None:
        t = self.t
        try:
            if rol == "marco" or rol == "lienzo":
                w.configure(bg=t["bg"])
            elif rol == "linea":
                w.configure(bg=t["borde"])
            elif rol == "lbl":
                w.configure(bg=t["bg"], fg=t["fg"])
            elif rol == "tenue":
                w.configure(bg=t["bg"], fg=t["tenue"])
            elif rol == "aviso":
                w.configure(bg=t["bg"], fg=t["aviso"])
            elif rol == "entry":
                w.configure(
                    bg=t["campo"], fg=t["fg"], insertbackground=t["fg"],
                    highlightbackground=t["borde"], highlightcolor=t["acento"],
                    disabledbackground=t["bg"], disabledforeground=t["tenue"],
                    selectbackground=t["acento"], selectforeground="#ffffff",
                )
            elif rol == "opcion":                       # check y radio
                w.configure(
                    bg=t["bg"], fg=t["fg"], activebackground=t["bg"],
                    activeforeground=t["fg"], selectcolor=t["campo"],
                    disabledforeground=t["tenue"],
                )
            elif rol == "boton":
                w.configure(
                    bg=t["boton"], fg=t["fg"], activebackground=t["boton_activo"],
                    activeforeground=t["fg"], disabledforeground=t["tenue"],
                )
            elif rol == "principal":
                w.configure(
                    bg=t["acento"], fg="#ffffff", activebackground=t["acento"],
                    activeforeground="#ffffff",
                )
            elif rol == "spin":
                w.configure(
                    bg=t["campo"], fg=t["fg"], buttonbackground=t["boton"],
                    insertbackground=t["fg"], highlightbackground=t["borde"],
                    highlightcolor=t["acento"], disabledbackground=t["bg"],
                    disabledforeground=t["tenue"],
                )
            elif rol == "desplegable":
                w.configure(
                    bg=t["boton"], fg=t["fg"], activebackground=t["boton_activo"],
                    activeforeground=t["fg"],
                )
                w["menu"].configure(
                    bg=t["campo"], fg=t["fg"], activebackground=t["acento"],
                    activeforeground="#ffffff",
                )
            elif rol == "escala":
                w.configure(
                    bg=t["acento"], troughcolor=t["borde"], activebackground=t["acento"]
                )
            elif rol == "color":
                w.configure(highlightbackground=t["borde"])
        except tk.TclError:
            pass

    def _aplicar_tema(self, nombre: str) -> None:
        """Repinta el diálogo entero con otro tema, sin cerrarlo."""
        self.nombre_tema = nombre
        self.t = TEMAS_UI[nombre]
        self.configure(bg=self.t["bg"])
        vivos = []
        for w, rol in self._widgets:
            try:
                if w.winfo_exists():
                    self._colorear(w, rol)
                    vivos.append((w, rol))
            except tk.TclError:
                pass
        self._widgets = vivos
        self._mostrar_pestana(self.pestana_actual)
        self._pintar_colores()
        self._refrescar_estados()
        barra_titulo_oscura(_hwnd(self), nombre == "oscuro")

    def _tema_deseado(self, preferido: str) -> str:
        """Resuelve 'sistema' consultando Windows cada pocos segundos."""
        if preferido != "sistema":
            self._tema_sistema = None
            return preferido
        ahora = time.monotonic()
        if self._tema_sistema is None or ahora - self._t_tema_sistema >= INTERVALO_TEMA_S:
            self._tema_sistema = tema_sistema_apps()
            self._t_tema_sistema = ahora
        return self._tema_sistema

    def _lbl(self, padre, texto, tenue=False, negrita=False, **kw):
        w = tk.Label(padre, text=texto, font=FUENTE_NEGRITA if negrita else FUENTE, **kw)
        return self._tema(w, "tenue" if tenue else "lbl")

    def _titulo(self, padre, texto, fila) -> int:
        self._lbl(padre, texto, negrita=True).grid(
            row=fila, column=0, columnspan=4, sticky="w", pady=(12, 3)
        )
        return fila + 1

    def _pista(self, padre, texto, fila, columnspan=4) -> int:
        self._lbl(padre, texto, tenue=True, justify="left", wraplength=560).grid(
            row=fila, column=0, columnspan=columnspan, sticky="w", pady=(0, 2)
        )
        return fila + 1

    def _marco(self, padre):
        return self._tema(tk.Frame(padre), "marco")

    def _linea(self, padre, alto=1):
        return self._tema(tk.Frame(padre, height=alto), "linea")

    def _entry(self, padre, ancho, texto="", **kw):
        e = tk.Entry(
            padre, width=ancho, relief="flat", highlightthickness=1, font=FUENTE, **kw
        )
        e.insert(0, texto)
        return self._tema(e, "entry")

    def _check(self, padre, texto, var, cmd=None):
        w = tk.Checkbutton(
            padre, text=texto, variable=var, command=cmd or self._refrescar_estados,
            highlightthickness=0, font=FUENTE, anchor="w",
        )
        return self._tema(w, "opcion")

    def _radio(self, padre, texto, var, valor, cmd=None):
        w = tk.Radiobutton(
            padre, text=texto, variable=var, value=valor,
            command=cmd or self._refrescar_estados,
            highlightthickness=0, font=FUENTE, anchor="w",
        )
        return self._tema(w, "opcion")

    def _boton(self, padre, texto, cmd, ancho=None, principal=False):
        w = tk.Button(
            padre, text=texto, command=cmd, width=ancho, relief="flat", bd=0,
            padx=10, pady=3, font=FUENTE, cursor="hand2", highlightthickness=0,
        )
        return self._tema(w, "principal" if principal else "boton")

    def _spin(self, padre, valor, desde, hasta, ancho=4):
        var = tk.StringVar(value=str(valor))
        s = tk.Spinbox(
            padre, from_=desde, to=hasta, textvariable=var, width=ancho,
            relief="flat", highlightthickness=1, font=FUENTE, justify="center",
        )
        var.set(str(valor))           # Spinbox pisa la variable con from_ al crearse
        s.var = var
        return self._tema(s, "spin")

    def _desplegable(self, padre, var, opciones, cmd=None, ancho=12):
        om = tk.OptionMenu(
            padre, var, *opciones, command=(lambda _v: cmd()) if cmd else None
        )
        om.configure(
            relief="flat", highlightthickness=0, bd=0, width=ancho, font=FUENTE,
            anchor="w", cursor="hand2",
        )
        om["menu"].configure(bd=0, font=FUENTE)
        return self._tema(om, "desplegable")

    def _escala(self, padre, desde, hasta, var, cmd, largo=260):
        w = tk.Scale(
            padre, from_=desde, to=hasta, orient="horizontal", showvalue=False,
            variable=var, command=cmd, length=largo, sliderlength=22, width=10,
            highlightthickness=0, bd=0, sliderrelief="flat",
        )
        return self._tema(w, "escala")

    def _boton_color(self, padre, obtener, fijar):
        b = tk.Button(
            padre, width=9, relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 8),
            highlightthickness=1,
        )

        def elegir() -> None:
            _, codigo = colorchooser.askcolor(color=obtener(), parent=self, title="Color")
            if codigo:
                fijar(codigo.lower())
                self._pintar_colores()

        b.configure(command=elegir)
        return self._tema(b, "color")

    # -------------------------------------------------------------- pestañas
    def _construir_pestanas(self) -> None:
        cabecera = self._marco(self)
        cabecera.grid(row=0, column=0, sticky="we")
        self._linea(self).grid(row=1, column=0, sticky="we")
        contenedor = self._marco(self)
        contenedor.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.paginas: dict[str, tk.Frame] = {}
        self.pestanas: dict[str, tuple] = {}
        for i, nombre in enumerate(self.PESTANAS):
            marco = self._marco(cabecera)
            marco.grid(row=0, column=i, padx=(0, 4))
            etiqueta = tk.Label(marco, text=nombre, font=FUENTE, padx=8, pady=4, cursor="hand2")
            etiqueta.pack()
            linea = tk.Frame(marco, height=2)
            linea.pack(fill="x")
            for w in (marco, etiqueta):
                w.bind("<Button-1>", lambda _e, n=nombre: self._mostrar_pestana(n))
            self.pestanas[nombre] = (etiqueta, linea)
            pagina = self._marco(contenedor)
            pagina.grid(row=0, column=0, sticky="nsew")
            self.paginas[nombre] = pagina

    def _mostrar_pestana(self, nombre: str) -> None:
        self.pestana_actual = nombre
        for n, (etiqueta, linea) in self.pestanas.items():
            activa = n == nombre
            etiqueta.configure(bg=self.t["bg"], fg=self.t["fg"] if activa else self.t["tenue"])
            linea.configure(bg=self.t["acento"] if activa else self.t["bg"])
        self.paginas[nombre].tkraise()

    # --------------------------------------------------------------- General
    def _pagina_general(self, p, inicio: str) -> None:
        c = self.cfg
        p.columnconfigure(1, weight=1)
        self._lbl(p, "Hora de inicio").grid(row=0, column=0, sticky="w")
        self.entrada_inicio = self._entry(p, 10, inicio, justify="center")
        self.entrada_inicio.grid(row=0, column=1, sticky="e", pady=3)
        self._lbl(p, "Trabajo efectivo (h:mm)").grid(row=1, column=0, sticky="w")
        self.entrada_duracion = self._entry(
            p, 10, formatear_hhmm(c["duracion_min"]), justify="center"
        )
        self.entrada_duracion.grid(row=1, column=1, sticky="e", pady=3)

        fila = self._titulo(p, "Avance de la barra", 2)
        self.v_progreso = tk.StringVar(value=c["progreso"])
        self._radio(p, "Real (ritmo constante)", self.v_progreso, "real").grid(
            row=fila, column=0, columnspan=2, sticky="w"
        )
        fila += 1
        self._radio(
            p, "Equilibrado (lento al principio, rápido al final)", self.v_progreso, "curva"
        ).grid(row=fila, column=0, columnspan=2, sticky="w")
        fila += 1
        self.label_curva = self._lbl(p, "")
        self.label_curva.grid(row=fila, column=0, columnspan=2, sticky="w", pady=(4, 0))
        fila += 1
        curva = c["curva"] or curva_recomendada(c["duracion_min"])
        self.v_curva = tk.IntVar(value=ORDEN_CURVAS.index(curva))
        self.deslizador = self._escala(
            p, 0, len(ORDEN_CURVAS) - 1, self.v_curva, self._actualizar_etiqueta_curva
        )
        self.deslizador.grid(row=fila, column=0, columnspan=2, sticky="we")
        fila += 1
        marcas = self._marco(p)
        marcas.grid(row=fila, column=0, columnspan=2, sticky="we")
        for i, nombre in enumerate(ORDEN_CURVAS):
            marcas.columnconfigure(i, weight=1)
            anclaje = "w" if i == 0 else ("e" if i == len(ORDEN_CURVAS) - 1 else "")
            self._tema(tk.Label(marcas, text=nombre, font=("Segoe UI", 7)), "tenue").grid(
                row=0, column=i, sticky=anclaje
            )
        fila += 1

        fila = self._titulo(p, "Al completar la jornada", fila)
        self.v_completar = tk.StringVar(value=c["al_completar"])
        self._radio(p, "Celebrar y cerrar la barra", self.v_completar, "cerrar").grid(
            row=fila, column=0, columnspan=2, sticky="w"
        )
        fila += 1
        self._radio(
            p, "Celebrar y seguir contando horas extra", self.v_completar, "extra"
        ).grid(row=fila, column=0, columnspan=2, sticky="w")
        fila += 1
        self.label_extra = self._lbl(p, "Color de las horas extra")
        self.label_extra.grid(row=fila, column=0, sticky="w", padx=(22, 0))
        self.boton_extra = self._boton_color(
            p, lambda: self.color_extra, lambda c_: setattr(self, "color_extra", c_)
        )
        self.boton_extra.grid(row=fila, column=1, sticky="e", pady=2)
        fila += 1

        fila = self._titulo(p, "Inactividad", fila)
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=2, sticky="w")
        self.v_inactividad = tk.BooleanVar(value=c["inactividad"])
        self._check(marco, "Descanso automático tras", self.v_inactividad).pack(side="left")
        self.spin_inactividad = self._spin(marco, c["inactividad_min"], 1, 240)
        self.spin_inactividad.pack(side="left", padx=4)
        self._lbl(marco, "min sin ratón ni teclado").pack(side="left")
        fila += 1
        self._pista(
            p, "Cuenta como descanso desde tu último movimiento. Si no lo era "
               "(un vídeo, una reunión), se deshace desde el icono de la bandeja.",
            fila, columnspan=2,
        )

    def _actualizar_etiqueta_curva(self, *_a) -> None:
        nombre = ORDEN_CURVAS[self.v_curva.get()]
        self.label_curva.configure(text=f"Intensidad de la curva: {nombre}")

    # ----------------------------------------------------------------- Barra
    def _pagina_barra(self, p) -> None:
        c = self.cfg
        fila = self._titulo(p, "Visibilidad", 0)
        self.v_visibilidad = tk.StringVar(value=c["visibilidad"])
        self._radio(p, "Siempre visible", self.v_visibilidad, "siempre").grid(
            row=fila, column=0, columnspan=4, sticky="w"
        )
        fila += 1
        self._radio(p, "Oculta; aparece al pasar el ratón por abajo",
                    self.v_visibilidad, "auto").grid(row=fila, column=0, columnspan=4, sticky="w")
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self._radio(marco, "Al pasar el ratón + asomar cada", self.v_visibilidad,
                    "asomar").pack(side="left")
        self.spin_asomar_cada = self._spin(marco, c["asomar_cada_min"], 1, 240)
        self.spin_asomar_cada.pack(side="left", padx=4)
        self._lbl(marco, "min durante").pack(side="left")
        self.spin_asomar_seg = self._spin(marco, c["asomar_seg"], 1, 120)
        self.spin_asomar_seg.pack(side="left", padx=4)
        self._lbl(marco, "s").pack(side="left")
        fila += 1
        self.radio_vis_salto = self._radio(
            p, "Al pasar el ratón + aparecer con cada salto", self.v_visibilidad, "salto"
        )
        self.radio_vis_salto.grid(row=fila, column=0, columnspan=4, sticky="w")
        fila += 1
        fila = self._pista(
            p, "Aparece unos segundos antes de cada salto y se esconde al terminar. "
               "Necesita el avance por saltos (pestaña Apariencia). Recomendado con "
               "saltos largos, de 10 min o más: con rangos cortos aparecerá cada dos por tres.",
            fila,
        )

        fila = self._titulo(p, "Tamaño", fila)
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self._lbl(marco, "Altura").pack(side="left")
        self.spin_altura = self._spin(marco, c["altura"], ALTURA_MIN, ALTURA_MAX, 3)
        self.spin_altura.pack(side="left", padx=4)
        self._lbl(marco, "px").pack(side="left", padx=(0, 18))
        self.v_marcas = tk.BooleanVar(value=c["marcas_hora"])
        self._check(marco, "Marca por cada hora trabajada", self.v_marcas).pack(side="left")
        fila += 1

        self.v_estilo: dict[str, tk.StringVar] = {}
        self.v_paleta: dict[str, tk.StringVar] = {}
        self.botones_color: dict[tuple[str, str], tk.Button] = {}
        etiquetas_estilo = list(ESTILOS_COLOR.values())
        for modo, titulo in (("trabajo", "Color en trabajo"), ("descanso", "Color en descanso")):
            fila = self._titulo(p, titulo, fila)
            marco = self._marco(p)
            marco.grid(row=fila, column=0, columnspan=4, sticky="w")
            self._lbl(marco, "Estilo").pack(side="left")
            var = tk.StringVar(value=ESTILOS_COLOR[self.estilos[modo]["tipo"]])
            self.v_estilo[modo] = var
            self._desplegable(
                marco, var, etiquetas_estilo, lambda m=modo: self._cambiar_estilo(m), 12
            ).pack(side="left", padx=(4, 14))
            self._lbl(marco, "Paleta").pack(side="left")
            var_p = tk.StringVar(value=SIN_PALETA)
            self.v_paleta[modo] = var_p
            self._desplegable(
                marco, var_p, list(PALETAS), lambda m=modo: self._aplicar_paleta(m), 10
            ).pack(side="left", padx=4)
            fila += 1
            marco = self._marco(p)
            marco.grid(row=fila, column=0, columnspan=4, sticky="w", pady=(4, 0))
            for n in ("c1", "c2"):
                self._lbl(marco, "Color 1" if n == "c1" else "Color 2").pack(side="left")
                boton = self._boton_color(
                    marco,
                    lambda m=modo, n=n: self.estilos[m][n],
                    lambda v, m=modo, n=n: self.estilos[m].__setitem__(n, v),
                )
                boton.pack(side="left", padx=(4, 14))
                self.botones_color[(modo, n)] = boton
            fila += 1

        self._boton(p, "Restaurar colores", self._restaurar_colores).grid(
            row=fila, column=0, sticky="w", pady=(10, 0)
        )
        fila += 1
        fila = self._titulo(p, "Vista previa", fila)
        borde = self._linea(p)
        borde.grid(row=fila, column=0, columnspan=4, sticky="w")
        self.lienzo_previa = self._tema(
            tk.Canvas(borde, width=360, height=12, highlightthickness=0, bd=0), "lienzo"
        )
        self.lienzo_previa.pack(padx=1, pady=1)
        self._item_previa = self.lienzo_previa.create_image(0, 0, anchor="nw")

    def _cambiar_estilo(self, modo: str) -> None:
        inverso = {v: k for k, v in ESTILOS_COLOR.items()}
        self.estilos[modo]["tipo"] = inverso.get(self.v_estilo[modo].get(), "plano")
        self._pintar_colores()

    def _aplicar_paleta(self, modo: str) -> None:
        nombre = self.v_paleta[modo].get()
        if nombre in PALETAS:
            c1, c2 = PALETAS[nombre]
            self.estilos[modo]["c1"], self.estilos[modo]["c2"] = c1, c2
            if self.estilos[modo]["tipo"] == "plano":
                self.estilos[modo]["tipo"] = "degradado"
                self.v_estilo[modo].set(ESTILOS_COLOR["degradado"])
        self.v_paleta[modo].set(SIN_PALETA)
        self._pintar_colores()

    def _restaurar_colores(self) -> None:
        base = config_por_defecto()
        for modo in ("trabajo", "descanso"):
            self.estilos[modo] = dict(base[f"estilo_{modo}"])
            self.v_estilo[modo].set(ESTILOS_COLOR[self.estilos[modo]["tipo"]])
        self.color_extra = base["color_extra"]
        self._pintar_colores()

    def _pintar_colores(self) -> None:
        t = self.t
        for (modo, n), boton in self.botones_color.items():
            color = self.estilos[modo][n]
            if n == "c2" and self.estilos[modo]["tipo"] == "plano":
                boton.configure(state="disabled", bg=t["boton"], text="—",
                                disabledforeground=t["tenue"])
            else:
                boton.configure(state="normal", bg=color, activebackground=color,
                                fg=color_contraste(color), text=color)
        self.boton_extra.configure(
            bg=self.color_extra, activebackground=self.color_extra,
            fg=color_contraste(self.color_extra), text=self.color_extra,
        )

    # ---------------------------------------------------------------- Avisos
    def _pagina_avisos(self, p) -> None:
        c = self.cfg
        t = self.t
        self.v_avisos = tk.BooleanVar(value=c["avisos"])
        self._check(p, "Mostrar avisos de hito en una burbuja",
                    self.v_avisos).grid(row=0, column=0, columnspan=4, sticky="w", pady=(4, 0))
        fila = self._pista(
            p, "Valor: 25 para un % de la jornada; 7:30 o 0:30 para tiempos. "
               "Los % cuentan trabajo real, no lo que se ve con la curva.", 1,
        )

        marco = self._linea(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="we", pady=(4, 0))
        self.marco_hitos = marco
        self.lienzo_hitos = self._tema(
            tk.Canvas(marco, highlightthickness=0, bd=0, height=170, width=520), "lienzo"
        )
        barra = tk.Scrollbar(marco, orient="vertical", command=self.lienzo_hitos.yview)
        self.lienzo_hitos.configure(yscrollcommand=barra.set)
        self.interior = self._marco(self.lienzo_hitos)
        self.lienzo_hitos.create_window((0, 0), window=self.interior, anchor="nw")
        self.interior.bind(
            "<Configure>",
            lambda _e: self.lienzo_hitos.configure(scrollregion=self.lienzo_hitos.bbox("all")),
        )
        self.lienzo_hitos.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        barra.pack(side="right", fill="y")
        for i, texto in enumerate(("Tipo", "Valor", "Mensaje")):
            self._lbl(self.interior, texto, tenue=True).grid(
                row=0, column=i, sticky="w", padx=4, pady=(4, 2)
            )
        for h in c["hitos"]:
            self._anadir_fila_hito(h)
        fila += 1

        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._boton(marco, "+ Añadir hito", lambda: self._anadir_fila_hito()).pack(side="left")
        self._boton(marco, "Frases por defecto", self._hitos_por_defecto).pack(side="left", padx=6)
        self._boton(marco, "Probar aviso", self._probar_aviso).pack(side="left")
        fila += 1
        fila = self._pista(
            p, "Varias frases separadas con | → cada día sale una al azar.   "
               "Variables: {restante} {trabajado} {salida} {porcentaje}", fila,
        )

        fila = self._titulo(p, "Dónde y cuánto", fila)
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self.v_aviso_posicion = tk.StringVar(value=c["aviso_posicion"])
        self._lbl(marco, "Mostrar").pack(side="left", padx=(0, 6))
        self._radio(marco, "Junto al cursor", self.v_aviso_posicion, "cursor").pack(side="left", padx=(0, 10))
        self._radio(marco, "En la punta de la barra", self.v_aviso_posicion, "barra").pack(side="left")
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self.v_aviso_auto = tk.BooleanVar(value=c["aviso_segundos"] == 0)
        self._lbl(marco, "Duración").pack(side="left", padx=(0, 6))
        self._radio(marco, "Automática según el texto", self.v_aviso_auto, True).pack(side="left", padx=(0, 10))
        self._radio(marco, "Fija", self.v_aviso_auto, False).pack(side="left")
        self.spin_aviso_seg = self._spin(marco, c["aviso_segundos"] or 6, 2, 60)
        self.spin_aviso_seg.pack(side="left", padx=4)
        self._lbl(marco, "s").pack(side="left")
        fila += 1
        fila = self._pista(
            p, "Los avisos no se pueden pulsar: los clics pasan a la ventana de debajo. "
               "Para quitar uno antes de tiempo, sacude el ratón a izquierda y derecha "
               "(→ ← → ←). Automática: 4 s + 0,3 s por palabra, entre 5 y 10 s.",
            fila,
        )

        fila = self._titulo(p, "Comportamiento", fila)
        self.v_no_molestar = tk.BooleanVar(value=c["no_molestar"])
        self._check(
            p, "No molestar: aplazar avisos y celebración si hay algo a pantalla completa",
            self.v_no_molestar,
        ).grid(row=fila, column=0, columnspan=4, sticky="w")
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self.v_descanso_largo = tk.BooleanVar(value=c["descanso_largo"])
        self._check(marco, "Aviso de descanso largo tras", self.v_descanso_largo).pack(side="left")
        self.spin_descanso_largo = self._spin(marco, c["descanso_largo_min"], 1, 480)
        self.spin_descanso_largo.pack(side="left", padx=4)
        self._lbl(marco, "min").pack(side="left")
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w", pady=(2, 0))
        self._lbl(marco, "Mensaje").pack(side="left", padx=(22, 6))
        self.entrada_descanso_largo = self._entry(marco, 52, c["descanso_largo_msg"])
        self.entrada_descanso_largo.pack(side="left")
        fila += 1
        self._pista(p, "Variable extra para este mensaje: {descanso}", fila)

    def _anadir_fila_hito(self, hito: dict | None = None) -> None:
        hito = hito or {"tipo": "porcentaje", "valor": "", "mensaje": ""}
        v_tipo = tk.StringVar(value=TIPOS_HITO[hito["tipo"]])
        desplegable = self._desplegable(self.interior, v_tipo, list(TIPOS_HITO.values()), ancho=9)
        valor = self._entry(self.interior, 6, hito["valor"], justify="center")
        mensaje = self._entry(self.interior, 46, hito["mensaje"])
        fila: dict = {"tipo": v_tipo, "valor": valor, "mensaje": mensaje}
        quitar = self._boton(self.interior, "✕", lambda: self._quitar_fila_hito(fila))
        quitar.configure(padx=6)
        fila["widgets"] = (desplegable, valor, mensaje, quitar)
        self.filas_hitos.append(fila)
        self._recolocar_hitos()
        if hito["valor"] == "":
            self.after(30, lambda: self.lienzo_hitos.yview_moveto(1.0))
            valor.focus_set()

    def _quitar_fila_hito(self, fila: dict) -> None:
        for w in fila["widgets"]:
            w.destroy()
        self.filas_hitos.remove(fila)
        self._recolocar_hitos()

    def _recolocar_hitos(self) -> None:
        for i, fila in enumerate(self.filas_hitos, start=1):
            for col, w in enumerate(fila["widgets"]):
                w.grid(row=i, column=col, sticky="w", padx=4, pady=2)
        # La tabla siempre tan ancha como sus columnas (las fuentes varían).
        self.interior.update_idletasks()
        self.lienzo_hitos.configure(width=self.interior.winfo_reqwidth())

    def _hitos_por_defecto(self) -> None:
        for fila in list(self.filas_hitos):
            self._quitar_fila_hito(fila)
        for h in HITOS_DEF:
            self._anadir_fila_hito(dict(h))
        self.lienzo_hitos.yview_moveto(0.0)

    def _rueda(self, evento) -> None:
        """La rueda solo desplaza la tabla de hitos cuando el ratón está encima."""
        try:
            debajo = self.winfo_containing(evento.x_root, evento.y_root)
        except (tk.TclError, KeyError):
            return
        raiz = str(self.marco_hitos)
        ruta = str(debajo) if debajo is not None else ""
        if ruta == raiz or ruta.startswith(raiz + "."):
            self.lienzo_hitos.yview_scroll(int(-evento.delta / 120), "units")

    def _probar_aviso(self) -> None:
        if self.al_probar_aviso:
            _, cfg = self._recoger(estricto=False)
            self.al_probar_aviso(cfg)

    # ----------------------------------------------------------- Celebración
    def _pagina_celebracion(self, p) -> None:
        c = self.cfg
        fila = self._titulo(p, "Estilo de la celebración", 0)
        self.v_celebracion = tk.StringVar(value=c["celebracion"])
        self._radio(p, "Emojis (lluvia de emojis, la clásica)", self.v_celebracion,
                    "emojis").grid(row=fila, column=0, columnspan=3, sticky="w")
        fila += 1
        self._radio(p, "Emojis propios", self.v_celebracion, "emojis_propios").grid(
            row=fila, column=0, sticky="w"
        )
        self.entrada_emojis = self._entry(p, 34, c["emojis_propios"])
        self.entrada_emojis.grid(row=fila, column=1, sticky="w", padx=6, pady=2)
        fila += 1
        self._radio(p, "Imagen PNG", self.v_celebracion, "imagen").grid(
            row=fila, column=0, sticky="w"
        )
        self.entrada_imagen = self._entry(p, 34, c["imagen_ruta"])
        self.entrada_imagen.grid(row=fila, column=1, sticky="w", padx=6, pady=2)
        self._boton(p, "Examinar…", self._elegir_imagen).grid(row=fila, column=2, sticky="w")
        fila += 1
        self._radio(p, "Texto", self.v_celebracion, "texto").grid(row=fila, column=0, sticky="w")
        self.entrada_texto = self._entry(p, 34, c["texto_celebracion"])
        self.entrada_texto.grid(row=fila, column=1, sticky="w", padx=6, pady=2)
        fila += 1
        self._radio(p, "Minimalista (una burbuja discreta, donde salgan los avisos, con el texto de arriba)",
                    self.v_celebracion, "minimalista").grid(row=fila, column=0, columnspan=3, sticky="w")
        fila += 1
        self._radio(p, "Ninguna", self.v_celebracion, "ninguna").grid(
            row=fila, column=0, columnspan=3, sticky="w"
        )
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self._lbl(marco, "Duración").pack(side="left")
        self.spin_segundos = self._spin(marco, c["segundos_celebracion"], 2, 60)
        self.spin_segundos.pack(side="left", padx=4)
        self._lbl(marco, "s").pack(side="left", padx=(0, 18))
        self._boton(marco, "Probar celebración", self._probar_celebracion).pack(side="left")
        fila += 1
        self._pista(
            p, "Emojis propios: escríbelos seguidos o separados por espacios. "
               "Imagen: mejor un PNG con fondo transparente; se usa en varios tamaños. "
               "Si la imagen no se puede abrir, se usa la lluvia de emojis.",
            fila, columnspan=3,
        )

    def _elegir_imagen(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self, title="Imagen para la celebración",
            filetypes=[("Imágenes", "*.png *.gif *.jpg *.jpeg *.webp *.bmp"), ("Todos", "*.*")],
        )
        if ruta:
            self.entrada_imagen.delete(0, tk.END)
            self.entrada_imagen.insert(0, os.path.normpath(ruta))
            self.v_celebracion.set("imagen")

    def _probar_celebracion(self) -> None:
        if self.al_probar_celebracion:
            _, cfg = self._recoger(estricto=False)
            self.al_probar_celebracion(cfg)

    # ------------------------------------------------------------ Apariencia
    def _pagina_apariencia(self, p) -> None:
        c = self.cfg
        fila = self._titulo(p, "Tema de la aplicación", 0)
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w")
        self.v_tema_app = tk.StringVar(value=c["tema_app"])
        for valor, texto in (("sistema", "Sistema"), ("claro", "Claro"), ("oscuro", "Oscuro")):
            self._radio(marco, texto, self.v_tema_app, valor).pack(side="left", padx=(0, 12))
        fila += 1
        fila = self._pista(p, "Afecta a este diálogo, al tooltip y a los avisos. "
                              "Se aplica al momento.", fila)

        fila = self._titulo(p, "Tema de la barra", fila)
        self.v_tema_barra = tk.StringVar(value=c["tema_barra"])
        for valor, texto in (
            ("app", "Igual que la app"),
            ("sistema", "Sistema (sigue a la barra de tareas de Windows)"),
            ("claro", "Claro"),
            ("oscuro", "Oscuro (colores un poco atenuados)"),
            ("ninguno", "Sin tema (colores tal cual, como en la v1)"),
        ):
            self._radio(p, texto, self.v_tema_barra, valor).grid(
                row=fila, column=0, columnspan=4, sticky="w"
            )
            fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self._lbl(marco, "Atenuación en oscuro").pack(side="left")
        self.v_atenuacion = tk.IntVar(value=c["atenuacion"])
        self._escala(marco, 0, 40, self.v_atenuacion, self._actualizar_etiqueta_atenuacion,
                     largo=180).pack(side="left", padx=8)
        self.label_atenuacion = self._lbl(marco, "")
        self.label_atenuacion.pack(side="left")
        fila += 1

        fila = self._titulo(p, "Brillo de la punta", fila)
        self.v_brillo = tk.BooleanVar(value=c["brillo"])
        self._check(p, "Brillo al avanzar (estela tipo cometa)", self.v_brillo).grid(
            row=fila, column=0, columnspan=4, sticky="w"
        )
        fila += 1
        self.v_brillo_modo = tk.StringVar(value=c["brillo_modo"])
        self.radios_brillo = []
        r = self._radio(p, "Continuo (en cada píxel que avanza)", self.v_brillo_modo, "continuo")
        r.grid(row=fila, column=0, columnspan=4, sticky="w", padx=(22, 0))
        self.radios_brillo.append(r)
        fila += 1
        self.spins_brillo = {}
        for modo, desde, hasta, unidad, cmin, cmax in (
            ("pixeles", 1, 2000, "píxeles", "brillo_px_min", "brillo_px_max"),
            ("minutos", 1, 240, "minutos", "brillo_min_min", "brillo_min_max"),
        ):
            marco = self._marco(p)
            marco.grid(row=fila, column=0, columnspan=4, sticky="w", padx=(22, 0))
            r = self._radio(marco, "Cada", self.v_brillo_modo, modo)
            r.pack(side="left")
            self.radios_brillo.append(r)
            s1 = self._spin(marco, c[cmin], desde, hasta, 5)
            s1.pack(side="left", padx=4)
            self._lbl(marco, "a").pack(side="left")
            s2 = self._spin(marco, c[cmax], desde, hasta, 5)
            s2.pack(side="left", padx=4)
            self._lbl(marco, unidad).pack(side="left")
            self.spins_brillo[modo] = (s1, s2)
            fila += 1
        self.v_saltos = tk.BooleanVar(value=c["saltos"])
        self.check_saltos = self._check(
            p, "Avance por saltos: la barra espera y avanza de golpe con cada destello",
            self.v_saltos,
        )
        self.check_saltos.grid(row=fila, column=0, columnspan=4, sticky="w", padx=(22, 0), pady=(4, 0))
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w", padx=(44, 0))
        self.label_preaviso = self._lbl(marco, "Preaviso: la cabeza brilla")
        self.label_preaviso.pack(side="left")
        self.spin_preaviso = self._spin(marco, c["preaviso_s"], 0, 5, 3)
        self.spin_preaviso.pack(side="left", padx=4)
        self.label_preaviso2 = self._lbl(marco, "s antes de saltar")
        self.label_preaviso2.pack(side="left")
        fila += 1
        marco = self._marco(p)
        marco.grid(row=fila, column=0, columnspan=4, sticky="w", padx=(44, 0))
        self.label_recta = self._lbl(marco, "Recta final: avance normal los últimos")
        self.label_recta.pack(side="left")
        self.spin_recta = self._spin(marco, c["recta_final_min"], 0, 120, 4)
        self.spin_recta.pack(side="left", padx=4)
        self.label_recta2 = self._lbl(marco, "min (0 = nunca)")
        self.label_recta2.pack(side="left")
        fila += 1
        self._pista(p, "Con dos valores distintos, cada pulso elige uno al azar dentro "
                       "de ese rango. Con dos iguales, el intervalo es fijo. "
                       "Los saltos necesitan «Cada … píxeles» o «Cada … minutos»; cuanto "
                       "más tiempo se acumula, más rápido corre la punta.", fila)

    def _actualizar_etiqueta_atenuacion(self, *_a) -> None:
        self.label_atenuacion.configure(text=f"{self.v_atenuacion.get()} %")

    # ------------------------------------------------------------------- pie
    def _construir_pie(self) -> None:
        t = self.t
        self._linea(self).grid(row=3, column=0, sticky="we", pady=(12, 8))
        pie = self._marco(self)
        pie.grid(row=4, column=0, sticky="we")
        pie.columnconfigure(1, weight=1)
        self.v_recordar = tk.BooleanVar(value=False)
        self._check(pie, "Recordar esta configuración para los próximos días",
                    self.v_recordar, cmd=lambda: None).grid(row=0, column=0, columnspan=4, sticky="w")
        self.aviso = self._tema(tk.Label(pie, text="", font=FUENTE), "aviso")
        self.aviso.grid(row=1, column=0, columnspan=4, sticky="w")
        self._lbl(pie, f"v{VERSION}", tenue=True).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._boton(pie, "Cancelar", self._cancelar, 10).grid(
            row=2, column=2, sticky="e", padx=(0, 6), pady=(8, 0)
        )
        self._boton(pie, "Aceptar", self._aceptar, 10, principal=True).grid(
            row=2, column=3, sticky="e", pady=(8, 0)
        )

    # --------------------------------------------------------------- estados
    def _refrescar_estados(self) -> None:
        def estado(w, activo: bool) -> None:
            try:
                w.configure(state="normal" if activo else "disabled")
            except tk.TclError:
                pass

        curva = self.v_progreso.get() == "curva"
        estado(self.deslizador, curva)
        self.label_curva.configure(fg=self.t["fg"] if curva else self.t["tenue"])

        extra = self.v_completar.get() == "extra"
        estado(self.boton_extra, extra)
        self.label_extra.configure(fg=self.t["fg"] if extra else self.t["tenue"])

        estado(self.spin_inactividad, self.v_inactividad.get())
        asomar = self.v_visibilidad.get() == "asomar"
        estado(self.spin_asomar_cada, asomar)
        estado(self.spin_asomar_seg, asomar)
        estado(self.spin_descanso_largo, self.v_descanso_largo.get())
        estado(self.entrada_descanso_largo, self.v_descanso_largo.get())

        brillo = self.v_brillo.get()
        for r in self.radios_brillo:
            estado(r, brillo)
        for modo, spins in self.spins_brillo.items():
            for s in spins:
                estado(s, brillo and self.v_brillo_modo.get() == modo)
        saltos_posible = brillo and self.v_brillo_modo.get() != "continuo"
        estado(self.check_saltos, saltos_posible)
        saltos = saltos_posible and self.v_saltos.get()
        for w in (self.spin_preaviso, self.spin_recta):
            estado(w, saltos)
        for w in (self.label_preaviso, self.label_preaviso2, self.label_recta, self.label_recta2):
            w.configure(fg=self.t["fg"] if saltos else self.t["tenue"])
        estado(self.radio_vis_salto, saltos)
        if not saltos and self.v_visibilidad.get() == "salto":
            self.v_visibilidad.set("auto")      # sin saltos no hay con qué aparecer
        estado(self.spin_aviso_seg, not self.v_aviso_auto.get())

    # --------------------------------------------------------------- recoger
    def _recoger(self, estricto: bool = True) -> tuple[str, dict]:
        """Lee el formulario. En modo estricto lanza ValueError((mensaje, pestaña))."""
        errores: list[tuple[str, str]] = []
        c = copy.deepcopy(self.cfg)

        texto_inicio = self.entrada_inicio.get().strip()
        try:
            hi, mi = parsear_hhmm(texto_inicio)
            if not (0 <= hi < 24 and 0 <= mi < 60):
                raise ValueError
        except ValueError:
            errores.append(("Hora de inicio no válida. Usa 9 o 9:30.", "General"))
        try:
            duracion = minutos_hhmm(self.entrada_duracion.get())
            if not 0 < duracion <= 24 * 60:
                raise ValueError
            c["duracion_min"] = duracion
        except ValueError:
            errores.append(("Duración no válida. Usa 8 o 8:30.", "General"))

        c["progreso"] = self.v_progreso.get()
        c["curva"] = ORDEN_CURVAS[self.v_curva.get()]
        c["al_completar"] = self.v_completar.get()
        c["color_extra"] = self.color_extra
        c["inactividad"] = bool(self.v_inactividad.get())
        c["inactividad_min"] = self.spin_inactividad.var.get()

        c["visibilidad"] = self.v_visibilidad.get()
        c["asomar_cada_min"] = self.spin_asomar_cada.var.get()
        c["asomar_seg"] = self.spin_asomar_seg.var.get()
        c["altura"] = self.spin_altura.var.get()
        c["marcas_hora"] = bool(self.v_marcas.get())
        c["estilo_trabajo"] = dict(self.estilos["trabajo"])
        c["estilo_descanso"] = dict(self.estilos["descanso"])

        c["avisos"] = bool(self.v_avisos.get())
        inverso = {v: k for k, v in TIPOS_HITO.items()}
        hitos = []
        for fila in self.filas_hitos:
            tipo = inverso.get(fila["tipo"].get(), "porcentaje")
            valor = fila["valor"].get().strip()
            mensaje = fila["mensaje"].get().strip()
            if not valor and not mensaje:
                continue                    # filas vacías: se ignoran
            if not valor_hito_valido(tipo, valor):
                errores.append((
                    f"Hito no válido: «{valor or 'vacío'}». Usa 25 para % o 0:30 para tiempos.",
                    "Avisos",
                ))
                continue
            hitos.append({"tipo": tipo, "valor": valor, "mensaje": mensaje})
        c["hitos"] = hitos
        c["no_molestar"] = bool(self.v_no_molestar.get())
        c["descanso_largo"] = bool(self.v_descanso_largo.get())
        c["descanso_largo_min"] = self.spin_descanso_largo.var.get()
        c["descanso_largo_msg"] = self.entrada_descanso_largo.get()

        c["celebracion"] = self.v_celebracion.get()
        c["emojis_propios"] = self.entrada_emojis.get()
        c["imagen_ruta"] = self.entrada_imagen.get().strip().strip('"')
        c["texto_celebracion"] = self.entrada_texto.get()
        c["segundos_celebracion"] = self.spin_segundos.var.get()
        if c["celebracion"] == "imagen" and not os.path.isfile(c["imagen_ruta"]):
            errores.append(("No encuentro la imagen de la celebración.", "Celebración"))
        if c["celebracion"] == "emojis_propios" and not separar_emojis(c["emojis_propios"]):
            errores.append(("Escribe al menos un emoji propio.", "Celebración"))

        c["tema_app"] = self.v_tema_app.get()
        c["tema_barra"] = self.v_tema_barra.get()
        c["atenuacion"] = self.v_atenuacion.get()
        c["brillo"] = bool(self.v_brillo.get())
        c["brillo_modo"] = self.v_brillo_modo.get()
        c["saltos"] = bool(self.v_saltos.get())
        c["preaviso_s"] = self.spin_preaviso.var.get()
        c["recta_final_min"] = self.spin_recta.var.get()
        c["aviso_posicion"] = self.v_aviso_posicion.get()
        c["aviso_segundos"] = 0 if self.v_aviso_auto.get() else max(2, _entero(
            self.spin_aviso_seg.var.get(), 2, 60, 6
        ))
        if c["visibilidad"] == "salto" and not (
            c["saltos"] and c["brillo"] and c["brillo_modo"] != "continuo"
        ):
            c["visibilidad"] = "auto"
        (p1, p2), (m1, m2) = self.spins_brillo["pixeles"], self.spins_brillo["minutos"]
        c["brillo_px_min"], c["brillo_px_max"] = p1.var.get(), p2.var.get()
        c["brillo_min_min"], c["brillo_min_max"] = m1.var.get(), m2.var.get()

        c = normalizar_config(c, base=self.cfg)
        if estricto and errores:
            raise ValueError(errores[0])
        return texto_inicio, c

    # ----------------------------------------------------- vista previa viva
    def _bucle_vista(self) -> None:
        try:
            if not self.winfo_exists():
                return
            _, c = self._recoger(estricto=False)
            visual = {k: copy.deepcopy(c[k]) for k in CLAVES_VISUALES}
            tema = self._tema_deseado(visual["tema_app"])
            if tema != self.nombre_tema:
                self._aplicar_tema(tema)
            if visual != self._ultima_visual:
                self._ultima_visual = visual
                if self.al_previsualizar:
                    self.al_previsualizar(visual)
            self._pintar_previa(visual)
        except tk.TclError:
            return
        self._id_vista = self.after(50, self._bucle_vista)

    def _pintar_previa(self, v: dict) -> None:
        ancho, alto = 360, 12
        tema = tema_efectivo_barra(v)
        et = estilo_para_tema(v["estilo_trabajo"], tema, v["atenuacion"])
        ed = estilo_para_tema(v["estilo_descanso"], tema, v["atenuacion"])
        a, b, borde = int(ancho * 0.38), int(ancho * 0.55), int(ancho * 0.78)
        ahora = time.monotonic()
        estela = BRILLO_ANCHO
        if v["brillo"] and v["saltos"] and v["brillo_modo"] != "continuo":
            # Simula la secuencia: preaviso (respira), salto de 30 px, apagado.
            preaviso = min(float(v["preaviso_s"]), 2.0)
            mantener = preaviso + SALTO_BASE_S - BRILLO_ATAQUE + 0.15
            periodo = BRILLO_ATAQUE + mantener + BRILLO_CAIDA + 0.8
            ciclo = ahora % periodo
            brillo = envolvente_brillo(ciclo, 0.0, mantener) * respiracion(ciclo, preaviso)
            avance = suavizar_salida((ciclo - preaviso) / SALTO_BASE_S) if ciclo > preaviso else 0.0
            borde = int(ancho * 0.78) - 30 + int(30 * avance)
            if ciclo < preaviso + SALTO_BASE_S:
                estela = int(BRILLO_ANCHO * ESTELA_SALTO)
        else:
            ciclo = ahora % 3.0
            brillo = envolvente_brillo(ciclo) if v["brillo"] else 0.0
        marcas = [int(ancho * k / 8.5) for k in range(1, 9)] if v["marcas_hora"] else []
        img = self.pintor.pintar(
            ancho, alto, FONDO_BARRA[tema], recortar_segmentos(
                [(0, a, et), (a, b, ed), (b, int(ancho * 0.78), et)], borde
            ),
            0.6, ahora, brillo, borde, marcas, estela,
        )
        self._foto_previa = ImageTk.PhotoImage(img)
        self.lienzo_previa.itemconfigure(self._item_previa, image=self._foto_previa)

    # --------------------------------------------------------------- cierre
    def _aceptar(self) -> None:
        try:
            texto_inicio, c = self._recoger(estricto=True)
        except ValueError as error:
            mensaje, pestana = error.args[0]
            self.aviso.configure(text=mensaje)
            self._mostrar_pestana(pestana)
            return
        self.resultado = (texto_inicio, c, bool(self.v_recordar.get()))
        self._cerrar()

    def _cancelar(self) -> None:
        self.resultado = None
        self._cerrar()

    def _cerrar(self) -> None:
        if self._id_vista is not None:
            try:
                self.after_cancel(self._id_vista)
            except (tk.TclError, ValueError):
                pass
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        self.destroy()


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------
class BarraJornada:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self._calcular_geometria()

        self.preferencias = cargar_preferencias()
        self.cfg = copy.deepcopy(self.preferencias)
        self.inicio: datetime | None = None
        # Tramos: [(datetime_desde, modo), ...] en orden cronológico.
        self.tramos: list[tuple[datetime, str]] = []
        self.completada = False
        self.hitos_disparados: set[str] = set()
        self.descansos_avisados: set[str] = set()
        self.silenciado = False
        self.descanso_auto: dict | None = None      # {"desde": dt, "hasta": dt | None}
        self._ignorar_inactividad = False
        self._dialogo_abierto = False
        self._celebracion_pendiente = False

        self.tema_ui = tema_efectivo_app(self.cfg)
        self.tema_barra = tema_efectivo_barra(self.cfg)
        self._ultimo_chequeo_tema = time.monotonic()

        # Pintado
        self.pintor = PintorBarra()
        self.segmentos: list = []
        self.px_borde = 0                   # punta VISIBLE
        self.px_real = 0                    # punta según el tiempo real
        self.px_visible: float | None = None
        self._salto: dict | None = None     # deslizamiento en curso
        self._ultima_suelta = time.monotonic()
        self.marcas: list[int] = []
        self.progreso_real = 0.0
        self._foto = None
        self._render_id = None

        # Revelado
        self.altura_visible = 0
        self.desde_cuando_encima: float | None = None
        self.ocultar_a_partir_de: float | None = None
        self.animacion_id = None
        self.forzar_hasta = 0.0
        self._venia_forzada = False
        self.proximo_asomo: float | None = None
        self.tooltip_visible = False

        # Brillo
        self.pulso_inicio: float | None = None
        self.pulso_base = 0.0
        self.pulso_mantener = BRILLO_MANTENER
        self.pulso_preaviso = 0.0           # s de "respiración" antes de saltar
        self._destello_pendiente = False    # esperando a que la barra aparezca
        self._recta_final_iniciada = False
        self.diagnostico_activo = os.path.exists(RUTA_DIAGNOSTICO_ON)
        self._ultimo_px = -1
        self._umbral_px: int | None = None
        self._proximo_brillo: float | None = None

        self.burbujas = GestorBurbujas(self)

        if not self._cargar_estado():
            if not self._pedir_configuracion():
                sys.exit(0)

        self._resolver_curva()
        self._actualizar_temas(forzar=True)
        self._construir_barra()
        self._construir_tooltip()
        self._iniciar_bandeja()
        self._aplicar_visibilidad()
        self._programar_asomo()
        self._sincronizar_hitos()
        self._recalcular()

        self._bucle_logica()
        self._despertar_render()            # arranca el bucle de pintado (uno solo)
        self._bucle_hover()
        self._bucle_topmost()

    # ------------------------------------------------------------ geometría
    def _calcular_geometria(self) -> None:
        if PEGADA_AL_BORDE_FISICO:
            self.x = 0
            self.ancho = user32.GetSystemMetrics(SM_CXSCREEN)
            self.base_y = user32.GetSystemMetrics(SM_CYSCREEN)
        else:
            r = _area_trabajo()
            self.x = r.left
            self.ancho = r.right - r.left
            self.base_y = r.bottom

    @property
    def duracion(self) -> timedelta:
        return timedelta(minutes=self.cfg["duracion_min"])

    @property
    def modo(self) -> str:
        return self.tramos[-1][1] if self.tramos else "trabajo"

    @property
    def altura(self) -> int:
        return self.cfg["altura"]

    def _resolver_curva(self) -> None:
        if self.cfg["curva"] is None:
            self.cfg["curva"] = curva_recomendada(self.cfg["duracion_min"])

    def _exponente(self) -> float:
        if self.cfg["progreso"] != "curva":
            return 1.0
        return CURVAS.get(self.cfg["curva"], CURVA_INTENSIDAD_DEF)

    def _en_horas_extra(self) -> bool:
        return self.completada and self.cfg["al_completar"] == "extra"

    def _saltos_configurados(self) -> bool:
        c = self.cfg
        return (
            c["saltos"] and c["brillo"] and c["brillo_modo"] != "continuo"
            and not self._en_horas_extra()
        )

    def _en_recta_final(self) -> bool:
        """Últimos minutos de la jornada: se avanza de forma continua."""
        minutos = self.cfg["recta_final_min"]
        if minutos <= 0 or self.inicio is None:
            return False
        return self._trabajo_restante() <= minutos * 60

    def _saltos_activos(self) -> bool:
        return self._saltos_configurados() and not self._en_recta_final()

    # ---------------------------------------------------------------- estado
    def _cargar_estado(self) -> bool:
        datos = _leer_json(RUTA_ESTADO)
        if not isinstance(datos, dict):
            return False
        try:
            inicio = datetime.fromisoformat(datos["inicio"])
            tramos = [
                (datetime.fromisoformat(t["desde"]), t["modo"])
                for t in datos["tramos"]
                if t["modo"] in ("trabajo", "descanso")
            ]
        except (KeyError, ValueError, TypeError):
            return False
        if inicio.date() != datetime.now().date() or not tramos:
            return False

        self.inicio = inicio
        self.tramos = normalizar_tramos(tramos)
        if "config" in datos:
            self.cfg = normalizar_config(datos["config"], base=self.preferencias)
        else:                                   # estado de la v1.x
            self.cfg = normalizar_config(datos, base=self.preferencias)
        self.completada = bool(datos.get("completada", False))
        self.hitos_disparados = set(datos.get("hitos_disparados") or [])
        self.descansos_avisados = set(datos.get("descansos_avisados") or [])
        self.silenciado = bool(datos.get("silenciado", False))
        auto = datos.get("descanso_auto")
        if isinstance(auto, dict):
            try:
                self.descanso_auto = {
                    "desde": datetime.fromisoformat(auto["desde"]),
                    "hasta": datetime.fromisoformat(auto["hasta"]) if auto.get("hasta") else None,
                }
            except (KeyError, ValueError, TypeError):
                self.descanso_auto = None
        if self.completada and self.cfg["al_completar"] == "cerrar":
            self._celebracion_pendiente = True
        return True

    def _guardar_estado(self) -> None:
        if self.inicio is None:
            return
        auto = None
        if self.descanso_auto:
            hasta = self.descanso_auto["hasta"]
            auto = {
                "desde": self.descanso_auto["desde"].isoformat(),
                "hasta": hasta.isoformat() if hasta else None,
            }
        _escribir_json(RUTA_ESTADO, {
            "version": 2,
            "inicio": self.inicio.isoformat(),
            "tramos": [{"desde": d.isoformat(), "modo": m} for d, m in self.tramos],
            "config": self.cfg,
            "completada": self.completada,
            "hitos_disparados": sorted(self.hitos_disparados),
            "descansos_avisados": sorted(self.descansos_avisados),
            "silenciado": self.silenciado,
            "descanso_auto": auto,
        })

    def _borrar_estado(self) -> None:
        try:
            os.remove(RUTA_ESTADO)
        except OSError:
            pass

    # --------------------------------------------------------- configuración
    def _pedir_configuracion(self) -> bool:
        if self._dialogo_abierto:
            return False
        self._dialogo_abierto = True
        ahora = datetime.now()
        inicio_def = (self.inicio or ahora).strftime("%H:%M")
        previa = copy.deepcopy(self.cfg)
        cfg_dialogo = copy.deepcopy(self.cfg)
        if cfg_dialogo["curva"] is None:
            cfg_dialogo["curva"] = curva_recomendada(cfg_dialogo["duracion_min"])

        dialogo = DialogoConfiguracion(
            self.root, inicio_def, cfg_dialogo,
            al_previsualizar=self._previsualizar,
            al_probar_celebracion=self._probar_celebracion,
            al_probar_aviso=self._probar_aviso,
        )
        self.root.wait_window(dialogo)
        self._dialogo_abierto = False

        if dialogo.resultado is None:
            self.cfg = previa
            self._config_cambiada()
            return False

        texto_inicio, nueva, recordar = dialogo.resultado
        hi, mi = parsear_hhmm(texto_inicio)
        self.inicio = ahora.replace(hour=hi, minute=mi, second=0, microsecond=0)
        self.cfg = nueva
        if recordar:
            guardar_preferencias(self.cfg)
            self.preferencias = cargar_preferencias()

        if not self.tramos:
            self.tramos = [(self.inicio, "trabajo")]
        else:
            tramos = [(max(d, self.inicio), m) for d, m in self.tramos]
            tramos[0] = (self.inicio, tramos[0][1])
            self.tramos = normalizar_tramos(tramos)

        # Si se alarga la jornada después de completarla, vuelve a estar en curso.
        if self.completada and self._trabajo_restante() > 0:
            self.completada = False
            self._celebracion_pendiente = False

        self._sincronizar_hitos()
        self._guardar_estado()
        self._config_cambiada()
        return True

    def _previsualizar(self, visual: dict) -> None:
        """Cambios en vivo mientras el diálogo está abierto."""
        self.cfg.update(copy.deepcopy(visual))
        self._aplicar_cambios_visuales()

    def _aplicar_cambios_visuales(self) -> None:
        self.pintor.limpiar()
        self._actualizar_temas(forzar=True)
        if hasattr(self, "lienzo"):
            self.lienzo.configure(height=self.altura)
            if self.altura_visible > 0 and self.animacion_id is None:
                self._fijar_altura(self.altura)
            self._recalcular()
            self._despertar_render()
        self._actualizar_icono()

    def _config_cambiada(self) -> None:
        self._aplicar_cambios_visuales()
        if hasattr(self, "lienzo"):
            self._aplicar_visibilidad()
        self._programar_asomo()
        self._reiniciar_brillo()
        self._actualizar_menu()

    def _probar_celebracion(self, cfg: dict) -> None:
        self._lanzar_celebracion(cfg, lambda: None)

    def _probar_aviso(self, cfg: dict) -> None:
        self.cfg["aviso_posicion"] = cfg["aviso_posicion"]
        self.cfg["aviso_segundos"] = cfg["aviso_segundos"]
        mensaje = cfg["hitos"][0]["mensaje"] if cfg["hitos"] else "Así se verán los avisos."
        self.burbujas.encolar(
            self._formatear_mensaje(mensaje), urgente=True, respetar_no_molestar=False
        )

    # ----------------------------------------------------------------- temas
    def _actualizar_temas(self, forzar: bool = False) -> None:
        ahora = time.monotonic()
        if not forzar and ahora - self._ultimo_chequeo_tema < INTERVALO_TEMA_S:
            return
        self._ultimo_chequeo_tema = ahora
        ui, barra = tema_efectivo_app(self.cfg), tema_efectivo_barra(self.cfg)
        if not forzar and (ui, barra) == (self.tema_ui, self.tema_barra):
            return
        self.tema_ui, self.tema_barra = ui, barra
        self.pintor.limpiar()
        if hasattr(self, "lienzo"):
            self.lienzo.configure(bg=FONDO_BARRA[barra])
            self._recalcular()
            self._despertar_render()
        if hasattr(self, "etiqueta"):
            self._estilizar_tooltip()

    def _estilo_render(self, modo: str) -> dict:
        return estilo_para_tema(
            self.cfg[f"estilo_{modo}"], self.tema_barra, self.cfg["atenuacion"]
        )

    def _estilo_extra(self) -> dict:
        c = self.cfg["color_extra"]
        return estilo_para_tema(
            {"tipo": "plano", "c1": c, "c2": c}, self.tema_barra, self.cfg["atenuacion"]
        )

    # ----------------------------------------------------------------- barra
    def _construir_barra(self) -> None:
        self.ventana = tk.Toplevel(self.root)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.geometry(
            f"{self.ancho}x{self.altura}+{self.x}+{self.base_y - self.altura}"
        )
        self.lienzo = tk.Canvas(
            self.ventana, width=self.ancho, height=self.altura,
            bg=FONDO_BARRA[self.tema_barra], highlightthickness=0, bd=0,
        )
        self.lienzo.pack(fill="both", expand=True)
        self._item_barra = self.lienzo.create_image(0, 0, anchor="nw")
        self.ventana.update_idletasks()
        self.hwnd_barra = _hwnd(self.ventana)
        _aplicar_estilos(self.hwnd_barra, click_through=True)
        _forzar_topmost(self.hwnd_barra)
        self.altura_visible = self.altura

    def _fijar_altura(self, altura: int) -> None:
        """Ajusta cuánta barra asoma por el borde inferior (0 = oculta)."""
        altura = max(0, min(self.altura, altura))
        self.altura_visible = altura
        if altura == 0:
            try:
                self.ventana.withdraw()
            except tk.TclError:
                pass
            return
        try:
            self.ventana.deiconify()
            self.ventana.geometry(f"{self.ancho}x{altura}+{self.x}+{self.base_y - altura}")
        except tk.TclError:
            return
        _forzar_topmost(self.hwnd_barra)
        self._despertar_render()

    def _animar_altura(self, destino: int) -> None:
        if self.animacion_id is not None:
            try:
                self.root.after_cancel(self.animacion_id)
            except (tk.TclError, ValueError):
                pass
            self.animacion_id = None

        def paso() -> None:
            if self.altura_visible == destino:
                self.animacion_id = None
                return
            avance = 1 if destino > self.altura_visible else -1
            self._fijar_altura(self.altura_visible + avance)
            self.animacion_id = self.root.after(PASO_ANIMACION_MS, paso)

        paso()

    def _aplicar_visibilidad(self) -> None:
        if not hasattr(self, "ventana"):
            return
        self.desde_cuando_encima = None
        self.ocultar_a_partir_de = None
        self.forzar_hasta = 0.0
        self._venia_forzada = False
        if self.animacion_id is not None:
            try:
                self.root.after_cancel(self.animacion_id)
            except (tk.TclError, ValueError):
                pass
            self.animacion_id = None
        self._fijar_altura(self.altura if self.cfg["visibilidad"] == "siempre" else 0)

    def asomar(self, segundos: float) -> None:
        """Muestra la barra un rato aunque esté en modo oculto."""
        if self.cfg["visibilidad"] == "siempre":
            return
        self.forzar_hasta = max(self.forzar_hasta, time.monotonic() + segundos)

    def _programar_asomo(self) -> None:
        if self.cfg["visibilidad"] == "asomar":
            self.proximo_asomo = time.monotonic() + self.cfg["asomar_cada_min"] * 60
        else:
            self.proximo_asomo = None

    def _gestionar_asomo(self) -> None:
        if self.proximo_asomo is not None and time.monotonic() >= self.proximo_asomo:
            self.asomar(self.cfg["asomar_seg"])
            self.root.after(200, self._disparar_brillo)
            self._programar_asomo()

    def punta_en_pantalla(self) -> tuple[int, int]:
        """
        Centro del último píxel pintado de la barra, en coordenadas de pantalla.
        Se mide con el rectángulo REAL de la ventana de la barra que da Windows,
        no con la geometría que le pedimos, por si el escalado la desplaza.
        """
        x0, y0, ancho_real = self.x, self.base_y - self.altura, self.ancho
        if hasattr(self, "hwnd_barra") and self.altura_visible > 0:
            rect = rect_ventana(self.hwnd_barra)
            if rect:
                x0, ancho_real = rect[0], rect[2] - rect[0]
                y0 = rect[3] - self.altura
        escala = ancho_real / self.ancho if self.ancho else 1.0
        punta = max(0.0, min(self.ancho - 0.5, self.px_borde - 0.5))
        # floor, no round: round() de Python redondea al par (376,5 -> 376 pero
        # 383,5 -> 384) y el mismo píxel caería a un lado u otro según la posición.
        return int(math.floor(x0 + punta * escala)), y0 - 2

    def limites_barra(self, _x: int = 0, _y: int = 0) -> tuple[int, int, int, int]:
        _, arriba, _, _ = area_monitor(self.x + 1, self.base_y - 1)
        return self.x, arriba, self.x + self.ancho, self.base_y

    # -------------------------------------------------------------- progreso
    def _descanso_acumulado(self, momento: datetime) -> float:
        total = 0.0
        for i, (desde, modo) in enumerate(self.tramos):
            if modo != "descanso":
                continue
            hasta = self.tramos[i + 1][0] if i + 1 < len(self.tramos) else momento
            total += max(0.0, (min(hasta, momento) - desde).total_seconds())
        return total

    def _total_efectivo(self, momento: datetime) -> float:
        return self.duracion.total_seconds() + self._descanso_acumulado(momento)

    def _trabajado(self, momento: datetime) -> float:
        return (momento - self.inicio).total_seconds() - self._descanso_acumulado(momento)

    def _trabajo_restante(self) -> float:
        return self.duracion.total_seconds() - self._trabajado(datetime.now())

    def _fraccion_lineal(self, momento: datetime, total: float) -> float:
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, (momento - self.inicio).total_seconds() / total))

    def _curvar(self, f: float) -> float:
        exp = self._exponente()
        return f if exp == 1.0 else f ** exp

    def _x_de(self, momento: datetime, total: float) -> int:
        return int(round(self._curvar(self._fraccion_lineal(momento, total)) * self.ancho))

    def _instante_con_trabajo(self, segundos: float, ahora: datetime) -> datetime:
        """Instante en que el trabajo acumulado llega a `segundos`."""
        acumulado = 0.0
        for i, (desde, modo) in enumerate(self.tramos):
            ultimo = i + 1 >= len(self.tramos)
            if modo != "trabajo":
                continue
            if ultimo:
                return desde + timedelta(seconds=segundos - acumulado)
            duracion = (self.tramos[i + 1][0] - desde).total_seconds()
            if acumulado + duracion >= segundos:
                return desde + timedelta(seconds=segundos - acumulado)
            acumulado += duracion
        # Ahora mismo en descanso: el trabajo pendiente empezaría ya.
        return ahora + timedelta(seconds=segundos - acumulado)

    def _recalcular(self) -> None:
        """Segmentos de color, punta y marcas. Se llama una vez por segundo."""
        if self.inicio is None:
            return
        ahora = datetime.now()
        objetivo = self.duracion.total_seconds()
        trabajado = self._trabajado(ahora)
        self.progreso_real = max(0.0, min(1.0, trabajado / objetivo)) if objetivo else 0.0

        if self._en_horas_extra():
            self.segmentos = [(0, self.ancho, self._estilo_extra())]
            self.px_borde = self.px_real = self.ancho
            self.px_visible = float(self.ancho)
            self._salto = None
            self.marcas = []
            return

        total = self._total_efectivo(ahora)
        px_borde = self._x_de(ahora, total)
        segmentos = []
        for i, (desde, modo) in enumerate(self.tramos):
            hasta = self.tramos[i + 1][0] if i + 1 < len(self.tramos) else ahora
            x0 = min(self._x_de(desde, total), px_borde)
            x1 = min(self._x_de(min(hasta, ahora), total), px_borde)
            if x1 > x0:
                segmentos.append((x0, x1, self._estilo_render(modo)))
        if segmentos and segmentos[-1][1] < px_borde:
            x0, _, estilo = segmentos[-1]
            segmentos[-1] = (x0, px_borde, estilo)
        self.segmentos = segmentos
        self.px_real = px_borde
        if self.px_visible is None or not self._saltos_configurados():
            self.px_visible = float(px_borde)       # sin saltos: sigue al tiempo real
            self._salto = None
            self._recta_final_iniciada = False
        elif self._en_recta_final():
            # Recta final: un último salto suelta lo acumulado y, a partir de
            # ahí, la barra avanza de forma continua hasta el final.
            ocupado = self._salto is not None or self._destello_pendiente
            if ocupado:
                self.px_visible = min(self.px_visible, float(px_borde))
            elif not self._recta_final_iniciada and self.px_visible < px_borde - 0.5:
                self._recta_final_iniciada = True
                self.px_visible = min(self.px_visible, float(px_borde))
                self.root.after(0, lambda: self._iniciar_destello(final=True))
            else:
                self._recta_final_iniciada = True
                self.px_visible = float(px_borde)
        else:
            self._recta_final_iniciada = False
            # La punta visible nunca va por delante de la real (p. ej. tras
            # cambiar la hora de inicio o la duración).
            self.px_visible = min(self.px_visible, float(px_borde))
        self.px_borde = int(round(self.px_visible))

        self.marcas = []
        if self.cfg["marcas_hora"]:
            for k in range(1, int(objetivo // 3600) + 1):
                if k * 3600 >= objetivo:
                    break
                instante = self._instante_con_trabajo(k * 3600, ahora)
                self.marcas.append(self._x_de(instante, total))

    # ---------------------------------------------------------------- render
    def _bucle_render(self) -> None:
        self._render_id = None
        espera = INTERVALO_LOGICA_MS
        try:
            if self.altura_visible > 0:
                espera = self._pintar()
        finally:
            self._render_id = self.root.after(espera, self._bucle_render)

    def _despertar_render(self) -> None:
        if not hasattr(self, "lienzo"):
            return
        if self._render_id is not None:
            try:
                self.root.after_cancel(self._render_id)
            except (tk.TclError, ValueError):
                pass
        self._render_id = self.root.after(0, self._bucle_render)

    def _avanzar_salto(self, ahora: float) -> None:
        if self._salto is None:
            return
        if ahora < self._salto["inicio"]:
            return                          # preaviso: la cabeza brilla, la barra espera
        u = (ahora - self._salto["inicio"]) / self._salto["duracion"]
        if u >= 1.0:
            self.px_visible = float(self.px_real)
            self._salto = None
        else:
            p0 = self._salto["desde"]
            self.px_visible = p0 + (self.px_real - p0) * suavizar_salida(u)
        self.px_borde = int(round(self.px_visible))

    def _pintar(self) -> int:
        """Pinta un frame y devuelve cuántos ms esperar hasta el siguiente."""
        ahora = time.monotonic()
        self._avanzar_salto(ahora)
        brillo = self._intensidad_brillo(ahora)
        segmentos = self.segmentos
        if self.px_borde < self.px_real:
            segmentos = recortar_segmentos(segmentos, self.px_borde)
        estela = int(BRILLO_ANCHO * ESTELA_SALTO) if self._salto is not None else BRILLO_ANCHO
        img = self.pintor.pintar(
            self.ancho, self.altura, FONDO_BARRA[self.tema_barra], segmentos,
            self.progreso_real, ahora, brillo, self.px_borde, self.marcas, estela,
        )
        self._foto = ImageTk.PhotoImage(img)
        self.lienzo.itemconfigure(self._item_barra, image=self._foto)
        if self.pulso_inicio is not None or self._salto is not None:
            return INTERVALO_ANIMACION_MS
        if any(s[2]["tipo"] == "movimiento" for s in self.segmentos):
            return INTERVALO_MOVIMIENTO_MS
        return INTERVALO_LOGICA_MS

    # ---------------------------------------------------------------- brillo
    def _reiniciar_brillo(self) -> None:
        self._ultimo_px = -1
        self._umbral_px = None
        self._proximo_brillo = None
        self._ultima_suelta = time.monotonic()

    def _intensidad_brillo(self, ahora: float) -> float:
        if self.pulso_inicio is None:
            return 0.0
        s = ahora - self.pulso_inicio
        if s >= BRILLO_ATAQUE + self.pulso_mantener + BRILLO_CAIDA:
            self.pulso_inicio = None
            return 0.0
        return envolvente_brillo(s, self.pulso_base, self.pulso_mantener) * respiracion(
            s, self.pulso_preaviso
        )

    def _soltar_acumulado(self, ahora: float) -> tuple[float, float]:
        """
        Avance por saltos: programa el salto hasta la punta real tras el
        preaviso. Devuelve (preaviso, duración del salto); (0, 0) si no hay
        nada que soltar.
        """
        if not self._saltos_configurados() or self.px_visible is None:
            return 0.0, 0.0
        acumulado = ahora - self._ultima_suelta
        self._ultima_suelta = ahora
        # Cualquier destello reinicia el ciclo, sea periódico, de hito o al asomar.
        modo = self.cfg["brillo_modo"]
        if modo == "pixeles":
            self._umbral_px = self.px_real + random.randint(
                self.cfg["brillo_px_min"], self.cfg["brillo_px_max"]
            )
        elif modo == "minutos":
            self._proximo_brillo = ahora + random.uniform(
                self.cfg["brillo_min_min"], self.cfg["brillo_min_max"]
            ) * 60
        if self.px_real - self.px_visible < 0.5:
            return 0.0, 0.0
        preaviso = float(self.cfg["preaviso_s"])
        duracion = duracion_salto(acumulado)
        self._salto = {
            "inicio": ahora + preaviso, "desde": self.px_visible, "duracion": duracion,
        }
        return preaviso, duracion

    def _disparar_brillo(self) -> None:
        if not self.cfg["brillo"] or self._en_horas_extra():
            return
        if self._salto is not None:
            return                      # ya hay un salto en marcha
        ahora = time.monotonic()
        preaviso, duracion = self._soltar_acumulado(ahora)
        if duracion == 0.0 and (
            self.pulso_inicio is not None and ahora - self.pulso_inicio < BRILLO_ATAQUE
        ):
            return                      # ya está encendiéndose
        # Si había un pulso apagándose, el nuevo arranca desde su intensidad.
        self.pulso_base = self._intensidad_brillo(ahora)
        self.pulso_inicio = ahora
        # Secuencia de un salto: preaviso (respira) -> salto -> apagado. La
        # cabeza sigue encendida hasta que la punta llega a su sitio.
        self.pulso_preaviso = preaviso if duracion else 0.0
        if duracion:
            self.pulso_mantener = max(
                BRILLO_MANTENER, preaviso + duracion - BRILLO_ATAQUE + 0.15
            )
        else:
            self.pulso_mantener = BRILLO_MANTENER
        self._despertar_render()

    def _iniciar_destello(self, final: bool = False) -> None:
        """
        Punto de entrada de todo destello. Con «Aparecer con cada salto» y la
        barra oculta, primero la hace aparecer y espera unos segundos para
        que dé tiempo a mirar; después, preaviso, salto y apagado.
        """
        if self._destello_pendiente:
            return
        aparecer = (
            self.cfg["visibilidad"] == "salto"
            and self._saltos_configurados()
            and (final or not self._en_recta_final())
            and self._salto is None
            and self.px_visible is not None
            and self.px_real - self.px_visible >= 0.5
            and self.altura_visible < self.altura
        )
        if not aparecer:
            self._disparar_brillo()
            return
        acumulado = time.monotonic() - self._ultima_suelta + APARICION_PREVIA_S
        total = (
            APARICION_PREVIA_S + self.cfg["preaviso_s"] + duracion_salto(acumulado)
            + BRILLO_CAIDA
        )
        self.asomar(total)
        self._destello_pendiente = True

        def lanzar() -> None:
            self._destello_pendiente = False
            self._disparar_brillo()

        self.root.after(int(APARICION_PREVIA_S * 1000), lanzar)

    def _gestionar_brillo(self) -> None:
        if not self.cfg["brillo"] or self._en_horas_extra():
            return
        px = self.px_borde
        modo = self.cfg["brillo_modo"]
        if self._saltos_activos():
            px = self.px_real               # el ciclo cuenta el avance retenido
        if modo == "continuo":
            if 0 <= self._ultimo_px < px:
                self._iniciar_destello()
            self._ultimo_px = px
        elif modo == "pixeles":
            salto = random.randint(self.cfg["brillo_px_min"], self.cfg["brillo_px_max"])
            if self._umbral_px is None:
                self._umbral_px = px + salto
            elif px >= self._umbral_px:
                self._iniciar_destello()
                self._umbral_px = px + salto
        else:
            ahora = time.monotonic()
            espera = random.uniform(self.cfg["brillo_min_min"], self.cfg["brillo_min_max"]) * 60
            if self._proximo_brillo is None:
                self._proximo_brillo = ahora + espera
            elif ahora >= self._proximo_brillo:
                self._iniciar_destello()
                self._proximo_brillo = ahora + espera

    # ----------------------------------------------------------------- lógica
    def _bucle_logica(self) -> None:
        try:
            ahora = datetime.now()
            self._actualizar_temas()
            self._gestionar_inactividad(ahora)
            self._recalcular()
            if self.tooltip_visible:
                self.etiqueta.configure(text=self._texto_tooltip())
            self._gestionar_brillo()
            self._gestionar_hitos(ahora)
            self._gestionar_asomo()
            self._comprobar_final()
        finally:
            self.root.after(INTERVALO_LOGICA_MS, self._bucle_logica)

    def _comprobar_final(self) -> None:
        if not self.completada and self._trabajo_restante() <= 0:
            self._disparar_brillo()             # suelta lo acumulado hasta el final
            self.completada = True
            self._celebracion_pendiente = True
            self._guardar_estado()
            self._actualizar_icono()
        if self._celebracion_pendiente and not self._dialogo_abierto:
            if self.cfg["no_molestar"] and pantalla_ocupada():
                return
            self._celebracion_pendiente = False
            self._celebrar()

    # ----------------------------------------------------------- inactividad
    def _gestionar_inactividad(self, ahora: datetime) -> None:
        if self.inicio is None:
            return
        inactivo = segundos_inactivo()
        if self._ignorar_inactividad:
            if inactivo < 3:
                self._ignorar_inactividad = False
            return
        auto_activo = self.descanso_auto is not None and self.descanso_auto["hasta"] is None

        if auto_activo:
            if inactivo < 3:                    # ha vuelto
                desde = self.descanso_auto["desde"]
                self.descanso_auto["hasta"] = ahora
                self.tramos.append((ahora, "trabajo"))
                self._guardar_estado()
                self._actualizar_icono()
                self._actualizar_menu()
                self._avisar(
                    f"He contado {formatear_corto((ahora - desde).total_seconds())} "
                    "como descanso. Si no lo era, deshazlo desde la bandeja."
                )
            return

        if (
            self.cfg["inactividad"]
            and self.modo == "trabajo"
            and not self.completada
            and inactivo >= self.cfg["inactividad_min"] * 60
        ):
            desde = ahora - timedelta(seconds=inactivo)
            ultimo = self.tramos[-1][0]
            if desde <= ultimo:
                desde = ultimo + timedelta(seconds=1)
            if desde < ahora:
                self.tramos.append((desde, "descanso"))
                self.descanso_auto = {"desde": desde, "hasta": None}
                self._guardar_estado()
                self._actualizar_icono()
                self._actualizar_menu()

    def _deshacer_descanso_auto(self) -> None:
        d = self.descanso_auto
        if not d:
            return
        desde, hasta = d["desde"], d["hasta"]
        self.tramos = normalizar_tramos([
            (t, m) for t, m in self.tramos
            if not (t == desde and m == "descanso")
            and not (hasta is not None and t == hasta and m == "trabajo")
        ])
        if not self.tramos:
            self.tramos = [(self.inicio, "trabajo")]
        if hasta is None:
            self._ignorar_inactividad = True    # sigue inactivo: no volver a marcarlo
        self.descanso_auto = None
        self._guardar_estado()
        self._recalcular()
        self._despertar_render()
        self._actualizar_icono()
        self._actualizar_menu()
        self._avisar("Descanso automático deshecho: ese rato cuenta como trabajo.",
                     respetar=False)

    # ------------------------------------------------------------------ avisos
    def _avisar(self, texto: str, respetar: bool = True) -> None:
        self.burbujas.encolar(texto, respetar_no_molestar=respetar)

    def _datos_jornada(self) -> dict[str, str]:
        ahora = datetime.now()
        objetivo = self.duracion.total_seconds()
        trabajado = self._trabajado(ahora)
        restante = objetivo - trabajado
        if self.modo == "descanso":
            descanso = (ahora - self.tramos[-1][0]).total_seconds()
        else:
            descanso = self._descanso_acumulado(ahora)
        salida = ahora + timedelta(seconds=max(0.0, restante))
        return {
            "restante": formatear_corto(max(0.0, restante)),
            "trabajado": formatear_corto(trabajado),
            "salida": salida.strftime("%H:%M"),
            "porcentaje": f"{int(max(0.0, min(100.0, 100 * trabajado / objetivo))) if objetivo else 0} %",
            "descanso": formatear_corto(descanso),
        }

    def _formatear_mensaje(self, mensaje: str) -> str:
        variantes = [v.strip() for v in mensaje.split("|") if v.strip()]
        texto = random.choice(variantes) if variantes else ""
        if self.inicio is not None:
            for clave, valor in self._datos_jornada().items():
                texto = texto.replace("{" + clave + "}", valor)
        return texto

    def _hito_cumplido(self, hito: dict) -> bool:
        objetivo = self.duracion.total_seconds()
        trabajado = self._trabajado(datetime.now())
        try:
            if hito["tipo"] == "porcentaje":
                v = float(hito["valor"].replace(",", ".").replace("%", "").strip())
                return objetivo > 0 and trabajado / objetivo * 100 >= v
            v = minutos_hhmm(hito["valor"]) * 60
        except ValueError:
            return False
        if hito["tipo"] == "trabajado":
            return trabajado >= v
        return objetivo > v and objetivo - trabajado <= v       # restante

    def _sincronizar_hitos(self) -> None:
        """Marca como vistos, sin avisar, los hitos que ya habían pasado."""
        if self.inicio is None:
            return
        for hito in self.cfg["hitos"]:
            if self._hito_cumplido(hito):
                self.hitos_disparados.add(clave_hito(hito))

    def _gestionar_hitos(self, ahora: datetime) -> None:
        cambios = False
        for hito in self.cfg["hitos"]:
            clave = clave_hito(hito)
            if clave in self.hitos_disparados or not self._hito_cumplido(hito):
                continue
            self.hitos_disparados.add(clave)
            cambios = True
            if self.cfg["avisos"] and not self.silenciado:
                self._avisar(self._formatear_mensaje(hito["mensaje"]))
                self.root.after(300, self._iniciar_destello)

        auto_activo = self.descanso_auto is not None and self.descanso_auto["hasta"] is None
        if self.cfg["descanso_largo"] and self.modo == "descanso" and not auto_activo:
            desde = self.tramos[-1][0]
            clave = desde.isoformat()
            if (
                clave not in self.descansos_avisados
                and (ahora - desde).total_seconds() >= self.cfg["descanso_largo_min"] * 60
            ):
                self.descansos_avisados.add(clave)
                cambios = True
                if not self.silenciado:
                    self._avisar(self._formatear_mensaje(self.cfg["descanso_largo_msg"]))
        if cambios:
            self._guardar_estado()

    # ------------------------------------------------------------ diagnóstico
    def _diagnostico(self, evento: str, datos: dict) -> None:
        """Si existe diagnostico.on, añade una línea JSON a diagnostico.log."""
        if not self.diagnostico_activo:
            return
        try:
            linea = {"hora": datetime.now().isoformat(timespec="seconds"),
                     "version": VERSION, "evento": evento, **datos}
            with open(RUTA_DIAGNOSTICO_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def diagnostico_burbuja(self, burbuja: "Burbuja") -> None:
        if not self.diagnostico_activo or not burbuja.existe():
            return
        datos = {
            "dpi_modo": MODO_DPI,
            "modo_aviso": burbuja.modo,
            "barra_pedida": [self.x, self.base_y - self.altura, self.ancho, self.altura],
            "px_borde": self.px_borde,
            "px_real": self.px_real,
            "punta_calculada": list(self.punta_en_pantalla()),
            "cursor": list(_posicion_cursor()),
            "punta_colita": list(burbuja.punta_pantalla),
        }
        if hasattr(self, "hwnd_barra"):
            datos["barra_real"] = rect_ventana(self.hwnd_barra)
            datos["barra_dpi"] = dpi_ventana(self.hwnd_barra)
            try:
                datos["barra_tk"] = [self.ventana.winfo_rootx(), self.ventana.winfo_rooty(),
                                     self.ventana.winfo_width(), self.ventana.winfo_height()]
            except tk.TclError:
                pass
        datos["burbuja_real"] = rect_ventana(burbuja.hwnd)
        datos["burbuja_pedida"] = burbuja.geom
        self._diagnostico("burbuja", datos)

    # ---------------------------------------------------------------- tooltip
    def _construir_tooltip(self) -> None:
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        self.etiqueta = tk.Label(self.tooltip, text="", font=("Segoe UI", 9), padx=8, pady=4)
        self.etiqueta.pack()
        self._estilizar_tooltip()
        self.tooltip.update_idletasks()
        _aplicar_estilos(_hwnd(self.tooltip), click_through=True)
        self.tooltip.withdraw()
        self.tooltip_visible = False

    def _estilizar_tooltip(self) -> None:
        t = TEMAS_UI[self.tema_ui]
        self.etiqueta.configure(bg=t["tooltip_bg"], fg=t["tooltip_fg"])

    def _texto_tooltip(self) -> str:
        ahora = datetime.now()
        descanso = self._descanso_acumulado(ahora)
        trabajado = (ahora - self.inicio).total_seconds() - descanso
        objetivo = self.duracion.total_seconds()
        restante = objetivo - trabajado
        etiqueta_modo = "Trabajo" if self.modo == "trabajo" else "Descanso"
        base = (
            f"{etiqueta_modo}  ·  {formatear_duracion(trabajado)} / "
            f"{formatear_duracion(objetivo)}"
        )
        if descanso > 0:
            base += f"  ·  descanso {formatear_duracion(descanso)}"
        if restante <= 0:
            return base + f"  ·  +{formatear_duracion(-restante)} de más"
        salida = ahora + timedelta(seconds=restante)
        texto = base + (
            f"  ·  quedan {formatear_duracion(restante)} (salida {salida.strftime('%H:%M')})"
        )
        if self.silenciado:
            texto += "  ·  avisos en silencio"
        return texto

    def _resumen_jornada(self) -> str:
        if self.inicio is None:
            return "Jornada completada"
        ahora = datetime.now()
        texto = f"Has trabajado {formatear_corto(self._trabajado(ahora))}"
        descanso = self._descanso_acumulado(ahora)
        if descanso > 0:
            texto += f"  ·  descanso {formatear_corto(descanso)}"
        return texto

    # ------------------------------------------------------------------ hover
    def _bucle_hover(self) -> None:
        try:
            x, y = _posicion_cursor()
            ahora = time.monotonic()
            en_zona = (
                self.base_y - max(self.altura, ZONA_DETECCION) - 1 <= y < self.base_y + 1
                and self.x <= x < self.x + self.ancho
            )
            if self.cfg["visibilidad"] in ("auto", "asomar", "salto"):
                self._gestionar_revelado(en_zona, ahora)

            mostrar_tooltip = en_zona and self.altura_visible > 0
            if mostrar_tooltip and not self.tooltip_visible:
                self.etiqueta.configure(text=self._texto_tooltip())
                self.tooltip.deiconify()
                self.tooltip_visible = True
            elif not mostrar_tooltip and self.tooltip_visible:
                self.tooltip.withdraw()
                self.tooltip_visible = False

            if self.tooltip_visible:
                self.tooltip.update_idletasks()
                ancho_tt = self.tooltip.winfo_width()
                alto_tt = self.tooltip.winfo_height()
                px = min(max(self.x, x - ancho_tt // 2), self.x + self.ancho - ancho_tt)
                py = self.base_y - self.altura - alto_tt - 6
                self.tooltip.geometry(f"+{px}+{py}")
                _forzar_topmost(_hwnd(self.tooltip))
        finally:
            self.root.after(INTERVALO_HOVER_MS, self._bucle_hover)

    def _gestionar_revelado(self, en_zona: bool, ahora: float) -> None:
        forzado = ahora < self.forzar_hasta
        if forzado and not en_zona:
            self.desde_cuando_encima = None
            self.ocultar_a_partir_de = None
            self._venia_forzada = True
            if self.altura_visible < self.altura and self.animacion_id is None:
                self._animar_altura(self.altura)
            return

        if en_zona:
            self._venia_forzada = False
            self.ocultar_a_partir_de = None
            if self.desde_cuando_encima is None:
                self.desde_cuando_encima = ahora
            elif (
                ahora - self.desde_cuando_encima >= SEGUNDOS_ESPERA
                and self.altura_visible < self.altura
                and self.animacion_id is None
            ):
                self._animar_altura(self.altura)
            return

        self.desde_cuando_encima = None
        if self.altura_visible == 0:
            self._venia_forzada = False
            return
        if self.ocultar_a_partir_de is None:
            # Tras asomar, se esconde enseguida; tras pasar el ratón, espera.
            espera = 0.0 if self._venia_forzada else SEGUNDOS_PERMANENCIA
            self.ocultar_a_partir_de = ahora + espera
            self._venia_forzada = False
        elif ahora >= self.ocultar_a_partir_de and self.animacion_id is None:
            self.ocultar_a_partir_de = None
            self._animar_altura(0)

    def _bucle_topmost(self) -> None:
        # Con un menú contextual abierto (p. ej. el de la bandeja) no se toca
        # el orden: si no, la barra se le pondría encima y lo taparía.
        if menu_contextual_abierto():
            self.root.after(INTERVALO_TOPMOST_MS, self._bucle_topmost)
            return
        try:
            self.ventana.attributes("-topmost", True)
        except tk.TclError:
            return
        if self.altura_visible > 0:
            _aplicar_estilos(self.hwnd_barra, click_through=True)
            _forzar_topmost(self.hwnd_barra)
        self.root.after(INTERVALO_TOPMOST_MS, self._bucle_topmost)

    # ------------------------------------------------------------------ final
    def _lanzar_celebracion(self, cfg: dict, al_terminar) -> None:
        tipo = cfg["celebracion"]
        segundos = cfg["segundos_celebracion"]
        try:
            if tipo == "emojis":
                CelebracionEmojis(self.root, segundos, al_terminar)
            elif tipo == "emojis_propios":
                CelebracionEmojis(
                    self.root, segundos, al_terminar, separar_emojis(cfg["emojis_propios"])
                )
            elif tipo == "imagen":
                CelebracionImagen(self.root, segundos, al_terminar, cfg["imagen_ruta"])
            elif tipo == "texto":
                CelebracionTexto(
                    self.root, segundos, al_terminar, cfg["texto_celebracion"],
                    self._resumen_jornada(), self.tema_ui,
                )
            elif tipo == "minimalista":
                texto = cfg["texto_celebracion"].strip() or "¡Jornada completada!"
                self.burbujas.encolar(
                    f"{texto}\n{self._resumen_jornada()}",
                    segundos=max(4, min(segundos, 10)),
                    urgente=True, respetar_no_molestar=False,
                )
                self.root.after(int(segundos * 1000), al_terminar)
            else:
                self.root.after(500, al_terminar)
        except Exception:
            CelebracionEmojis(self.root, segundos, al_terminar)

    def _celebrar(self) -> None:
        try:
            self.tooltip.withdraw()
            self.tooltip_visible = False
        except tk.TclError:
            pass

        def al_terminar() -> None:
            if self.cfg["al_completar"] == "cerrar":
                self._terminar()
            else:
                self._recalcular()
                self._despertar_render()
                self._actualizar_icono()

        self._lanzar_celebracion(self.cfg, al_terminar)

    # --------------------------------------------------------------- bandeja
    def _imagen_icono(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if self._en_horas_extra():
            d.ellipse((6, 6, 58, 58), fill=self.cfg["color_extra"])
            return img
        estilo = self.cfg[f"estilo_{self.modo}"]
        d.ellipse((6, 6, 58, 58), fill=estilo["c1"])
        if estilo["tipo"] != "plano":
            d.pieslice((6, 6, 58, 58), -90, 90, fill=estilo["c2"])
        return img

    def _actualizar_icono(self) -> None:
        if hasattr(self, "icono"):
            try:
                self.icono.icon = self._imagen_icono()
            except Exception:
                pass

    def _actualizar_menu(self) -> None:
        if hasattr(self, "icono"):
            try:
                self.icono.update_menu()
            except Exception:
                pass

    def _accion(self, funcion):
        def manejador(*_args) -> None:
            self.root.after(0, funcion)
        return manejador

    def _iniciar_bandeja(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Cambiar modo", self._accion(self._alternar_modo), default=True),
            pystray.MenuItem("Configurar", self._accion(self._pedir_configuracion)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Probar celebración",
                self._accion(lambda: self._lanzar_celebracion(self.cfg, lambda: None)),
            ),
            pystray.MenuItem(
                "Silenciar avisos hoy", self._accion(self._alternar_silencio),
                checked=lambda _item: self.silenciado,
            ),
            pystray.MenuItem(
                "Deshacer descanso automático", self._accion(self._deshacer_descanso_auto),
                enabled=lambda _item: self.descanso_auto is not None,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Terminar", self._accion(self._terminar)),
        )
        self.icono = pystray.Icon("barra_jornada", self._imagen_icono(), "Jornada", menu)
        threading.Thread(target=self.icono.run, daemon=True).start()

    def _alternar_modo(self) -> None:
        ahora = datetime.now()
        if self.descanso_auto is not None and self.descanso_auto["hasta"] is None:
            self.descanso_auto["hasta"] = ahora     # lo cierra el usuario a mano
        nuevo = "descanso" if self.modo == "trabajo" else "trabajo"
        self.tramos.append((ahora, nuevo))
        self._guardar_estado()
        self._recalcular()
        self._despertar_render()
        self._actualizar_icono()
        self._actualizar_menu()

    def _alternar_silencio(self) -> None:
        self.silenciado = not self.silenciado
        self._guardar_estado()
        self._actualizar_menu()
        self._avisar(
            "Avisos en silencio hasta mañana." if self.silenciado else "Avisos activados de nuevo.",
            respetar=False,
        )

    def _terminar(self) -> None:
        self._borrar_estado()
        try:
            self.icono.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    def ejecutar(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if not es_unica_instancia():
        sys.exit(0)
    activar_dpi_por_monitor()           # antes de crear cualquier ventana
    BarraJornada().ejecutar()
