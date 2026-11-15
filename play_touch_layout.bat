@echo off
REM Runs the game on your PC with the PHONE layout (your mouse acts as one finger).
cd /d "%~dp0"
set SMASH_TOUCH=1
set SDL_MOUSE_TOUCH_EVENTS=1
python main.py
pause
