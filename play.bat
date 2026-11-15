@echo off
cd /d "%~dp0"
python -c "import pygame" 2>nul || python -m pip install pygame
python main.py
if errorlevel 1 pause
