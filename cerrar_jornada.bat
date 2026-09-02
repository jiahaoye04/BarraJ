@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Terminar jornada

set "ESTADO=%APPDATA%\barra_jornada\estado.json"

echo.
echo   ================================================
echo     TERMINAR LA JORNADA
echo   ================================================
echo.
echo   Esto cierra el programa y borra el progreso de hoy.
echo   Tu configuracion (horas y colores) se conserva.
echo.

choice /C SN /N /M "   Continuar? (S = si, N = no): "
if errorlevel 2 (
    echo.
    echo   Cancelado. No se ha tocado nada.
    echo.
    echo   Pulsa una tecla para salir.
    pause >nul
    exit /b
)

echo.
echo   Cerrando el programa...

set "ENCONTRADO="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*barra_jornada.py*' } | Select-Object -ExpandProperty ProcessId"`) do (
    set "ENCONTRADO=1"
    taskkill /F /PID %%P >nul 2>&1
    if errorlevel 1 (
        echo   [!] No se pudo cerrar el proceso %%P
    ) else (
        echo   [OK] Proceso %%P cerrado.
    )
)

if not defined ENCONTRADO echo   [ ] No habia ningun proceso en marcha.

echo.
echo   Borrando el progreso de hoy...

if exist "%ESTADO%" (
    del /F /Q "%ESTADO%" >nul 2>&1
    if exist "%ESTADO%" (
        echo   [!] No se pudo borrar el progreso.
        echo       Borralo a mano: %ESTADO%
    ) else (
        echo   [OK] Progreso borrado.
    )
) else (
    echo   [ ] No habia progreso guardado.
)

echo.
echo   Listo. La proxima vez que abras jornada.bat
echo   empezaras un dia nuevo desde cero.
echo.
echo   Pulsa una tecla para salir.
pause >nul