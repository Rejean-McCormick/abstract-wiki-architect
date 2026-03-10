@echo off
setlocal EnableExtensions
title SemantiK Architect (WSL + uv/.venv)

REM Resolve repo root from BAT location
set "WIN_REPO=%~dp0"
for %%I in ("%WIN_REPO%.") do set "WIN_REPO=%%~fI"

REM If BAT is not exactly at repo root, try one parent up
if not exist "%WIN_REPO%\manage.py" (
  if exist "%WIN_REPO%\..\manage.py" (
    for %%I in ("%WIN_REPO%\..") do set "WIN_REPO=%%~fI"
  )
)

if not exist "%WIN_REPO%\manage.py" (
  echo ERROR: manage.py not found near this BAT.
  echo Place this BAT in the repo root, or edit WIN_REPO manually.
  pause
  exit /b 1
)

where wsl.exe >NUL 2>&1
if errorlevel 1 (
  echo ERROR: wsl.exe not found.
  echo Install/enable WSL first.
  pause
  exit /b 1
)

REM Convert Windows path to WSL path without relying on wslpath output parsing
set "DRIVE=%WIN_REPO:~0,1%"
if /I "%DRIVE%"=="A" set "DRIVE=a"
if /I "%DRIVE%"=="B" set "DRIVE=b"
if /I "%DRIVE%"=="C" set "DRIVE=c"
if /I "%DRIVE%"=="D" set "DRIVE=d"
if /I "%DRIVE%"=="E" set "DRIVE=e"
if /I "%DRIVE%"=="F" set "DRIVE=f"
if /I "%DRIVE%"=="G" set "DRIVE=g"
if /I "%DRIVE%"=="H" set "DRIVE=h"
if /I "%DRIVE%"=="I" set "DRIVE=i"
if /I "%DRIVE%"=="J" set "DRIVE=j"
if /I "%DRIVE%"=="K" set "DRIVE=k"
if /I "%DRIVE%"=="L" set "DRIVE=l"
if /I "%DRIVE%"=="M" set "DRIVE=m"
if /I "%DRIVE%"=="N" set "DRIVE=n"
if /I "%DRIVE%"=="O" set "DRIVE=o"
if /I "%DRIVE%"=="P" set "DRIVE=p"
if /I "%DRIVE%"=="Q" set "DRIVE=q"
if /I "%DRIVE%"=="R" set "DRIVE=r"
if /I "%DRIVE%"=="S" set "DRIVE=s"
if /I "%DRIVE%"=="T" set "DRIVE=t"
if /I "%DRIVE%"=="U" set "DRIVE=u"
if /I "%DRIVE%"=="V" set "DRIVE=v"
if /I "%DRIVE%"=="W" set "DRIVE=w"
if /I "%DRIVE%"=="X" set "DRIVE=x"
if /I "%DRIVE%"=="Y" set "DRIVE=y"
if /I "%DRIVE%"=="Z" set "DRIVE=z"

set "REST=%WIN_REPO:~2%"
set "REST=%REST:\=/%"
set "WSL_REPO=/mnt/%DRIVE%%REST%"

if not defined WSL_REPO (
  echo ERROR: WSL path conversion failed.
  pause
  exit /b 1
)

echo ==================================================
echo SKA WSL SHELL (uv + .venv)
echo Windows repo: %WIN_REPO%
echo WSL repo:     %WSL_REPO%
echo ==================================================
echo.

wsl.exe --cd "%WSL_REPO%" --exec bash -lc "set -e; cd '%WSL_REPO%'; sed -i 's/\r$//' ./scripts/enter_wsl_env.sh; chmod +x ./scripts/enter_wsl_env.sh; exec bash ./scripts/enter_wsl_env.sh"

set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo WSL exited with code %CODE%
  pause
)

endlocal