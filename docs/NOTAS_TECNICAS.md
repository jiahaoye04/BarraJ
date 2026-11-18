# Notas técnicas de desarrollo

El porqué de las decisiones de diseño, los fallos encontrados por el camino y
lo que queda pendiente. Es el cuaderno de desarrollo, no documentación de
usuario: los cambios visibles están en [`CHANGELOG.md`](../CHANGELOG.md) y en
las [notas de versión](notas-de-version/).

Las entradas van de la más nueva a la más antigua.

---

## 2.0.0 · 2026-11-18 — «Con brillo propio»

Reescritura de casi todo lo visual y del diálogo. Sigue siendo un único
fichero (`barra_jornada.py`, ~3.000 líneas) con las mismas dependencias:
`pystray` y `pillow`. El tema del sistema se lee con `winreg` (biblioteca
estándar).

### Motor de pintado: de rectángulos a una imagen

- La v1.2 recorría la barra columna a columna y creaba un rectángulo por
  grupo de color en cada refresco. Con brillo animado y degradados eso
  significaba cientos de items de `Canvas` creados y borrados por fotograma en
  una ventana click-through: el cuello de botella que estaba apuntado.
- Ahora la barra es **una sola imagen**. `PintorBarra.pintar()` compone una
  fila RGB de 1 px de alto con Pillow, la escala en vertical con `NEAREST` y
  la sustituye en un único `create_image`. Nada se crea ni se borra por
  fotograma.
- Las **fronteras de tramo se calculan analíticamente**: la curva es monótona,
  así que la frontera de un tramo que empieza en el instante *t* cae en
  `x = curvar(lineal(t)) · ancho`. Mismo resultado que el recorrido por
  columnas de la v1.2, sin el bucle de píxeles.
- **Tiras cacheadas** por `(tipo, c1, c2, ancho)`. El degradado en movimiento
  usa una tira cíclica de `2 × ancho` y un recorte desplazado por el tiempo,
  así que animarlo no regenera ningún degradado.
- Los degradados **se mezclan en luz lineal** (gamma 2.2) para evitar la banda
  apagada del centro que sale al interpolar en sRGB.
- **Refresco variable** con un único bucle que se reprograma a sí mismo:
  1 s en reposo, 50 ms con degradado en movimiento y 33 ms durante un destello
  o un salto. `_despertar_render()` cancela el `after` pendiente y fuerza un
  fotograma inmediato.
  - **Fallo encontrado:** llamar a `_bucle_render()` directamente en el
    arranque, además de despertarlo desde `_fijar_altura`, dejaba **dos
    cadenas** de `after` en paralelo. Ahora solo se arranca vía
    `_despertar_render()`.
- La barra **sigue sin `WS_EX_LAYERED`** (ver 1.1.0). El halo del brillo se
  dibuja dentro de la propia barra, sobre la parte aún vacía, no en una
  ventana más alta.

### Brillo y avance por saltos

- Envolvente del pulso: ataque senoidal de 0,25 s, meseta de 0,35 s y caída
  en coseno de 1,6 s (`envolvente_brillo`). Estela de 56 px con caída
  `(1 − d/ancho)^2,4` y halo de 6 px por delante.
- Un pulso que llega mientras otro se apaga arranca desde la intensidad
  actual (`pulso_base`), así no hay parpadeo.
- Disparadores: *continuo* (cada píxel), *píxeles* (umbral = punta +
  `randint(min, max)`) o *minutos* (`uniform(min, max)`). Mínimo y máximo
  iguales equivalen a un intervalo fijo.
- **Avance por saltos.** Se separan `px_real` (lo que marca el tiempo) y
  `px_visible` (lo que se pinta). Mientras no hay destello, `px_visible` se
  queda quieto y los segmentos se recortan en él (`recortar_segmentos`). Un
  destello arranca un deslizamiento con *ease-out* cúbico hasta `px_real`.
  - Duración: `0,6 s · √(acumulado / 300 s)`, entre 0,25 s y 3 s. Con la raíz
    cuadrada, un salto de 30 min dura 2,4 veces lo de uno de 5 min y recorre
    6 veces más distancia, es decir, corre 2,4 veces más rápido. El requisito
    era que 0,6 s estuviera bien para un ciclo de 5 min, pero que un ciclo de
    30 min no se soltara en el mismo tiempo, sino con más velocidad.
  - Mientras la punta corre, la meseta del pulso se alarga para que la cabeza
    blanca siga encendida hasta llegar.
  - Cualquier destello (de ciclo, de hito o de asomar) suelta lo acumulado y
    reinicia el ciclo. Al completar la jornada se fuerza un destello antes de
    celebrar, para que la barra llegue al final.
  - `px_visible` nunca puede quedar por delante de `px_real` (pasaría al
    cambiar la hora de inicio): se recorta en cada recálculo.

