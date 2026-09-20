@echo off
:: Launches h3sed from source using the local virtual environment.
:: Pass a savegame path to open it directly, or drag a savegame onto this file.
setlocal
set HERE=%~dp0
set PYTHONPATH=%HERE%src
start "" "%HERE%.venv\Scripts\pythonw.exe" -m h3sed %*
endlocal
