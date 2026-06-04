@echo off
setlocal enabledelayedexpansion

:: Use the directory where this batch file lives
set "SCRIPT_DIR=%~dp0python and models"
set "CONFIG_DIR=%~dp0python and models"

:: --- Auto-setup: venv + dependencies + model ---
if not exist "%SCRIPT_DIR%\venv\" (
    echo Creating venv and installing dependencies...
    python -m venv "%SCRIPT_DIR%\venv"
    call "%SCRIPT_DIR%\venv\Scripts\activate"
    python -m pip install --upgrade pip
    pip install torch torchvision pillow tqdm transformers einops huggingface-hub pandas requests
) else (
    call "%SCRIPT_DIR%\venv\Scripts\activate"
)

:: Check for model
if not exist "%SCRIPT_DIR%\models\model.safetensors" (
    echo Downloading model.safetensors from HuggingFace...
    pip install huggingface-hub -q
    python "%SCRIPT_DIR%\download_model.py"
)

:: --- Main work ---
cd /d "%SCRIPT_DIR%"

echo Initializing Manual Tagger...

:: Loop through every folder in the location of this batch file
for /d %%D in ("%~dp0*") do (
    set "FOLDER_NAME=%%~nxD"
    set "SKIP=0"
    
    :: Check for ~ in the name (marked done)
    echo "!FOLDER_NAME!" | findstr /i "~" >nul
    if not errorlevel 1 set "SKIP=1"
    
    :: Skip python and models
    if "!FOLDER_NAME!" == "python and models" set "SKIP=1"
    
    if "!SKIP!" == "1" (
        echo Skipping: !FOLDER_NAME!
    ) else (
        echo ---------------------------------------
        echo Processing: !FOLDER_NAME!
        
        python manual_tagger.py ^
         --input "%%~fD" ^
         --output "%%~fD" ^
         --dict "./models/master_taglist.csv" ^
         --presets "%CONFIG_DIR%\presets.txt"
    )
)

echo.
echo Manual tagger windows opened above. Close them when done.
exit
