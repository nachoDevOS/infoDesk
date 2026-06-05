@echo off
echo ============================================
echo  infoDesk - Generando ejecutable .exe
echo ============================================
echo.

py -3.13 -m pip install -r requirements.txt

py -3.13 -m PyInstaller ^
  --onefile ^
  --windowed ^
  --icon=icono.ico ^
  --name=infoDesk ^
  --add-data "config.ini;." ^
  --add-data "notification.mp3;." ^
  --add-data "icono.ico;." ^
  --noupx ^
  cliente.py

echo.
echo Copiando config.ini a dist\...
copy /Y config.ini dist\config.ini

echo.
echo ============================================
echo  Listo! Archivos en dist\
echo  Copiar infoDesk.exe y config.ini a cada PC.
echo ============================================
pause
