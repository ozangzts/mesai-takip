@echo off
REM ---------------------------------------------------------------------------
REM Teslim edilecek zip'i uretir ve icine girmemesi gerekeni reddeder.
REM
REM     paketle.cmd
REM
REM Once derle.cmd calistirilmis olmali. Sonuc Masaustune yazilir.
REM
REM Neden ayri bir adim: derle.cmd'nin urettigi dist\MesaiTakip klasoru ayni
REM zamanda kurulup TEST EDILEN klasor. Yani icine gercek personel.yaml,
REM gercek gmail.yaml, personel listesi Excel'i ve uretilmis raporlar giriyor.
REM O klasoru dogrudan ziplemek, canli bir uygulama sifresini ve 181 kisinin
REM adini birine vermek demek. Zip bir kopyadan uretiliyor ve yazilmadan once
REM icerigi kontrol ediliyor.
REM ---------------------------------------------------------------------------
setlocal

set "PY="
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY=%CONDA_PREFIX%\python.exe"
if not defined PY call :bul "%LOCALAPPDATA%\miniconda3\envs\mesai"
if not defined PY call :bul "%USERPROFILE%\miniconda3\envs\mesai"
if not defined PY call :bul "%LOCALAPPDATA%\anaconda3\envs\mesai"
if not defined PY call :bul "%USERPROFILE%\anaconda3\envs\mesai"
if not defined PY call :bul "C:\ProgramData\miniconda3\envs\mesai"
if not defined PY call :bul "C:\ProgramData\anaconda3\envs\mesai"

if not defined PY (
    echo HATA: 'mesai' conda ortami bulunamadi.
    exit /b 9
)

pushd "%~dp0"
"%PY%" paketle.py
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:bul
if exist "%~1\python.exe" set "PY=%~1\python.exe"
goto :eof
