@ECHO OFF
taskkill /im RenewedTroveTools.exe /F > nul 2>&1
taskkill /im flet.exe /F > nul 2>&1
if /I "%~x2"==".msi" (
	msiexec /i "%~2" /qb+! TARGETDIR="%~1"
) else (
	start /wait "" "%~2" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="%~1"
)
del /q "%~2"
start "" /d "%~1" RenewedTroveTools.exe