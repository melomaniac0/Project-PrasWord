@echo off
REM run.bat — Windows launcher for PrasWord
REM Works whether or not the package is installed via pip.
set SCRIPT_DIR=%~dp0
set PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%
python -m prasword %*
