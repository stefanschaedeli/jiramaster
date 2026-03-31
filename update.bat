@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0update.ps1"
if %ERRORLEVEL% neq 0 pause
