# BarraJ

![Versión](https://img.shields.io/badge/versi%C3%B3n-2.0.0-2f81f7)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Plataforma](https://img.shields.io/badge/plataforma-Windows%2011-555555)
![Dependencias](https://img.shields.io/badge/dependencias-pystray%20%C2%B7%20pillow-2e8b57)

**Una barra finísima encima de la barra de tareas que se llena a lo largo de
tu jornada laboral.**

BarraJ (en la bandeja, *Barra de jornada*) te dice de un vistazo cuánto llevas
y cuánto te queda, sin ventanas, sin alarmas y sin quitarte el foco. No se
puede pulsar ni estorba: los clics la atraviesan.

- Ves avanzar el día sin mirar el reloj.
- El descanso no cuenta como trabajo: tu hora de salida se recalcula sola.
- Te avisa con una burbuja cuando llevas la mitad o te quedan 10 minutos.
- Y al terminar, lo celebra.

> ### 🆕 Novedades de la 2.0 · «Con brillo propio»
>
> **Avisos de hito** en burbuja, **avance por saltos**, **degradados y colores
> en movimiento**, un **brillo** nuevo tipo cometa, **tema claro y oscuro**,
> **descanso automático** y **celebraciones a tu gusto**.
>
> [Leer las notas de la versión →](docs/notas-de-version/2.0.0.md)

---

## Índice

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Primeros pasos](#primeros-pasos)
- [El icono de la bandeja](#el-icono-de-la-bandeja)
- [Trabajo y descanso](#trabajo-y-descanso)
- [Configuración](#configuración)
- [Avisos de hito](#avisos-de-hito)
- [Brillo y avance por saltos](#brillo-y-avance-por-saltos)
- [Tema claro y oscuro](#tema-claro-y-oscuro)
- [Al terminar la jornada](#al-terminar-la-jornada)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Si algo falla](#si-algo-falla)
- [Tus datos](#tus-datos)
- [Versiones](#versiones)

---

## Requisitos

- **Windows 11.**
- **Python 3.10 o superior**, del instalador oficial de
  [python.org](https://www.python.org/downloads/).
- Dos librerías, para el icono de la bandeja y los gráficos. Instálalas una
  vez desde una consola:

  ```
  pip install pystray pillow
  ```

---

## Instalación

1. Descarga el repositorio: botón **Code → Download ZIP**, o
   `git clone https://github.com/jiahaoye04/BarraJ.git`.
2. Deja juntos en la misma carpeta:
   - `barra_jornada.py`
   - `jornada.bat`
   - `cerrar_jornada.bat`
3. Haz doble clic en `jornada.bat`.

**Si al abrirlo no pasa nada**, mira [Si algo falla](#si-algo-falla).

### Actualizar a una versión nueva

1. Cierra la barra: **Terminar** en el menú de la bandeja.
2. Sustituye `barra_jornada.py` por el nuevo.
3. Ábrela como siempre.

Tus preferencias se conservan y, si vienen de una versión antigua, se
convierten solas. Si tenías una jornada en marcha, sigue donde estaba. La
versión instalada aparece abajo a la izquierda en **Configurar**.

---

## Primeros pasos

1. Haz doble clic en `jornada.bat`. Se abre la ventana de configuración.
2. Rellena:
   - **Hora de inicio**: a qué hora has empezado. Vale `9`, `9:30`, `9.30` o
     `9,30`.
   - **Trabajo efectivo**: cuántas horas quieres trabajar hoy. `8` o `8:30`.
3. Pulsa **Aceptar**. La barra aparece abajo y empieza a llenarse.

Y ya está. No hay que hacer nada más durante el día.

> **Que no te lo pregunte todo cada mañana.** Marca **Recordar esta
> configuración para los próximos días** y mañana vendrá todo rellenado. De
> fábrica son 8:30 horas.

---

## El icono de la bandeja

Junto al reloj de Windows aparece un **círculo de color**: es el mando a
distancia del programa.

- **Clic izquierdo** → cambia entre **trabajo** y **descanso**.
- **Clic derecho** → menú:

| Opción | Qué hace |
|---|---|
| **Cambiar modo** | Lo mismo que el clic izquierdo. |
| **Configurar** | Abre la ventana de configuración. |
| **Probar celebración** | Lanza la celebración elegida, para verla sin esperar. |
| **Silenciar avisos hoy** | Calla las burbujas hasta mañana. |
| **Deshacer descanso automático** | Devuelve a trabajo el último descanso marcado por inactividad. |
| **Terminar** | Cierra el programa y borra el progreso del día. |

> Si no ves el círculo, pulsa la flechita `^` de la barra de tareas: Windows
> esconde ahí los iconos nuevos. Arrástralo fuera para tenerlo siempre a la
> vista.

---

## Trabajo y descanso

- **Trabajo** (azul de serie): el tiempo cuenta para tu jornada.
- **Descanso** (verde de serie): el tiempo **no** cuenta. La barra se reajusta
  y tu hora de salida se retrasa.

Ejemplo: pones 8 horas y te tomas 1 hora para comer. Saldrás 9 horas después
de entrar.

Cada tramo se queda pintado en el color de su momento, así ves cómo ha ido el
día.

**¿Cuánto te queda?** Pon el ratón abajo del todo, sobre la barra. Aparece un
aviso con lo trabajado, el descanso acumulado, lo que falta y **a qué hora
sales**.

### Descanso automático

Opcional, en **Configurar → General**. Si pasas N minutos sin tocar ratón ni
teclado, la barra pasa a descanso **desde tu último movimiento**. Al volver,
una burbuja te dice cuánto ha contado. ¿Era una reunión? **Deshacer descanso
automático** en la bandeja.

---

## Configuración

Cinco pestañas. Casi todo lo visual se ve **en directo** en la barra mientras
tocas; **Cancelar** lo deja todo como estaba.

### General

- **Hora de inicio** y **trabajo efectivo**.
- **Avance de la barra**:
  - *Real*: ritmo constante.
  - *Equilibrado*: lento al principio y rápido al final, que es como se
    siente el día. Cuatro intensidades: Lineal, Suave, Media, Fuerte. De
    serie, la que mejor encaja con tus horas.
- **Al completar la jornada**: celebrar y cerrar, o celebrar y **seguir
  contando horas extra**.
- **Inactividad**: descanso automático.

### Barra

- **Visibilidad**:

| Modo | Qué hace |
|---|---|
| **Siempre visible** | Está ahí todo el día. |
| **Oculta** | Sube al dejar el ratón en el borde de abajo y se esconde 5 segundos después de quitarlo. |
| **Oculta + asomar** | Además, se asoma sola cada N minutos durante unos segundos. |

- **Altura** de 2 a 8 píxeles y **marcas** por cada hora trabajada.
- **Color en trabajo** y **en descanso**, cada uno con su estilo:

| Estilo | Qué hace |
|---|---|
| **Plano** | Un solo color. |
| **Degradado** | Del color 1 al 2 a lo largo de toda la barra. |
| **Cambiante** | Un color que pasa del 1 al 2 según avanza la jornada. |
| **En movimiento** | Un degradado que se desplaza suavemente. |

- **Paletas**: Océano, Atardecer, Aurora, Neón, Bosque, Fuego, Lavanda y
  Grafito.
- **Vista previa** animada.

### Avisos, Celebración y Apariencia

Las tres tienen su propia sección más abajo.

---

## Avisos de hito

Una burbuja aparece sobre la punta de la barra cuando llegas a un punto que
tú eliges, y se va sola a los pocos segundos. **Haz clic en ella** para
quitarla al momento.

En **Configurar → Avisos**, cada hito tiene tipo, valor y mensaje:

| Tipo | Valor | Salta cuando… |
|---|---|---|
| **% jornada** | `25` | llevas el 25 % del trabajo efectivo |
| **Trabajado** | `6:00` | llevas 6 horas trabajadas |
| **Restante** | `0:30` | quedan 30 minutos |

- **Varias frases** separadas por `|`: cada día sale una al azar.
- **Variables**: `{restante}`, `{trabajado}`, `{salida}` y `{porcentaje}`.
  Ejemplo: `10 minutos. Sales a las {salida}.`
- Los porcentajes cuentan el **trabajo real**, no lo que se ve con el avance
  equilibrado.
- Cada hito salta **una vez al día**, aunque reinicies.
- **No molestar**: con un juego, un vídeo a pantalla completa, una
  presentación o la sesión bloqueada, los avisos esperan.
- **Aviso de descanso largo**, opcional, con la variable `{descanso}`.

---

## Brillo y avance por saltos

En **Configurar → Apariencia → Brillo de la punta**.

El **brillo** es un destello tipo cometa en la punta de la barra:

| Modo | Cuándo destella |
|---|---|
| **Continuo** | En cada píxel que avanza. |
| **Cada X a Y píxeles** | Cada vez que la barra recorre esa distancia. |
| **Cada N a M minutos** | Cada ese tiempo. De serie, cada 5 minutos. |

Con dos valores distintos, cada destello elige uno al azar dentro del rango;
con dos iguales, el intervalo es fijo.

**Avance por saltos**: la barra se queda quieta, acumula el avance y lo suelta
de golpe con cada destello. Cuanto más ha acumulado, más rápido corre la
punta: 5 minutos se sueltan en 0,6 s y 30 minutos en 1,5 s. El tooltip y los
avisos usan siempre el tiempo real.

---

## Tema claro y oscuro

- **Tema de la aplicación**: Sistema, Claro u Oscuro. Afecta a la ventana de
  configuración (barra de título incluida), al tooltip y a los avisos. Cambia
  al momento y, en *Sistema*, sigue a Windows en unos segundos.
- **Tema de la barra**, por separado:

| Opción | Qué hace |
|---|---|
| **Igual que la app** | Sigue al tema de arriba. |
| **Sistema** | Sigue a la **barra de tareas** de Windows, que puede ir distinta de las aplicaciones. |
| **Claro** | Fondo claro. |
| **Oscuro** | Fondo oscuro y colores **atenuados** para que no deslumbren (0–40 %, regulable). |
| **Sin tema** | Colores tal cual. |

---

## Al terminar la jornada

Al completar tus horas llega la **celebración**, que eliges en **Configurar →
Celebración**:

| Estilo | Qué verás |
|---|---|
| **Emojis** | Una lluvia de emojis. |
| **Emojis propios** | La misma lluvia, con los tuyos. |
| **Imagen PNG** | Tu imagen cayendo en varios tamaños. |
| **Texto** | Una tarjeta con tu frase y el resumen del día. |
| **Minimalista** | Una burbuja discreta sobre la barra. |
| **Ninguna** | Nada. |

Puedes seguir trabajando mientras: no bloquea nada. Después, según lo que
hayas elegido, la barra **se cierra sola** o **sigue contando horas extra**
en su propio color.

---

## Preguntas frecuentes

**Si cierro el programa por error, ¿pierdo el día?**
No. Vuelve a abrirlo: recupera el progreso automáticamente, sin preguntar.

**Si lo abro dos veces, ¿salen dos barras?**
No. La segunda se cierra sola.

**Me marcó descanso mientras veía un vídeo.**
*Deshacer descanso automático* en la bandeja. Si te pasa a menudo, sube los
minutos o desactiva la opción.

**¿La barra tapa los menús del clic derecho?**
No. Mientras haya un menú abierto, se queda debajo, y al cerrarlo vuelve
arriba en menos de medio segundo.

**La barra desaparece con algunos programas.**
Con los que van a pantalla completa de verdad (vídeos, juegos con F11). Vuelve
sola al salir de ese modo.

**¿Gasta mucho?**
No. En reposo se actualiza una vez por segundo; solo se anima durante un
destello, un salto o con el degradado en movimiento.

**El progreso se borra al día siguiente, ¿es normal?**
Sí. Cada mañana empieza un día nuevo y te pide la hora de inicio.

---

## Si algo falla

**Al hacer doble clic en `jornada.bat` no pasa nada.**
Lo más habitual es que falten `pystray` o `pillow` (ver
[Requisitos](#requisitos)) o que Windows no encuentre Python. En el segundo
caso, edita `jornada.bat` con el Bloc de notas y pon en la línea
`set "PYTHONW=..."` la ruta completa a tu `pythonw.exe`.

**La barra se ha quedado colgada o no encuentras el icono.**
Haz doble clic en **`cerrar_jornada.bat`**. Te pide confirmación, cierra el
programa a la fuerza y borra el progreso del día. Tu configuración se
conserva.

**Quieres ver el error concreto.**
Abre `jornada.bat` con el Bloc de notas, cambia `pythonw` por `python` en las
dos líneas donde aparece y guárdalo. Al ejecutarlo verás una ventana negra con
el mensaje. Cuando termines, déjalo como estaba.

---

## Tus datos

Todo se queda en tu equipo, en `%APPDATA%\barra_jornada\`:

| Fichero | Qué guarda | Cuándo se borra |
|---|---|---|
| `preferencias.json` | Tu configuración recordada | Nunca, salvo que lo borres tú |
| `estado.json` | El progreso de hoy | Con *Terminar*, o al cerrarse sola al final del día; al día siguiente ya no se usa |

Se escriben de forma segura: un apagado brusco no los deja a medias.

---

## Versiones

| Versión | Fecha | Lo principal |
|---------|-------|--------------|
| **2.0.0** | 2026-11-18 | Avisos de hito, avance por saltos, estilos de color, temas, celebraciones · [notas](docs/notas-de-version/2.0.0.md) |
| 1.2.1 | 2026-11-05 | Arreglo del lanzador y requisitos en el README |
| 1.2.0 | 2026-10-29 | Avance equilibrado y brillo en la punta |
| 1.1.0 | 2026-07-20 | Tramos de color, el descanso no consume jornada, modo oculto |
| 1.0.0 | 2026-07-15 | Primera versión |

- [Registro de cambios completo](CHANGELOG.md)
- [Notas de versión](docs/notas-de-version/)
- [Notas técnicas de desarrollo](docs/NOTAS_TECNICAS.md)