### Avisos de hito y burbujas

- Hitos `{tipo, valor, mensaje}` con tipos `porcentaje`, `trabajado` y
  `restante`. El porcentaje se mide sobre **trabajo real**, no sobre la
  fracción curvada: con la curva Media, la barra a la mitad corresponde a
  ~67 % del trabajo.
- Identidad del hito: `tipo|valor`. Editar solo el mensaje no hace que vuelva
  a saltar. Los disparados se guardan en el estado del día.
- `_sincronizar_hitos()` marca como vistos, en silencio, los que ya se
  cumplen al arrancar o al aceptar la configuración. Sin eso, abrir la barra a
  media jornada (o añadir un hito del 25 % a las cuatro de la tarde) soltaba
  una ráfaga de avisos.
- `restante` exige `objetivo > valor`: con una jornada de 20 min, un hito de
  «quedan 30 min» saltaría nada más empezar.
- Variables con `str.replace`, no `str.format`: así unas llaves sueltas en un
  mensaje no lanzan `KeyError`.
- **Burbuja**: `Toplevel` sin bordes con color clave y `-alpha` para el
  fundido. Se dibuja con polígonos de `Canvas` (rectángulo redondeado con
  `smooth=True` y cola triangular). No se usa Pillow porque el texto
  antialiasado sobre el color clave deja un halo oscuro; en el `Canvas`, el
  texto se suaviza contra el fondo de la propia burbuja.
- **Clic para cerrar**: la burbuja **no** lleva `WS_EX_TRANSPARENT`, pero sí
  `WS_EX_NOACTIVATE`, así que recibe el clic sin robar el foco. Las zonas del
  color clave siguen dejando pasar el clic por cómo Windows hace el *hit
  testing* de las ventanas con color clave.
- Cola en `GestorBurbujas`: una burbuja a la vez, sondeo cada 300 ms. Antes de
  mostrarla pide a la barra que se asome (`asomar()`), por si está oculta.
- **No molestar**: `SHQueryUserNotificationState`. Estados 1 (bloqueado o
  salvapantallas), 2 (pantalla completa), 3 (Direct3D a pantalla completa) y 4
  (presentación) aplazan avisos y celebración. El *Asistente de
  concentración* no se expone de forma fiable por esa API; no se promete.

### Descanso automático

- `GetLastInputInfo` contra `GetTickCount`, con máscara de 32 bits para
  sobrevivir al desbordamiento a los 49,7 días.
- Pasado el umbral, se inserta un tramo de descanso **retroactivo** en
  `ahora − inactivo`, nunca antes del último tramo existente.
- `descanso_auto = {desde, hasta}` permite deshacerlo quitando exactamente esos
  dos tramos. Si se deshace mientras el usuario sigue sin tocar nada,
  `_ignorar_inactividad` impide que se vuelva a marcar en el siguiente
  segundo.
- Cambiar de modo a mano durante un descanso automático lo cierra con esa
  hora como `hasta`.

### Temas

- `AppsUseLightTheme` para el tema de la app; `SystemUsesLightTheme` para la
  opción *Sistema* de la barra. Son ajustes distintos en Windows, y la barra
  se apoya sobre la barra de tareas, que sigue al segundo.
- Atenuación en oscuro: desatura hacia la luminancia (60 % de la intensidad)
  y luego multiplica el brillo. El azul puro sobre fondo oscuro deslumbra más
  por la saturación que por la luminosidad.
- **Diálogo con cambio en vivo**, mismo enfoque que ExtractJ pero sin `ttk`:
  cada widget se registra con un papel (`lbl`, `tenue`, `entry`, `opcion`,
  `boton`, `spin`, `desplegable`…) y `_aplicar_tema()` los recolorea desde la
  paleta activa. Los widgets destruidos (filas de hitos borradas) se purgan
  del registro en cada repintado.
- Barra de título: `DwmSetWindowAttribute` (atributo 20, o 19 en Windows 10
  antiguo) seguido de `SetWindowPos(... SWP_FRAMECHANGED)`. Sin el
  `FRAMECHANGED`, el cambio no se ve hasta que la ventana pierde el foco.
- El tema del sistema se sondea cada 3 s; Windows no avisa a Tk del cambio.

### Ventanas y z-order

- **El menú de la bandeja quedaba tapado.** Los menús contextuales también son
  topmost, y el bucle de 500 ms volvía a subir la barra por encima del menú
  recién abierto. Ahora `_forzar_topmost` y `_bucle_topmost` comprueban antes
  si hay una ventana visible de clase `#32768` (la de todos los menús
  contextuales clásicos, enumerada con `FindWindowExW`). Si la hay, no tocan
  el z-order. También se salta `attributes("-topmost", True)`, porque Tk
  también llama a `SetWindowPos` con `HWND_TOPMOST` y vuelve a subirla.
