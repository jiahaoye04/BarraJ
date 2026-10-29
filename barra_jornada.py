"""
Barra de progreso de la jornada laboral — Windows 11.

- La barra se pinta por tramos: cada franja conserva el color del modo
  (trabajo / descanso) en el que estabas durante ese intervalo.
- El tiempo de descanso NO consume jornada: la duración total se amplía
  con cada minuto de descanso y la barra se recalcula continuamente.
- Progreso real (ritmo constante) o curvado (primeras horas lentas, últimas
  rápidas) con intensidad ajustable.
- Brillo opcional en la punta cuando la barra avanza.
- Colores, duración y modo de visibilidad configurables y recordables.
- Al completarse, lanza una celebración de emojis y se cierra sola.

Dependencias:
    pip install pystray pillow

Uso:
    pythonw barra_jornada.py / jornada.bat
"""

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
from tkinter import colorchooser
from PIL import Image, ImageDraw, ImageFont, ImageTk
import pystray

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
ALTURA_BARRA = 4                    # px
DURACION_POR_DEFECTO = "8:30"       # valor de fábrica; el usuario puede cambiarlo
COLOR_TRABAJO_DEF = "#2f81f7"       # azul
COLOR_DESCANSO_DEF = "#2ea043"      # verde
COLOR_FONDO = "#1c1c1c"

# "siempre" -> la barra está visible todo el rato.
# "auto"    -> oculta; se revela al dejar el ratón en el borde inferior.
VISIBILIDAD_DEF = "siempre"

# Progreso: "real" = ritmo constante; "curva" = primeras horas lentas,
# últimas rápidas. La intensidad es el exponente aplicado a la fracción
# de trabajo: 1.0 equivale a lineal; cuanto mayor, más pronunciada la curva.
PROGRESO_DEF = "real"
CURVAS = {           # etiqueta -> exponente
    "Lineal": 1.0,
    "Suave": 1.35,
    "Media": 1.7,
    "Fuerte": 2.3,
}
ORDEN_CURVAS = ["Lineal", "Suave", "Media", "Fuerte"]
CURVA_INTENSIDAD_DEF = 1.7          # usado solo si no hay recomendación por horas

# Brillo de la punta
BRILLO_DEF = True
BRILLO_ANCHO = 48                   # px del degradado hacia la punta
BRILLO_DECAIMIENTO = 0.78           # factor por frame; más bajo = se apaga antes

# False -> pegada al borde superior de la barra de tareas (recomendado).
# True  -> pegada al borde físico de la pantalla; la barra de tareas la tapará
#          al activarla, salvo que la pongas en "ocultar automáticamente".
PEGADA_AL_BORDE_FISICO = False

# Modo "auto"
SEGUNDOS_ESPERA = 0.05              # tiempo con el ratón encima antes de aparecer
SEGUNDOS_PERMANENCIA = 5.0          # tiempo visible tras retirar el ratón
ZONA_DETECCION = 3                  # px desde el borde que activan el revelado
PASO_ANIMACION_MS = 25

# Celebración final
SEGUNDOS_CELEBRACION = 10           # tras completarse, se cierra sola
NUM_EMOJIS = 45
EMOJIS = "🎉🎊✨🥳🎈🌟💪🛋️😴🍻👏🔥⭐🏆🙌"
RUTA_FUENTE_EMOJI = r"C:\Windows\Fonts\seguiemj.ttf"

INTERVALO_PROGRESO_MS = 1000
INTERVALO_BRILLO_MS = 60            # refresco del degradado de la punta
INTERVALO_HOVER_MS = 100
INTERVALO_TOPMOST_MS = 500
INTERVALO_ANIMACION_MS = 33

COLOR_CLAVE = "#010203"             # color que Windows hará transparente

RUTA_ESTADO = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "barra_jornada",
    "estado.json",
)

# Preferencias del usuario (sobreviven de un día a otro).
RUTA_PREFERENCIAS = os.path.join(
    os.path.dirname(RUTA_ESTADO),
    "preferencias.json",
)

# --------------------------------------------------------------------------
# WinAPI
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.restype = ctypes.c_long

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

SW_SHOWNOACTIVATE = 4

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SPI_GETWORKAREA = 0x0030

GA_ROOT = 2


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


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


def _forzar_topmost(hwnd: int) -> None:
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


# --------------------------------------------------------------------------
# Utilidades
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


def formatear_duracion(segundos: float) -> str:
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos = resto // 60
    return f"{horas}h {minutos:02d}m"


def color_valido(valor: str, por_defecto: str) -> str:
    if isinstance(valor, str) and len(valor) == 7 and valor.startswith("#"):
        try:
            int(valor[1:], 16)
            return valor
        except ValueError:
            pass
    return por_defecto


