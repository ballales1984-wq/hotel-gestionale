@echo off
REM Backup database script for Windows
REM This script runs the Python backup script

cd /d "%~dp0.."
python scripts\backup_db.py
pause