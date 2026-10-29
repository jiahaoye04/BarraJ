# Registro de cambios

Notas técnicas para mí, no documentación de usuario. Para eso está `README.md`.

---

## 2026-07-15 — Versión inicial

Primera versión funcional. Alcance mínimo:

- Ventana `tkinter` sin bordes, ancho completo, 4 px, en el borde inferior.
- Click-through vía `WS_EX_TRANSPARENT`; `topmost` reafirmado en bucle.
- Configuración al arrancar: hora de inicio y duración de la jornada.
- Colores fijos en constantes, sin posibilidad de cambiarlos desde la interfaz.
- Barra de un solo color, rectángulo único redimensionado cada segundo.
- Icono en bandeja (`pystray`) con switch trabajo/descanso y salir.
- Tooltip con tiempo restante al pasar el cursor.
- Persistencia del progreso del día en `%APPDATA%\barra_jornada\estado.json`.

**Limitación de diseño:** el descanso solo cambiaba el color del conjunto de la
barra y **consumía jornada**. El denominador era fijo (`duracion`), así que
descansar no retrasaba la hora de salida. Modelo incorrecto para mi horario real.

---

## 2026-07-20 — Revisión completa

### Modelo de tiempo

- El estado pasa de un único `modo` a una **lista de tramos** `[(desde, modo)]`.
  La barra se pinta con un rectángulo por tramo, así cada franja conserva el
  color del modo en que se estaba. Ya no se recolorea el conjunto.
- **El descanso deja de consumir jornada.** Denominador dinámico:
  `total_efectivo = duracion + descanso_acumulado(ahora)`.
  Se recalcula en cada refresco (1 s), no cada N minutos: el reajuste es
  continuo. Efecto colateral esperado: durante un descanso el conjunto de la
  barra retrocede levemente porque crece el denominador.
- `_trabajo_efectivo_restante()` decide la finalización, no la fracción pintada.
  Durante un descanso numerador y denominador crecen a la par, así que la
  fracción tiende a 1 sin alcanzarlo; usar la fracción como condición de fin
  habría sido un bug.
- Tooltip ampliado: trabajado / objetivo, descanso acumulado y **hora de salida
  estimada**, que se desplaza sola conforme se descansa.

### Configuración

- Colores de trabajo y descanso configurables (`tkinter.colorchooser`), en el
  arranque y en caliente desde la bandeja. Se repintan tramos e icono al vuelo
  vía `_refrescar_aspecto()`.
- Separación **preferencias / estado**:
  - `preferencias.json` — duración, colores y visibilidad por defecto. Permanente.
  - `estado.json` — progreso del día. Se borra al terminar.

  Esto arregla un fallo de la versión anterior: los colores vivían solo en el
  estado diario y se reseteaban cada mañana. La casilla "Recordar" del diálogo
  es lo que escribe en preferencias; sin marcarla, el cambio es solo para hoy.
- Valor de fábrica de la jornada: 8:30, sobrescribible por el usuario.
- `parsear_hhmm()` acepta `9`, `9:30`, `9.30`, `9,15`. Un número suelto son
  horas en punto. Validado contra entradas vacías, no numéricas y `1:2:3`.

### Visibilidad

- Dos modos, persistidos: `siempre` y `auto`.
- En `auto`: oculta por defecto; revelado tras 0,5 s de permanencia del cursor
  en el borde; animación de subida modificando la geometría (altura 0→4 px con
  la `y` compensada); permanece 5 s tras salir el cursor y se retira.
- La detección usa `GetCursorPos` contra `ZONA_DETECCION`, no eventos de la
  ventana: la barra está oculta y no puede recibir eventos.
- Animación por geometría, **no** por alfa, para no reintroducir
  `WS_EX_LAYERED` (ver más abajo).

### Final de jornada

- Al completarse: overlay a pantalla completa con emojis animados, 10 s, y
  autocierre del programa.
- Transparencia por `-transparentcolor` con color clave `#010203`.
  Click-through, así que no bloquea el trabajo mientras dura.
- Los emojis se rasterizan con Pillow desde `seguiemj.ttf` con
  `embedded_color=True`. Tk los pintaría en monocromo. Cacheados por
  `(emoji, tamaño)`. Fallback a `create_text` si falla la carga de la fuente.
- El icono de bandeja **no** se detiene al iniciar la celebración: durante esos
  10 s el proceso sigue vivo y hay que poder cerrarlo.

### Problemas de ventana resueltos por el camino

- **La barra de tareas la tapaba.** No tiene arreglo: la taskbar de Windows 11
  vive en una z-order band superior; solo se salta con `uiAccess` (app firmada,
  nivel instalador). No compensa. Solución adoptada: anclar al borde inferior
  del **área de trabajo** (`SPI_GETWORKAREA`) en vez del borde físico. Queda
  `PEGADA_AL_BORDE_FISICO` como flag por si algún día pongo la taskbar en
  ocultación automática.