- El menú moderno del Explorador de Windows 11 es una ventana XAML de otra
  clase: queda pendiente.
- **Instancia única** con `CreateMutexW("Local\BarraJornada_instancia_unica")`.
  Se pone `set_last_error(0)` antes de llamarlo, porque si el mutex es nuevo
  Windows no limpia el último error.

### Celebraciones

- Base `_VentanaFlotante` (sin bordes, topmost, color clave, fundidos) y
  clases intercambiables: `CelebracionEmojis`, `CelebracionImagen`,
  `CelebracionTexto`. La minimalista reutiliza la burbuja.
- **Emojis compuestos**: la v1.x hacía `random.choice` sobre la cadena, es
  decir, sobre *code points*. `🛋️` son dos (U+1F6CB + U+FE0F), así que a veces
  salía el selector de variación suelto como partícula vacía.
  `separar_emojis()` agrupa por selectores, tonos de piel, ZWJ, teclas y
  pares de indicadores regionales.
- **Imagen PNG**: el canal alfa se binariza en 128 antes de pegarla sobre el
  color clave. El color clave no admite semitransparencia, y los bordes
  suavizados dejaban un halo oscuro.
- **Texto**: tarjeta con fondo propio detrás del texto por el mismo motivo
  (ClearType suaviza contra el fondo). La imagen se carga **antes** de crear
  la ventana: si falla, no queda una ventana vacía y se cae a emojis.

### Persistencia

- `estado.json` formato 2: `inicio`, `tramos`, una **copia de la
  configuración del día**, `completada`, hitos disparados, descansos avisados,
  silencio y descanso automático.
- `normalizar_config()` valida clave a clave contra la base y migra la v1.x
  (`color_trabajo` / `color_descanso` → `estilo_*` plano). Se usa tanto para
  las preferencias como para el estado.
- Escritura atómica: `fichero.tmp` + `os.replace`.
- `completada` se guarda: en modo horas extra, reabrir no vuelve a celebrar; en
  modo cerrar, una celebración aplazada por *no molestar* se muestra al
  reabrir.

### Pruebas

Probado en Linux con Xvfb, con un arnés que sustituye `ctypes.windll` y
`pystray` por imitaciones: migración de estado 1.x, hitos (incluido que no
salten los ya pasados), inactividad con deshacer, asomar, temas, las seis
celebraciones, horas extra, persistencia, avance por saltos (retención, punto
intermedio del deslizamiento y llegada exacta), clic en burbujas y tarjeta, y
repintado del diálogo claro → oscuro → claro. Lo que depende del
compositor de Windows (fundidos con color clave, barra de título, menús
contextuales reales) se valida a mano.

---

## 1.2.1 · 2026-11-05 — Arreglos de instalación

- `jornada.bat` tenía un marcador de ruta sin rellenar y sin alternativa, así
  que no arrancaba. Ahora sigue el mismo esquema que el lanzador de ExtractJ:
  prueba la ruta configurada y, si no existe, usa `pythonw` del PATH.
- `README.md`: añadida sección de requisitos (`pystray` y `pillow`). Con
  `pythonw` un import fallido no muestra nada, así que era fácil quedarse sin
  saber por qué no abría.
- `README.md`: la sección *Si algo falla* explica el caso de que no arranque y
  corrige las instrucciones para ver el error.
- Añadido `.gitignore` para `__pycache__/`.

---

---

## 1.2.0 · 2026-10-29 — Ritmo de avance y brillo de punta

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

## 1.1.0 · 2026-07-20 — Revisión completa

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

## 1.0.0 · 2026-07-15 — Versión inicial

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

## Pendiente / ideas

- Menú contextual moderno del Explorador de Windows 11: es una ventana XAML de
  otra clase y puede quedar debajo de la barra. Hay que averiguar su clase en
  un equipo real y añadirla a `menu_contextual_abierto()`.
- Emojis a color dentro de las burbujas. Tk los pinta en monocromo; habría que
  rasterizar las líneas con emojis con Pillow, como en la celebración.
- Color histórico por tramo: hoy, al cambiar un color se recolorean también
  los tramos pasados. Haría falta guardar el estilo dentro de cada tramo.
- La barra desaparece con aplicaciones a pantalla completa real. Sin solución
  limpia.
- Varios monitores: la barra solo vive en el principal.
- Empaquetar con PyInstaller y meter acceso directo en `shell:startup`.
- Detectar reuniones o vídeos (micrófono en uso, `SetThreadExecutionState` de
  otra app) para no marcar descanso automático en falso.
