@echo off
cd /d "%~dp0"
REM Set your API key here to avoid hardcoding it:
REM set API_KEY=your_api_key_here
python refresh_tags.py
