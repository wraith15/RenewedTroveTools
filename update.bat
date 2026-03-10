@ECHO OFF
taskkill /im RenewedTroveTools.exe /F > nul 2>&1
taskkill /im flet.exe /F > nul 2>&1
msiexec /i "%~2" /qb+! TARGETDIR="%~1"
del /q "%~2"
start "" /d "%~1" RenewedTroveTools.exe