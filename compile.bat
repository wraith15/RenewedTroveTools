@ECHO OFF
call .\venv\Scripts\activate.bat
echo Compiling Executable
py build_installer.py
PAUSE