- **HWND incorrecto.** `GetParent` sobre una ventana `overrideredirect` no
  devuelve fiablemente la ventana real. Cambiado a `GetAncestor(..., GA_ROOT)`.
- **Eclipse maximizado se sobrepintaba.** Los estilos extendidos eran correctos
  (`0x80800A8` verificado), así que no era z-order sino repintado de ventana
  layered. Se quitó `WS_EX_LAYERED` de la barra, que además entraba en conflicto
  con el `-transparentcolor` del overlay de celebración. Bucle de topmost bajado
  a 500 ms y con `ShowWindow(SW_SHOWNOACTIVATE)` para autorrecuperarse.

### Utilidades

- `jornada.bat` — lanzador con `pythonw.exe` (ruta absoluta; el alias del
  Microsoft Store tapaba el Python real en el PATH).
- `cerrar_jornada.bat` — terminación forzada. Filtra por `CommandLine` con
  `Get-CimInstance Win32_Process`, no mata todos los `pythonw`. Además borra
  `estado.json` (no `preferencias.json`), replicando el *Terminar* de la
  bandeja: matar el proceso a secas dejaba el estado a medias y al reabrir
  recuperaba una jornada que ya no quería. Confirmación `choice` previa, que
  la acción es destructiva.
- `README.md` — instrucciones para usuario no técnico.

---

## 2026-10-29 — Ritmo de avance y brillo de punta

### Progreso real vs. curvado

- Dos modos nuevos, persistidos: `progreso = "real"` (lineal, como hasta
  ahora) y `"curva"` (primeras horas lentas en barra, últimas rápidas, para
  compensar la percepción del paso del tiempo).
- La curva es `fraccion_trabajo ** exp`, aplicada **solo sobre la fracción de
  trabajo** (no sobre el reloj: el descanso ya deforma el denominador aparte).
  Intensidades: Lineal 1.0 / Suave 1.35 / Media 1.7 / Fuerte 2.3, elegidas con
  un `tk.Scale` de 4 topes.
- `curva = None` en preferencias significa "usar la recomendada por horas"
  (`curva_recomendada`: ≤6h Suave, 6-9h Media, >9h Fuerte). Se resuelve a una
  etiqueta concreta en el arranque vía `_resolver_curva()`.

### Repintado columna a columna

- **Cambio de fondo del dibujado.** Con curva, un rectángulo por tramo deja de
  valer: la deformación no es lineal *dentro* de un tramo, así que un tramo
  largo se curvaría por dentro y las fronteras caerían mal. `_redibujar()` pasa
  a recorrer columnas de píxel: cada x → fracción curvada → fracción lineal
  (inversa `fc ** (1/exp)`) → instante real → modo activo → color. Se agrupan
  columnas contiguas del mismo color en un solo rectángulo. Validado que las
  fronteras trabajo/descanso quedan en orden también curvadas.
- En modo lineal (`exp == 1.0`) la inversa es la identidad; mismo resultado que
  antes, solo que calculado por columnas. Coste despreciable a 1 refresco/s.

### Brillo de la punta

- Versión adoptada: degradado **dentro** de la barra, no halo saliente. Se
  descartó el halo porque exigía una ventana más alta con color clave, lo que
  reintroduce el `WS_EX_LAYERED`/`-transparentcolor` que ya dio repintado con
  Eclipse. El degradado no toca el z-order.
- Bucle propio (`_bucle_brillo`, 60 ms): compara el borde pintado con el del
  frame anterior; si avanzó, enciende a 1.0; si no, decae por
  `BRILLO_DECAIMIENTO` (~1 s hasta apagarse). Los últimos `BRILLO_ANCHO` px se
  mezclan hacia blanco con `mezclar_hacia_blanco`, más intenso en la punta.
- Opcional, persistido (`brillo`). Se omite si la barra está oculta.

### Config

- El diálogo crece con: radios Real/Equilibrado, deslizador de intensidad (gris
  cuando Real), y casilla de brillo. Deslizador construido con `fila`
  incremental para no renumerar filas a mano.
- **Bug corregido en caliente:** `grid(sticky="center")` no es válido en Tk
  (`sticky` solo acepta n/e/s/w); las marcas intermedias del deslizador
  reventaban el arranque con `pythonw` (terminal que parpadea y se cierra).
  Centrado = `sticky=""`.
- Observado: el equipo del trabajo corre **Python 3.14**.

---

## Pendiente / ideas

- Al cambiar de color se recolorean también los tramos pasados. Decidido así a
  propósito; si en algún momento quiero color histórico por tramo, hay que
  guardar el color dentro de cada entrada de `tramos`.
- La barra desaparece con aplicaciones a pantalla completa real. Sin solución
  limpia.
- Empaquetar con PyInstaller y meter acceso directo en `shell:startup`.
- Con `ALTURA_BARRA = 4` la animación de revelado se percibe más como un
  parpadeo que como un deslizamiento. Subir altura si molesta.
