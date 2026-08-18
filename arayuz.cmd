@echo off
REM ---------------------------------------------------------------------------
REM Mesai raporu penceresini acar. Ciftt tiklanabilir.
REM
REM Terminal gerektirmez; klasor secimi ve donem penceredeki alanlardan yapilir.
REM Komut satirini tercih ediyorsan rapor.cmd kullan.
REM ---------------------------------------------------------------------------
setlocal

set "PY="
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\pythonw.exe" set "PY=%CONDA_PREFIX%\pythonw.exe"

if not defined PY call :bul "%LOCALAPPDATA%\miniconda3\envs\mesai"
if not defined PY call :bul "%USERPROFILE%\miniconda3\envs\mesai"
if not defined PY call :bul "%LOCALAPPDATA%\anaconda3\envs\mesai"
if not defined PY call :bul "%USERPROFILE%\anaconda3\envs\mesai"
if not defined PY call :bul "C:\ProgramData\miniconda3\envs\mesai"
if not defined PY call :bul "C:\ProgramData\anaconda3\envs\mesai"

if not defined PY (
    echo.
    echo HATA: 'mesai' conda ortami bulunamadi.
    echo.
    echo Kurulum:
    echo     conda env create -f environment.yml
    echo     conda activate mesai
    echo     pip install -e . --no-deps
    echo.
    pause
    exit /b 9
)

pushd "%~dp0"
REM pythonw: konsol penceresi acilmaz.
start "" "%PY%" -m mesai.gui
popd
exit /b 0

:bul
if exist "%~1\pythonw.exe" set "PY=%~1\pythonw.exe"
goto :eof