def visibilidad_valida(valor, por_defecto: str) -> str:
    return valor if valor in ("siempre", "auto") else por_defecto


def progreso_valido(valor, por_defecto: str) -> str:
    return valor if valor in ("real", "curva") else por_defecto


def curva_valida(valor, por_defecto: str) -> str:
    return valor if valor in CURVAS else por_defecto


def curva_recomendada(duracion_min: int) -> str:
    """Topes de curva sugeridos según la duración de la jornada."""
    horas = duracion_min / 60.0
    if horas <= 6:
        return "Suave"
    if horas <= 9:
        return "Media"
    return "Fuerte"


def _hex_a_rgb(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def mezclar_hacia_blanco(color: str, t: float) -> str:
    """t=0 -> color original; t=1 -> blanco."""
    t = max(0.0, min(1.0, t))
    r, g, b = _hex_a_rgb(color)
    r = int(r + (255 - r) * t)
    g = int(g + (255 - g) * t)
    b = int(b + (255 - b) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def cargar_preferencias() -> dict:
    """Valores por defecto del usuario. Si no existen, los de fábrica."""
    hd, md = parsear_hhmm(DURACION_POR_DEFECTO)
    prefs = {
        "duracion_min": hd * 60 + md,
        "color_trabajo": COLOR_TRABAJO_DEF,
        "color_descanso": COLOR_DESCANSO_DEF,
        "visibilidad": VISIBILIDAD_DEF,
        "progreso": PROGRESO_DEF,
        "curva": None,          # None = usar recomendación por horas
        "brillo": BRILLO_DEF,
    }
    try:
        with open(RUTA_PREFERENCIAS, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError):
        return prefs

    minutos = datos.get("duracion_min")
    if isinstance(minutos, int) and 0 < minutos <= 24 * 60:
        prefs["duracion_min"] = minutos
    prefs["color_trabajo"] = color_valido(datos.get("color_trabajo"), COLOR_TRABAJO_DEF)
    prefs["color_descanso"] = color_valido(
        datos.get("color_descanso"), COLOR_DESCANSO_DEF
    )
    prefs["visibilidad"] = visibilidad_valida(
        datos.get("visibilidad"), VISIBILIDAD_DEF
    )
    prefs["progreso"] = progreso_valido(datos.get("progreso"), PROGRESO_DEF)
    guardada = datos.get("curva")
    prefs["curva"] = guardada if guardada in CURVAS else None
    prefs["brillo"] = bool(datos.get("brillo", BRILLO_DEF))
    return prefs


def guardar_preferencias(
    duracion_min: int,
    color_trabajo: str,
    color_descanso: str,
    visibilidad: str,
    progreso: str,
    curva: str,
    brillo: bool,
) -> None:
    try:
        os.makedirs(os.path.dirname(RUTA_PREFERENCIAS), exist_ok=True)
        with open(RUTA_PREFERENCIAS, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "duracion_min": duracion_min,
                    "color_trabajo": color_trabajo,
                    "color_descanso": color_descanso,
                    "visibilidad": visibilidad,
                    "progreso": progreso,
                    "curva": curva,
                    "brillo": brillo,
                },
                f,
            )
    except OSError:
        pass


# --------------------------------------------------------------------------
# Diálogo de configuración
# --------------------------------------------------------------------------
class DialogoConfiguracion(tk.Toplevel):
    def __init__(
        self,
        padre: tk.Tk,
        inicio: str,
        duracion: str,
        color_trabajo: str,
        color_descanso: str,
        visibilidad: str,
        progreso: str,
        curva: str,
        brillo: bool,
    ):
        super().__init__(padre)
        self.resultado = None
        self.color_trabajo = color_trabajo
        self.color_descanso = color_descanso

        self.title("Jornada")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(padx=16, pady=14)

        fila = 0
        tk.Label(self, text="Hora de inicio").grid(row=fila, column=0, sticky="w")
        self.entrada_inicio = tk.Entry(self, width=10, justify="center")
        self.entrada_inicio.insert(0, inicio)
        self.entrada_inicio.grid(row=fila, column=1, padx=(12, 0), pady=4, sticky="e")

        fila += 1
        tk.Label(self, text="Trabajo efectivo").grid(row=fila, column=0, sticky="w")
        self.entrada_duracion = tk.Entry(self, width=10, justify="center")
        self.entrada_duracion.insert(0, duracion)
        self.entrada_duracion.grid(row=fila, column=1, padx=(12, 0), pady=4, sticky="e")

        fila += 1
        tk.Label(self, text="Color de trabajo").grid(row=fila, column=0, sticky="w")
        self.boton_trabajo = tk.Button(
            self, width=8, relief="ridge",
            command=lambda: self._elegir_color("trabajo"),
        )
        self.boton_trabajo.grid(row=fila, column=1, padx=(12, 0), pady=4, sticky="e")

        fila += 1
        tk.Label(self, text="Color de descanso").grid(row=fila, column=0, sticky="w")
        self.boton_descanso = tk.Button(
            self, width=8, relief="ridge",
            command=lambda: self._elegir_color("descanso"),
        )
        self.boton_descanso.grid(row=fila, column=1, padx=(12, 0), pady=4, sticky="e")

        fila += 1
        tk.Button(self, text="Restaurar colores", command=self._restaurar_colores).grid(
            row=fila, column=0, columnspan=2, sticky="w", pady=(2, 0)
        )

        # --- Progreso ---
        fila += 1
        tk.Label(self, text="Avance de la barra").grid(
            row=fila, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        self.progreso = tk.StringVar(value=progreso)
        fila += 1
        tk.Radiobutton(
            self, text="Real (ritmo constante)",
            variable=self.progreso, value="real", command=self._actualizar_curva_estado,
        ).grid(row=fila, column=0, columnspan=2, sticky="w")
        fila += 1
        tk.Radiobutton(
            self, text="Equilibrado (lento al principio, rápido al final)",
            variable=self.progreso, value="curva", command=self._actualizar_curva_estado,
        ).grid(row=fila, column=0, columnspan=2, sticky="w")

        fila += 1
        self.label_curva = tk.Label(self, text="Intensidad de la curva")
        self.label_curva.grid(row=fila, column=0, columnspan=2, sticky="w", pady=(6, 0))
        fila += 1
        self.indice_curva = tk.IntVar(value=ORDEN_CURVAS.index(curva))
        self.deslizador = tk.Scale(
            self, from_=0, to=len(ORDEN_CURVAS) - 1,
            orient="horizontal", showvalue=False,
            variable=self.indice_curva, command=self._actualizar_etiqueta_curva,
            length=230, sliderlength=28,
        )
        self.deslizador.grid(row=fila, column=0, columnspan=2, sticky="we")
        fila += 1
        marcas = tk.Frame(self)
        marcas.grid(row=fila, column=0, columnspan=2, sticky="we")
        for i, nombre in enumerate(ORDEN_CURVAS):
            marcas.columnconfigure(i, weight=1)
            if i == 0:
                anclaje = "w"
            elif i == len(ORDEN_CURVAS) - 1:
                anclaje = "e"
            else:
                anclaje = ""          # vacío = centrado; "center" no es válido en grid
            tk.Label(marcas, text=nombre, font=("Segoe UI", 7)).grid(
                row=0, column=i, sticky=anclaje
            )

        # --- Brillo ---
        fila += 1
        self.brillo = tk.BooleanVar(value=brillo)
        tk.Checkbutton(
            self, text="Brillo en la punta al avanzar", variable=self.brillo,
        ).grid(row=fila, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # --- Visibilidad ---
        fila += 1
        tk.Label(self, text="Visibilidad de la barra").grid(
            row=fila, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        self.visibilidad = tk.StringVar(value=visibilidad)
        fila += 1
        tk.Radiobutton(
            self, text="Siempre visible",
            variable=self.visibilidad, value="siempre",
        ).grid(row=fila, column=0, columnspan=2, sticky="w")
        fila += 1
        tk.Radiobutton(
            self, text="Oculta; aparece al dejar el ratón abajo",
            variable=self.visibilidad, value="auto",
        ).grid(row=fila, column=0, columnspan=2, sticky="w")

        fila += 1
        self.recordar = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self,
            text="Recordar esta configuración para los próximos días",
            variable=self.recordar,
        ).grid(row=fila, column=0, columnspan=2, sticky="w", pady=(8, 0))

        fila += 1
        self.aviso = tk.Label(self, text="", fg="#c0392b")
        self.aviso.grid(row=fila, column=0, columnspan=2, sticky="w")

        fila += 1
        tk.Button(self, text="Aceptar", width=12, command=self._aceptar).grid(
            row=fila, column=0, columnspan=2, pady=(10, 0)
        )

        self._pintar_botones()
        self._actualizar_etiqueta_curva()
        self._actualizar_curva_estado()

        self.bind("<Return>", lambda _e: self._aceptar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.entrada_inicio.focus_set()
        self.entrada_inicio.select_range(0, tk.END)
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 4
        self.geometry(f"+{x}+{max(0, y)}")
        self.grab_set()

    def _actualizar_etiqueta_curva(self, *_a) -> None:
        nombre = ORDEN_CURVAS[self.indice_curva.get()]
        self.label_curva.configure(text=f"Intensidad de la curva: {nombre}")

    def _actualizar_curva_estado(self, *_a) -> None:
        activo = self.progreso.get() == "curva"
        estado = "normal" if activo else "disabled"
        self.deslizador.configure(state=estado)
        self.label_curva.configure(fg="#000000" if activo else "#9a9a9a")

    def _pintar_botones(self) -> None:
        for boton, color in (
            (self.boton_trabajo, self.color_trabajo),
            (self.boton_descanso, self.color_descanso),
        ):
            boton.configure(bg=color, activebackground=color, text=color)

    def _elegir_color(self, cual: str) -> None:
        actual = self.color_trabajo if cual == "trabajo" else self.color_descanso
        _, codigo = colorchooser.askcolor(color=actual, parent=self, title="Color")
        if not codigo:
            return
        if cual == "trabajo":
            self.color_trabajo = codigo
        else:
            self.color_descanso = codigo
        self._pintar_botones()

    def _restaurar_colores(self) -> None:
        self.color_trabajo = COLOR_TRABAJO_DEF
        self.color_descanso = COLOR_DESCANSO_DEF
        self._pintar_botones()

    def _aceptar(self) -> None:
        try:
            parsear_hhmm(self.entrada_inicio.get())
            h, m = parsear_hhmm(self.entrada_duracion.get())
            if h * 60 + m <= 0:
                raise ValueError
        except ValueError:
            self.aviso.configure(text="Formato no válido. Usa 9 o 9:30.")
            return
        self.resultado = (
            self.entrada_inicio.get().strip(),
            self.entrada_duracion.get().strip(),
            self.color_trabajo,
            self.color_descanso,
            self.visibilidad.get(),
            self.progreso.get(),
            ORDEN_CURVAS[self.indice_curva.get()],
            bool(self.brillo.get()),
            bool(self.recordar.get()),
        )
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()


# --------------------------------------------------------------------------
# Celebración final: emojis animados a pantalla completa
# --------------------------------------------------------------------------
class Celebracion:
    def __init__(self, root: tk.Tk, al_terminar) -> None:
        self.root = root
        self.al_terminar = al_terminar
        self.ancho = user32.GetSystemMetrics(SM_CXSCREEN)
        self.alto = user32.GetSystemMetrics(SM_CYSCREEN)

        self.ventana = tk.Toplevel(root)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.geometry(f"{self.ancho}x{self.alto}+0+0")
        self.ventana.configure(bg=COLOR_CLAVE)
        self.ventana.attributes("-transparentcolor", COLOR_CLAVE)

        self.lienzo = tk.Canvas(
            self.ventana, width=self.ancho, height=self.alto,
            bg=COLOR_CLAVE, highlightthickness=0, bd=0,
        )
        self.lienzo.pack(fill="both", expand=True)

        self.ventana.update_idletasks()
        self.hwnd = _hwnd(self.ventana)
        _aplicar_estilos(self.hwnd, click_through=True)
        _forzar_topmost(self.hwnd)

        self.cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.particulas = [self._nueva_particula(inicial=True) for _ in range(NUM_EMOJIS)]
        self._animar()
        self.root.after(int(SEGUNDOS_CELEBRACION * 1000), self._cerrar)

    def _imagen(self, emoji: str, tam: int):
        clave = (emoji, tam)
        if clave in self.cache:
            return self.cache[clave]
        try:
            fuente = ImageFont.truetype(RUTA_FUENTE_EMOJI, tam)
            img = Image.new("RGBA", (int(tam * 1.6), int(tam * 1.6)), (0, 0, 0, 0))
            ImageDraw.Draw(img).text(
                (tam * 0.1, 0), emoji, font=fuente, embedded_color=True
            )
            foto = ImageTk.PhotoImage(img)
        except Exception:
            return None
        self.cache[clave] = foto
        return foto

    def _nueva_particula(self, inicial: bool = False) -> dict:
        tam = random.choice([28, 34, 40, 48, 56])
        emoji = random.choice(EMOJIS)
        foto = self._imagen(emoji, tam)
        x = random.uniform(0, self.ancho)
        y = random.uniform(0, self.alto) if inicial else self.alto + tam
        if foto is not None:
            item = self.lienzo.create_image(x, y, image=foto, anchor="center")
        else:
            item = self.lienzo.create_text(
                x, y, text=emoji, font=("Segoe UI Emoji", tam // 2), fill="#ffd166"
            )
        return {
            "item": item,
            "foto": foto,
            "x": x,
            "y": y,
            "vy": random.uniform(1.4, 3.6),
            "fase": random.uniform(0, 6.28),
            "amplitud": random.uniform(0.6, 2.2),
            "tam": tam,
        }

    def _animar(self) -> None:
        if not self.ventana.winfo_exists():
            return
        for p in self.particulas:
            p["fase"] += 0.08
            p["y"] -= p["vy"]
            p["x"] += p["amplitud"] * math.sin(p["fase"])
            if p["y"] < -p["tam"]:
                p["y"] = self.alto + p["tam"]
                p["x"] = random.uniform(0, self.ancho)
            self.lienzo.coords(p["item"], p["x"], p["y"])
        _forzar_topmost(self.hwnd)
        self.root.after(INTERVALO_ANIMACION_MS, self._animar)

    def _cerrar(self) -> None:
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass
        self.al_terminar()


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------
class BarraJornada:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

        self._calcular_geometria()

        self.preferencias = cargar_preferencias()
        self.inicio: datetime | None = None
        self.duracion = timedelta(0)          # trabajo efectivo
        self.color_trabajo = self.preferencias["color_trabajo"]
        self.color_descanso = self.preferencias["color_descanso"]
        self.visibilidad = self.preferencias["visibilidad"]
        self.progreso = self.preferencias["progreso"]
        self.curva = self.preferencias["curva"]       # etiqueta o None
        self.brillo = self.preferencias["brillo"]
        # Tramos: [(datetime_desde, modo), ...] en orden cronológico.
        self.tramos: list[tuple[datetime, str]] = []
        self.rectangulos: list[int] = []
        self.completada = False

        # Estado del revelado automático
        self.altura_visible = ALTURA_BARRA
        self.desde_cuando_encima: float | None = None
        self.ocultar_a_partir_de: float | None = None
        self.animacion_id = None

        # Estado del brillo de la punta
        self.ultimo_borde = -1.0        # fracción pintada en el último frame
        self.intensidad_brillo = 0.0    # 0..1, decae con el tiempo
        self.rect_brillo: list[int] = []

        if not self._cargar_estado():
            if not self._pedir_configuracion():
                sys.exit(0)

        self._resolver_curva()

        self._construir_barra()
        self._construir_tooltip()
        self._iniciar_bandeja()
        self._aplicar_visibilidad()

        self._bucle_progreso()
        self._bucle_brillo()
        self._bucle_hover()
        self._bucle_topmost()

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
    def modo(self) -> str:
        return self.tramos[-1][1] if self.tramos else "trabajo"

    def _color(self, modo: str) -> str:
        return self.color_trabajo if modo == "trabajo" else self.color_descanso

    def _resolver_curva(self) -> None:
        """Si no hay curva elegida, usa la recomendada por las horas."""
        if self.curva is None:
            minutos = int(self.duracion.total_seconds() // 60) or self.preferencias["duracion_min"]
            self.curva = curva_recomendada(minutos)

    def _exponente(self) -> float:
        if self.progreso != "curva":
            return 1.0
        return CURVAS.get(self.curva, CURVA_INTENSIDAD_DEF)

    # ---------------------------------------------------------------- estado
    def _cargar_estado(self) -> bool:
        try:
            with open(RUTA_ESTADO, "r", encoding="utf-8") as f:
                datos = json.load(f)
            inicio = datetime.fromisoformat(datos["inicio"])
            tramos = [
                (datetime.fromisoformat(t["desde"]), t["modo"])
                for t in datos["tramos"]
            ]
        except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            return False

        if inicio.date() != datetime.now().date() or not tramos:
            return False

        self.inicio = inicio
        self.duracion = timedelta(
            minutes=datos.get("duracion_min", self.preferencias["duracion_min"])
        )
        self.tramos = tramos
        self.color_trabajo = color_valido(
            datos.get("color_trabajo"), self.preferencias["color_trabajo"]
        )
        self.color_descanso = color_valido(
            datos.get("color_descanso"), self.preferencias["color_descanso"]
        )
        self.visibilidad = visibilidad_valida(
            datos.get("visibilidad"), self.preferencias["visibilidad"]
        )
        self.progreso = progreso_valido(
            datos.get("progreso"), self.preferencias["progreso"]
        )
        guardada = datos.get("curva")
        self.curva = guardada if guardada in CURVAS else self.preferencias["curva"]
        self.brillo = bool(datos.get("brillo", self.preferencias["brillo"]))
        return True

    def _guardar_estado(self) -> None:
        os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
        with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "inicio": self.inicio.isoformat(),
                    "duracion_min": int(self.duracion.total_seconds() // 60),
                    "color_trabajo": self.color_trabajo,
                    "color_descanso": self.color_descanso,
                    "visibilidad": self.visibilidad,
                    "progreso": self.progreso,
                    "curva": self.curva,
                    "brillo": self.brillo,
                    "tramos": [
                        {"desde": desde.isoformat(), "modo": modo}
                        for desde, modo in self.tramos
                    ],
                },
                f,
            )

    def _borrar_estado(self) -> None:
        try:
            os.remove(RUTA_ESTADO)
        except OSError:
            pass

    def _pedir_configuracion(self) -> bool:
        ahora = datetime.now()
        inicio_def = (
            self.inicio.strftime("%H:%M") if self.inicio else ahora.strftime("%H:%M")
        )
        if self.duracion:
            total = int(self.duracion.total_seconds() // 60)
        else:
            total = self.preferencias["duracion_min"]
        duracion_def = f"{total // 60}:{total % 60:02d}"
        curva_dialogo = self.curva or curva_recomendada(total)

        dialogo = DialogoConfiguracion(
            self.root, inicio_def, duracion_def,
            self.color_trabajo, self.color_descanso, self.visibilidad,
            self.progreso, curva_dialogo, self.brillo,
        )
        self.root.wait_window(dialogo)
        if dialogo.resultado is None:
            return False

        (
            texto_inicio,
            texto_duracion,
            color_trabajo,
            color_descanso,
            visibilidad,
            progreso,
            curva,
            brillo,
            recordar,
        ) = dialogo.resultado
        hi, mi = parsear_hhmm(texto_inicio)
        hd, md = parsear_hhmm(texto_duracion)
        self.inicio = ahora.replace(hour=hi, minute=mi, second=0, microsecond=0)
        self.duracion = timedelta(hours=hd, minutes=md)
        self.color_trabajo = color_valido(color_trabajo, COLOR_TRABAJO_DEF)
        self.color_descanso = color_valido(color_descanso, COLOR_DESCANSO_DEF)
        self.visibilidad = visibilidad_valida(visibilidad, VISIBILIDAD_DEF)
        self.progreso = progreso_valido(progreso, PROGRESO_DEF)
        self.curva = curva_valida(curva, curva_recomendada(hd * 60 + md))
        self.brillo = bool(brillo)

        if recordar:
            guardar_preferencias(
                hd * 60 + md, self.color_trabajo, self.color_descanso,
                self.visibilidad, self.progreso, self.curva, self.brillo,
            )
            self.preferencias = cargar_preferencias()

        if not self.tramos:
            self.tramos = [(self.inicio, "trabajo")]
        else:
            tramos = [(max(d, self.inicio), m) for d, m in self.tramos]
            tramos[0] = (self.inicio, tramos[0][1])
            self.tramos = tramos

        self.completada = False
        self._guardar_estado()
        self._refrescar_aspecto()
        self._aplicar_visibilidad()
        return True

    def _refrescar_aspecto(self) -> None:
        """Aplica los colores en caliente (barra e icono), si ya existen."""
        if hasattr(self, "lienzo"):
            self._redibujar()
        if hasattr(self, "icono"):
            try:
                self.icono.icon = self._imagen_icono()
            except Exception:
                pass

    def _aplicar_visibilidad(self) -> None:
        """Deja la barra en el estado que corresponda al modo elegido."""
        if not hasattr(self, "ventana"):
            return
        self.desde_cuando_encima = None
        self.ocultar_a_partir_de = None
        if self.animacion_id is not None:
            try:
                self.root.after_cancel(self.animacion_id)
            except (tk.TclError, ValueError):
                pass
            self.animacion_id = None

        if self.visibilidad == "siempre":
            self._fijar_altura(ALTURA_BARRA)
        else:
            self._fijar_altura(0)

    # ----------------------------------------------------------------- barra
    def _construir_barra(self) -> None:
        self.ventana = tk.Toplevel(self.root)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.geometry(
            f"{self.ancho}x{ALTURA_BARRA}+{self.x}+{self.base_y - ALTURA_BARRA}"
        )
        self.lienzo = tk.Canvas(
            self.ventana,
            width=self.ancho,
            height=ALTURA_BARRA,
            bg=COLOR_FONDO,
            highlightthickness=0,
            bd=0,
        )
        self.lienzo.pack(fill="both", expand=True)
        self.ventana.update_idletasks()
        self.hwnd_barra = _hwnd(self.ventana)
        _aplicar_estilos(self.hwnd_barra, click_through=True)
        _forzar_topmost(self.hwnd_barra)

    def _fijar_altura(self, altura: int) -> None:
        """Ajusta cuánta barra asoma por el borde inferior (0 = oculta)."""
        altura = max(0, min(ALTURA_BARRA, altura))
        self.altura_visible = altura
        if altura == 0:
            try:
                self.ventana.withdraw()
            except tk.TclError:
                pass
            return
        try:
            self.ventana.deiconify()
            self.ventana.geometry(
                f"{self.ancho}x{altura}+{self.x}+{self.base_y - altura}"
            )
        except tk.TclError:
            return
        _forzar_topmost(self.hwnd_barra)

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

    def _construir_tooltip(self) -> None:
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        self.etiqueta = tk.Label(
            self.tooltip,
            text="",
            bg="#101010",
            fg="#f0f0f0",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        )
        self.etiqueta.pack()
        self.tooltip.update_idletasks()
        _aplicar_estilos(_hwnd(self.tooltip), click_through=True)
        self.tooltip.withdraw()
        self.tooltip_visible = False

    # -------------------------------------------------------------- progreso
    def _descanso_acumulado(self, momento: datetime) -> float:
        """Segundos de descanso desde el inicio hasta `momento`."""
        total = 0.0
        for i, (desde, modo) in enumerate(self.tramos):
            if modo != "descanso":
                continue
            hasta = self.tramos[i + 1][0] if i + 1 < len(self.tramos) else momento
            total += max(0.0, (min(hasta, momento) - desde).total_seconds())
        return total

    def _total_efectivo(self, momento: datetime) -> float:
        """Duración total de la barra: trabajo efectivo + descansos tomados."""
        return self.duracion.total_seconds() + self._descanso_acumulado(momento)

    def _fraccion_lineal(self, momento: datetime, total: float) -> float:
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, (momento - self.inicio).total_seconds() / total))

    def _modo_en(self, momento: datetime) -> str:
        """Modo activo en un instante dado, según los tramos."""
        actual = self.tramos[0][1] if self.tramos else "trabajo"
        for desde, modo in self.tramos:
            if desde <= momento:
                actual = modo
            else:
                break
        return actual

    def _curvar(self, f: float) -> float:
        """Aplica la curva de ritmo a una fracción lineal 0..1."""
        exp = self._exponente()
        if exp == 1.0:
            return f
        return f ** exp

    def _borde_actual(self) -> float:
        """Fracción de barra pintada ahora mismo (0..1), ya curvada."""
        ahora = datetime.now()
        total = self._total_efectivo(ahora)
        return self._curvar(self._fraccion_lineal(ahora, total))

    def _redibujar(self) -> None:
        """
        Pinta la barra columna a columna: cada x mapea a su instante real y
        toma el color del modo activo en ese instante. Así la curva deforma
        el eje correctamente sin romper las fronteras de color.
        """
        ahora = datetime.now()
        total = self._total_efectivo(ahora)
        inicio_s = self.inicio.timestamp()

        for rect in self.rectangulos:
            self.lienzo.delete(rect)
        self.rectangulos = []

        borde = self._borde_actual()            # fracción pintada
        px_borde = int(round(borde * self.ancho))
        if px_borde <= 0 or total <= 0:
            return

        exp = self._exponente()
        # Recorremos columnas y agrupamos tramos del mismo color.
        x = 0
        color_actual = None
        inicio_segmento = 0
        while x <= px_borde:
            if x < px_borde:
                # fracción curvada de esta columna -> fracción lineal -> instante
                fc = x / self.ancho
                fl = fc ** (1.0 / exp) if exp != 1.0 else fc
                instante = datetime.fromtimestamp(inicio_s + fl * total)
                color = self._color(self._modo_en(instante))
            else:
                color = None  # fuerza el cierre del último segmento

            if color != color_actual:
                if color_actual is not None and x > inicio_segmento:
                    self.rectangulos.append(
                        self.lienzo.create_rectangle(
                            inicio_segmento, 0, x, ALTURA_BARRA,
                            fill=color_actual, width=0,
                        )
                    )
                color_actual = color
                inicio_segmento = x
            x += 1

    def _bucle_progreso(self) -> None:
        self._redibujar()
        if self.tooltip_visible:
            self.etiqueta.configure(text=self._texto_tooltip())

        if not self.completada and self._trabajo_efectivo_restante() <= 0:
            self.completada = True
            self._celebrar()

        self.root.after(INTERVALO_PROGRESO_MS, self._bucle_progreso)

    # ---------------------------------------------------------------- brillo
    def _bucle_brillo(self) -> None:
        if not self.brillo or self.altura_visible <= 0:
            self._limpiar_brillo()
            self.root.after(INTERVALO_BRILLO_MS, self._bucle_brillo)
            return

        borde = self._borde_actual()
        if borde > self.ultimo_borde + 1e-6:
            self.intensidad_brillo = 1.0        # ha avanzado: enciende
        else:
            self.intensidad_brillo *= BRILLO_DECAIMIENTO
        self.ultimo_borde = borde

        self._pintar_brillo(borde)
        self.root.after(INTERVALO_BRILLO_MS, self._bucle_brillo)

    def _limpiar_brillo(self) -> None:
        for r in self.rect_brillo:
            try:
                self.lienzo.delete(r)
            except tk.TclError:
                pass
        self.rect_brillo = []

    def _pintar_brillo(self, borde: float) -> None:
        self._limpiar_brillo()
        if self.intensidad_brillo < 0.02 or borde <= 0:
            return
        px_borde = int(round(borde * self.ancho))
        if px_borde <= 0:
            return
        color_base = self._color(self.modo)
        # Degradado: de color normal (lejos de la punta) a casi blanco (en la punta).
        pasos = 8
        ancho_paso = max(1, BRILLO_ANCHO // pasos)
        for i in range(pasos):
            x2 = px_borde - i * ancho_paso
            x1 = x2 - ancho_paso
            if x2 <= 0:
                break
            cercania = 1.0 - (i / pasos)          # 1 en la punta, 0 al fondo
            t = cercania * self.intensidad_brillo * 0.9
            color = mezclar_hacia_blanco(color_base, t)
            self.rect_brillo.append(
                self.lienzo.create_rectangle(
                    max(0, x1), 0, x2, ALTURA_BARRA, fill=color, width=0,
                )
            )

    def _trabajo_efectivo_restante(self) -> float:
        ahora = datetime.now()
        trabajado = (ahora - self.inicio).total_seconds() - self._descanso_acumulado(ahora)
        return self.duracion.total_seconds() - trabajado

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
        return base + (
            f"  ·  quedan {formatear_duracion(restante)}"
            f" (salida {salida.strftime('%H:%M')})"
        )

    # ----------------------------------------------------------------- hover
    def _bucle_hover(self) -> None:
        x, y = _posicion_cursor()
        ahora = time.monotonic()
        en_zona = (
            self.base_y - max(ALTURA_BARRA, ZONA_DETECCION) - 1 <= y < self.base_y + 1
            and self.x <= x < self.x + self.ancho
        )

        if self.visibilidad == "auto":
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
            py = self.base_y - ALTURA_BARRA - alto_tt - 6
            self.tooltip.geometry(f"+{px}+{py}")
            _forzar_topmost(_hwnd(self.tooltip))

        self.root.after(INTERVALO_HOVER_MS, self._bucle_hover)

    def _gestionar_revelado(self, en_zona: bool, ahora: float) -> None:
        if en_zona:
            self.ocultar_a_partir_de = None
            if self.desde_cuando_encima is None:
                self.desde_cuando_encima = ahora
            elif (
                ahora - self.desde_cuando_encima >= SEGUNDOS_ESPERA
                and self.altura_visible < ALTURA_BARRA
                and self.animacion_id is None
            ):
                self._animar_altura(ALTURA_BARRA)
            return

        self.desde_cuando_encima = None
        if self.altura_visible == 0:
            return
        if self.ocultar_a_partir_de is None:
            self.ocultar_a_partir_de = ahora + SEGUNDOS_PERMANENCIA
        elif ahora >= self.ocultar_a_partir_de and self.animacion_id is None:
            self.ocultar_a_partir_de = None
            self._animar_altura(0)

    def _bucle_topmost(self) -> None:
        try:
            self.ventana.attributes("-topmost", True)
        except tk.TclError:
            return
        if self.altura_visible > 0:
            _aplicar_estilos(self.hwnd_barra, click_through=True)
            _forzar_topmost(self.hwnd_barra)
        self.root.after(INTERVALO_TOPMOST_MS, self._bucle_topmost)

    # ------------------------------------------------------------------ final
    def _celebrar(self) -> None:
        try:
            self.tooltip.withdraw()
            self.tooltip_visible = False
        except tk.TclError:
            pass
        Celebracion(self.root, self._terminar)

    # --------------------------------------------------------------- bandeja
    def _imagen_icono(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((6, 6, 58, 58), fill=self._color(self.modo))
        return img

    def _iniciar_bandeja(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Cambiar modo", self._accion_modo, default=True),
            pystray.MenuItem("Configurar", self._accion_editar),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Terminar", self._accion_terminar),
        )
        self.icono = pystray.Icon("barra_jornada", self._imagen_icono(), "Jornada", menu)
        threading.Thread(target=self.icono.run, daemon=True).start()

    def _accion_modo(self, *_args) -> None:
        self.root.after(0, self._alternar_modo)

    def _accion_editar(self, *_args) -> None:
        self.root.after(0, self._pedir_configuracion)

    def _accion_terminar(self, *_args) -> None:
        self.root.after(0, self._terminar)

    def _alternar_modo(self) -> None:
        nuevo = "descanso" if self.modo == "trabajo" else "trabajo"
        self.tramos.append((datetime.now(), nuevo))
        self._guardar_estado()
        self._refrescar_aspecto()

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
    BarraJornada().ejecutar()