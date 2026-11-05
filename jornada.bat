@echo off
rem Lanzador de la Barra de jornada. Debe estar en la misma carpeta que el .py
rem Si Python no esta en el PATH, cambia la ruta de abajo por la de tu pythonw.exe

set "PYTHONW={your_location}\Python\bin\pythonw.exe"

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0barra_jornada.py"
) else (
    start "" pythonw "%~dp0barra_jornada.py"
)
