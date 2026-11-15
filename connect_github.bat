@echo off
REM ============================================================
REM  One-time setup: uploads this folder to github.com/kaya7oast/ChiikawaSmash
REM  1) On github.com make a NEW EMPTY repo called ChiikawaSmash (no README).
REM  2) Double-click this file.
REM  3) On GitHub: Settings -^> Pages -^> Source: "GitHub Actions".
REM  After that, use push_update.bat to upload changes.
REM ============================================================
cd /d "%~dp0"
where git >nul 2>nul || (echo Git is not installed. Get it from https://git-scm.com/download/win then run this again. & pause & exit /b 1)
if exist ".git" (echo This folder is already linked to GitHub. Use push_update.bat to upload changes. & pause & exit /b 0)

git init -b main
git remote add origin https://github.com/kaya7oast/ChiikawaSmash.git
git config user.name >nul 2>nul || git config user.name "kaya7oast"
git config user.email >nul 2>nul || git config user.email "kaya7oast@users.noreply.github.com"
REM if the repo was made with a README, adopt its history but keep this folder as-is
git fetch origin >nul 2>nul && git reset origin/main >nul 2>nul
git add -A
git commit -m "Chiikawa Smash"
git push -u origin main || (echo Upload failed - check the repo exists and you signed in. & pause & exit /b 1)
echo.
echo Done! Now on GitHub: Settings -^> Pages -^> Source: GitHub Actions.
echo The phone version will be at https://kaya7oast.github.io/ChiikawaSmash/ in about 3 minutes.
pause
