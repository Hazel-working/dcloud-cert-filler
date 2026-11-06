@echo off
chcp 65001 >nul
setlocal

rem ===== Change this line if the project folder is moved =====
set "PROJ=D:\wcx\dcloud-cert-filler-main"
rem ==========================================================

set "OUT=%PROJ%\dist\console_payload.js"
set "USR=%PROJ%\dist\dcloud-filler.user.js"

echo ==========================================
echo  Refresh DCloud fill data
echo ==========================================
echo Project : %PROJ%
echo.

if not exist "%PROJ%\dcf\__main__.py" (
  echo [ERROR] Project folder not found.
  echo Edit the line  set "PROJ=..."  near the top of this file.
  echo.
  pause
  exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found. Reinstall and tick "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

pushd "%PROJ%"
if errorlevel 1 (
  echo [ERROR] Cannot enter project folder.
  echo.
  pause
  exit /b 1
)

echo Running: python -m dcf console
echo.
python -m dcf console
set "RC=%ERRORLEVEL%"
popd

if not "%RC%"=="0" (
  echo.
  echo [FAILED] Nothing was generated. Fix the errors above and try again.
  echo.
  pause
  exit /b 1
)

if not exist "%OUT%" (
  echo [ERROR] Expected file missing: %OUT%
  echo.
  pause
  exit /b 1
)

echo.
echo [OK] Updated files:
for %%F in ("%OUT%" "%USR%") do if exist "%%~F" echo   %%~fF  [%%~zF bytes, updated %%~tF]

rem Put the path on the clipboard (no trailing newline) for the file picker
<nul set /p "=%OUT%" | clip >nul 2>&1

echo.
echo File path copied to clipboard.
echo Next: on the DCloud page panel click "Import data" -^> "Choose file",
echo       then press Ctrl+V in the file name box.
echo.
pause
endlocal
