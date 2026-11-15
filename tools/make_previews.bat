@echo off
cd /d "%~dp0.."
python -c "import pygame" 2>nul || python -m pip install pygame
python tools\contact_sheet.py > tools\preview_log.txt 2>&1
echo done >> tools\preview_log.txt
