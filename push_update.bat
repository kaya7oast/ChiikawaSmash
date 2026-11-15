@echo off
REM Uploads every change in this folder to GitHub. The phone version rebuilds in ~3 minutes.
cd /d "%~dp0"
if not exist ".git" (echo Run connect_github.bat first. & pause & exit /b 1)
git add -A
git commit -m "Update from my PC" || echo Nothing new to upload.
git push
echo.
echo Uploaded. Check the Actions tab on GitHub, then refresh the game in ~3 minutes.
pause
