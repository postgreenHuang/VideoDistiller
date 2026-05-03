@echo off
title Video-Distiller Build

py -3.12 -m PyInstaller build.spec --noconfirm

echo.
echo Done! Output: dist\Video-Distiller\r
pause
