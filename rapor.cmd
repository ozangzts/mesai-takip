@echo off
REM ---------------------------------------------------------------------------
REM Raporu conda ortamini aktive etmeden uretir.
REM
REM   rapor.cmd --ay 2026-05
REM   rapor.cmd --ay 2026-06 --girdi "G:\Ortak Drive'lar\IK\Mesai\2026-06"
REM
REM Hangi klasorden cagrildigi onemli degil; script kendi dizinine gecer.
REM Zaten aktif bir conda ortami varsa onu kullanir, yoksa 'mesai' ortamini arar.
REM ---------------------------------------------------------------------------
setlocal

if "%~1"=="" goto :kullanim

set "PY="

REM 1) Zaten aktif bir ortam varsa onu kullan.
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY=%CONDA_PREFIX%\python.exe"

REM 2) Degilse 'mesai' ortamini bilinen conda konumlarinda ara.
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
    exit /b 9
)

pushd "%~dp0"
"%PY%" -m mesai rapor %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:bul
if exist "%~1\python.exe" set "PY=%~1\python.exe"
goto :eof

:kullanim
echo.
echo Kullanim:  rapor.cmd --ay YYYY-MM [--girdi KLASOR] [--cikti DOSYA]
echo.
echo Ornekler:
echo     rapor.cmd --ay 2026-05
echo     rapor.cmd --ay 2026-06 --girdi "G:\Drive\Mesai\2026-06"
echo.
echo Tum secenekler:  rapor.cmd --ay 2026-05 --help
echo.
exit /b 2
