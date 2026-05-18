@echo off
REM Windows wrapper so you can run `streaming-catalog.bat ...` from the repo
REM root. Uses .venv\ if present, otherwise the system python (which must
REM have the package installed).
setlocal
set "DIR=%~dp0"
if exist "%DIR%.venv\Scripts\python.exe" (
    "%DIR%.venv\Scripts\python.exe" -m streaming_catalog %*
) else if exist "%DIR%.venv\bin\python3" (
    "%DIR%.venv\bin\python3" -m streaming_catalog %*
) else (
    python -m streaming_catalog %*
)
