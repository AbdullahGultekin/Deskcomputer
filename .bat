@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ---- Config ----
set APP_NAME=PizzeriaApp
set ENTRY=main.py
set ICON=icon.ico

REM ---- Virtualenv activeren ----
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [FOUT] Virtualenv niet gevonden op .venv\Scripts\activate.bat
  echo Maak/installeer eerst je .venv en benodigde packages.
  exit /b 1
)

REM ---- Zorg dat PyInstaller aanwezig is ----
python -m pip show pyinstaller >NUL 2>&1
if errorlevel 1 (
  echo [INFO] Installeer PyInstaller...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo [FOUT] Installatie PyInstaller mislukt.
    exit /b 1
  )
)

REM ---- Opruimen vorige build ----
if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist %APP_NAME%.spec del /Q %APP_NAME%.spec

REM ---- Data die mee moet ----
set ADDDATA=
set ADDDATA=!ADDDATA! --add-data "settings.json;."
set ADDDATA=!ADDDATA! --add-data "menu.json;."
set ADDDATA=!ADDDATA! --add-data "extras.json;."
set ADDDATA=!ADDDATA! --add-data "straatnamen.json;."
set ADDDATA=!ADDDATA! --add-data "pizzeria.db;."
set ADDDATA=!ADDDATA! --add-data "klanten.csv;."
set ADDDATA=!ADDDATA! --add-data "postcode.json;."
set ADDDATA=!ADDDATA! --add-data "postcode.csv;."
set ADDDATA=!ADDDATA! --add-data "straatnamen.csv;."
set ADDDATA=!ADDDATA! --add-data "bestellingen.csv.migrated;."
set ADDDATA=!ADDDATA! --add-data "app_errors.log;."
REM modules-map in de exe als submap 'modules'
set ADDDATA=!ADDDATA! --add-data "modules;modules"

REM ---- Optionele icon (alleen als aanwezig) ----
set ICONARG=
if exist "%ICON%" (
  set ICONARG=--icon "%ICON%"
)

REM ---- Build (map-build, geen consolevenster) ----
pyinstaller --noconsole --name "%APP_NAME%" %ICONARG% ^
  %ADDDATA% ^
  --hidden-import win32timezone ^
  "%ENTRY%"

if errorlevel 1 (
  echo [FOUT] Build is mislukt.
  exit /b 1
)

echo.
echo [OK] Build voltooid. Uitvoer staat in: dist\%APP_NAME%\
echo Startbestand: dist\%APP_NAME%\%APP_NAME%.exe
echo.

REM ---- Pauze bij dubbelklik ----
pause
endlocal