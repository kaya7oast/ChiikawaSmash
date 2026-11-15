@echo off
cd /d "%~dp0.."
python tools\fx_preview.py > tools\preview_log.txt 2>&1
echo done >> tools\preview_log.txt
