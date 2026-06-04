@echo off
setlocal enabledelayedexpansion

:: Use the directory where this batch file lives
set "SCRIPT_DIR=%~dp0python and models"

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

echo Opening settings editor...
python customize.py
exit
