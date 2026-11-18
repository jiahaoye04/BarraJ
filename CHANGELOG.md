# Registro de cambios

Todos los cambios relevantes de BarraJ, de la versión más nueva a la más
antigua.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
las versiones siguen [Versionado Semántico](https://semver.org/lang/es/):

- **Mayor** (`2.0.0`): cambios que alteran cómo funciona algo que ya existía.
- **Menor** (`1.2.0`): funciones nuevas; lo anterior sigue igual.
- **Parche** (`1.2.1`): correcciones.

Las notas completas de cada versión, con el detalle de cada novedad, están en
[`docs/notas-de-version/`](docs/notas-de-version/).
Las decisiones técnicas, en [`docs/NOTAS_TECNICAS.md`](docs/NOTAS_TECNICAS.md).

---

## [2.0.0] — 2026-11-18 · «Con brillo propio»

[Notas de la versión completas →](docs/notas-de-version/2.0.0.md)

### Añadido

- **Avisos de hito**: una burbuja sobre la punta de la barra al llegar a un %
  de la jornada, a un tiempo trabajado o a un tiempo restante.
  - Mensajes propios, con varias frases al azar (`|`) y variables
    (`{restante}`, `{trabajado}`, `{salida}`, `{porcentaje}`).
  - Seis hitos de serie, editables.
  - Se cierran con un clic, sin quitar el foco.
  - Cada hito salta una vez al día; los ya pasados no se repiten al reabrir.
  - Modo **no molestar** con aplicaciones a pantalla completa, presentaciones o
    la sesión bloqueada.
  - Aviso de descanso largo, opcional.
- **Avance por saltos**: la barra acumula el avance y lo suelta de golpe con
  cada destello, más rápido cuanto más ha acumulado.
- **Estilos de color** por modo: plano, degradado, cambiante y en movimiento,
  con ocho paletas.
- **Brillo por umbral**: cada X–Y píxeles o cada N–M minutos, con rango
  aleatorio opcional. Estela tipo cometa, halo y fundidos.
- **Tema claro y oscuro** para la app, con cambio en vivo y barra de título
  oscura.
- **Tema de la barra** independiente: igual que la app, sistema (sigue a la
  barra de tareas), claro, oscuro con atenuación regulable, o sin tema.
- **Visibilidad *Oculta + asomar***: se asoma sola cada N minutos.
- **Descanso automático** por inactividad, desactivado de serie, con
  *Deshacer* en la bandeja.
- **Celebraciones**: emojis, emojis propios, imagen PNG, texto, minimalista o
  ninguna, con duración configurable y botón *Probar*.
- **Horas extra**: opción de seguir contando al completar la jornada.
- Altura de la barra configurable (2–8 px) y marcas por hora trabajada.
- Menú de la bandeja: *Probar celebración*, *Silenciar avisos hoy* y
  *Deshacer descanso automático*.
- Número de versión visible en el diálogo de configuración.

### Cambiado

- ⚠️ El **brillo** ya no se enciende en cada píxel: por defecto destella cada
  5 minutos. El comportamiento anterior sigue disponible como *Continuo*.
- ⚠️ `preferencias.json` y `estado.json` pasan a **formato 2**. Se convierten
  solos al arrancar, pero una versión 1.x ya no los lee bien.
- El diálogo de configuración se organiza en **cinco pestañas** y aplica los
  cambios visuales en directo; *Cancelar* los deshace.
- La barra se pinta como una única imagen con refresco variable, en lugar de
  rectángulos por columna.
- Solo puede haber una barra abierta a la vez.
- El estado y las preferencias se guardan de forma atómica.

### Corregido

- La barra tapaba el menú contextual del icono de la bandeja.
- Los emojis compuestos (🛋️, 👨‍💻, banderas, tonos de piel) podían partirse en
  la celebración y aparecer como huecos vacíos.

---

## [1.2.1] — 2026-11-05

### Corregido

- `jornada.bat` no arrancaba: tenía un marcador de ruta sin rellenar. Ahora
  prueba la ruta configurada y, si no existe, usa `pythonw` del PATH.

### Añadido

- Sección de requisitos en el README (`pystray` y `pillow`) y ayuda para ver
  el error cuando no arranca.
- `.gitignore`.

---

## [1.2.0] — 2026-10-29

### Añadido

- **Avance equilibrado**: primeras horas lentas y últimas rápidas, con cuatro
  intensidades (Lineal, Suave, Media, Fuerte) y una recomendada según la
  duración de la jornada.
- **Brillo en la punta** al avanzar, opcional.

### Cambiado

- La barra se pinta columna a columna para que las fronteras entre trabajo y
  descanso caigan bien también con el avance curvado.

### Corregido

- El diálogo de configuración no abría con `pythonw` por un error en las
  marcas del deslizador.

---

## [1.1.0] — 2026-07-20

### Añadido

- **Tramos**: cada franja conserva el color del modo en que estabas.
- Colores de trabajo y descanso configurables, también en caliente desde la
  bandeja.
- Preferencias recordadas entre días (casilla *Recordar*), separadas del
  progreso del día.
- Visibilidad **siempre** u **oculta** con revelado al pasar el ratón.
- Tooltip con trabajado, descanso y hora de salida estimada.
- Celebración con emojis al completar la jornada.
- `cerrar_jornada.bat` para cerrar a la fuerza y empezar un día limpio.

### Cambiado

- ⚠️ **El descanso ya no consume jornada**: cada minuto de descanso retrasa la
  hora de salida.
- La barra se ancla al área de trabajo, encima de la barra de tareas.

### Corregido

- La barra se sobrepintaba con algunas aplicaciones maximizadas.

---

## [1.0.0] — 2026-07-15

Primera versión.

### Añadido

- Barra de 4 px a lo ancho de la pantalla que se llena durante la jornada.
- Hora de inicio y duración al arrancar.
- Icono en la bandeja con cambio trabajo/descanso.
- Tooltip con el tiempo restante.
- Progreso del día guardado entre reinicios.

[2.0.0]: https://github.com/jiahaoye04/BarraJ/releases/tag/v2.0.0
[1.2.1]: https://github.com/jiahaoye04/BarraJ/commit/509f516
[1.2.0]: https://github.com/jiahaoye04/BarraJ/commit/492de63
[1.1.0]: https://github.com/jiahaoye04/BarraJ/blob/main/docs/NOTAS_TECNICAS.md
[1.0.0]: https://github.com/jiahaoye04/BarraJ/blob/main/docs/NOTAS_TECNICAS.md
