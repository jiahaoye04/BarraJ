# Barra de jornada

Una barra fina de color en el borde inferior de la pantalla que se va llenando a lo largo de tu jornada laboral.

## Cómo se usa

1. Haz doble clic en `jornada.bat`.
2. Se abre una ventanita. Rellena:
   - **Hora de inicio**: a qué hora has empezado. Puedes escribir `9` o `9:30`.
   - **Trabajo efectivo**: cuántas horas quieres trabajar hoy. `8` o `8:30`.
   - **Colores** (opcional): un color para trabajo y otro para descanso.
   - El resto de opciones (cómo avanza la barra, brillo, visibilidad) tienen valores por defecto que ya van bien; los explican las secciones de abajo.
3. Pulsa **Aceptar**. La barra aparece abajo y empieza a llenarse.

Y ya está. No hay nada más que hacer durante el día.

### Que no te lo pregunte todo cada mañana

En la ventanita hay una casilla: **"Recordar estas horas y colores para los próximos días"**. Si la marcas, mañana ya vendrá todo rellenado con esos valores y solo tendrás que confirmar la hora de entrada.

De fábrica son 8:30 horas. Puedes cambiarlo cuando quieras marcando otra vez la casilla.

## El icono de la bandeja

Junto al reloj de Windows aparece un **círculo de color**. Es el mando a distancia del programa:

- **Clic izquierdo** → cambia entre **trabajo** y **descanso**.
- **Clic derecho** → menú:
  - *Configurar*: cambia horas, colores y visibilidad.
  - *Terminar*: cierra el programa y borra el progreso del día.

> Si no ves el círculo, pulsa la flechita `^` de la barra de tareas: Windows esconde ahí los iconos nuevos. Puedes arrastrarlo fuera para tenerlo siempre a la vista.

## Trabajo y descanso

- **Azul (trabajo)**: el tiempo cuenta para tu jornada.
- **Verde (descanso)**: el tiempo **no** cuenta. La barra sigue avanzando, pero tu hora de salida se retrasa.

Ejemplo: pones 8 horas y te tomas 1 hora de comida. Saldrás 9 horas después de entrar. La barra se reajusta sola.

Los tramos se quedan pintados: verás en el color de cada momento cuándo trabajaste y cuándo descansaste.

## Ver cuánto te queda

Pon el ratón encima de la barra, abajo del todo. Aparece un aviso con el tiempo trabajado, el descanso acumulado y **a qué hora sales**. Al quitar el ratón desaparece.

## Barra siempre visible u oculta

En la ventana de configuración eliges entre dos formas de trabajar:

- **Siempre visible**: la barra está ahí todo el día. Es lo normal.
- **Oculta**: no se ve nada. Si dejas el ratón medio segundo en el borde de abajo, la barra sube sola; se queda 5 segundos más después de que retires el ratón y vuelve a esconderse.

Puedes cambiar de modo cuando quieras desde *Configurar*, en el icono de la bandeja.

## Cómo avanza la barra

En *Configurar* eliges cómo se llena:

- **Real**: avanza a ritmo constante. Una hora siempre ocupa lo mismo.
- **Equilibrado**: avanza poco en las primeras horas y más en las últimas. Como el día "se siente" más largo al principio y más corto al final, así la barra acompaña mejor esa sensación. Con el deslizador ajustas cuánto se nota (Lineal, Suave, Media, Fuerte); por defecto viene el que mejor encaja con tus horas.

## Brillo en la punta

Hay una casilla **"Brillo en la punta al avanzar"**. Con ella, el extremo de la barra se ilumina un instante cada vez que avanza y se apaga enseguida. Como la barra se mueve muy despacio, es una forma de ver "de un vistazo" que sigue corriendo. Puedes apagarlo si prefieres algo más sobrio.

## Cuando termines

Al completar tus horas, la pantalla se llena de emojis durante **10 segundos** y el programa se cierra solo. No molesta: puedes seguir usando el ordenador con normalidad mientras.

## Cosas a tener en cuenta

- **Si cierras el programa por error**, vuelve a abrirlo: recupera el progreso del día automáticamente, sin preguntarte nada.
- **La barra desaparece** si pones un programa a pantalla completa de verdad (vídeos, juegos con F11). Vuelve sola al salir de ese modo.
- **No estorba**: no puedes hacer clic en la barra, los clics pasan a través de ella.
- El progreso se borra al día siguiente. Cada mañana vuelve a pedirte la hora de inicio.

## Si algo falla

**La barra se ha quedado colgada, no responde o no encuentras el icono.**
Haz doble clic en **`cerrar_jornada.bat`**. Te pide confirmación y luego cierra el programa a la fuerza y borra el progreso del día. Tu configuración (horas y colores) se conserva. Al abrir `jornada.bat` de nuevo, empiezas un día limpio.

**Quieres ver el error concreto.**
Abre `jornada.bat` con el Bloc de notas, cambia `pythonw.exe` por `python.exe` y guárdalo. Al ejecutarlo verás una ventana negra con el mensaje de error. Cuando termines, déjalo como estaba.
