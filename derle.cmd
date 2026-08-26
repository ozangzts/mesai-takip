@echo off
REM ---------------------------------------------------------------------------
REM MesaiTakip.exe uretir ve teslim edilecek klasoru toplar.
REM
REM     derle.cmd
REM
REM Sonuc: dist\MesaiTakip\  -- bu klasorun tamami zip'lenip verilir.
REM
REM Iki adim var ve ikincisi atlanirsa program config dosyalarini bulamaz:
REM PyInstaller 6, veri dosyalarini _internal\ altina koyuyor, program ise
REM exe'nin YANINDA ariyor. O yuzden config\ ve KULLANIM.txt buradan kopyalanir.
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

echo.
echo [1/3] Testler...
"%PY%" -m pytest -q
if errorlevel 1 (
    echo.
    echo HATA: testler gecmedi. Derleme yapilmadi.
    popd
    exit /b 1
)

echo.
echo [2/3] PyInstaller...
"%PY%" -m PyInstaller MesaiTakip.spec --noconfirm
if errorlevel 1 (
    echo HATA: derleme basarisiz.
    popd
    exit /b 1
)

echo.
echo [3/3] config\ ve KULLANIM.txt exe'nin yanina kopyalaniyor...
if not exist "dist\MesaiTakip\config" mkdir "dist\MesaiTakip\config"
REM Gercek isim yazimlarini ve giris bilgisini tasiyan iki dosya HARIC.
REM Ornekleri kopyalanir; gercekleri kuran kisi elle koyar.
for %%f in (config\*) do (
    if /I not "%%~nxf"=="personel.yaml" if /I not "%%~nxf"=="gmail.yaml" (
        copy /Y "%%f" "dist\MesaiTakip\config\" >nul
    )
)
copy /Y "KULLANIM.txt" "dist\MesaiTakip\" >nul
if exist "dist\MesaiTakip\_internal\KULLANIM.txt" del "dist\MesaiTakip\_internal\KULLANIM.txt"
if exist "dist\MesaiTakip\_internal\config" rmdir /S /Q "dist\MesaiTakip\_internal\config"

echo.
echo TAMAM. Teslim edilecek klasor:  dist\MesaiTakip\
echo.
echo Kuran kisinin elle koymasi gerekenler:
echo     config\personel.yaml   (ornegi: personel.example.yaml)
echo     config\gmail.yaml      (ornegi: gmail.example.yaml)
echo.
popd
exit /b 0

:bul
if exist "%~1\python.exe" set "PY=%~1\python.exe"
goto :eof
