@echo off
chcp 65001 >nul
setlocal

set "CHROME=C:\Program Files\Google Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo [ERROR] chrome.exe not found. Edit CHROME in this file.
  pause
  exit /b 1
)

rem Profile path resolves against the CURRENT Windows user (Administrator on the build machine).
rem No username is hardcoded anywhere in this project.
set "PROFILE=%LOCALAPPDATA%\DCloudFillerChromeProfile"

echo User    : %USERNAME%
echo Debug   : 127.0.0.1:9222
echo Profile : %PROFILE%
echo.
echo Chrome 136+ refuses remote debugging on the default profile,
echo so this opens a DEDICATED profile. Log in to DCloud once here,
echo keep this window open, then run: python -m dcf run --driver cdp
echo.

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "https://dev.dcloud.net.cn/"

endlocal
