@echo off
setlocal enabledelayedexpansion

:: Tag a LoRA dataset laid out as:
::     <dataset>\images\              the original images (one copy)
::     <dataset>\1. GENDER\ ... \12. SYMBOLS\   only the .txt for each image
:: Drag the dataset folder onto this file (or run it and paste the path).
:: One editor window per category, in order; put ~ in a category folder's name to skip it.

set "SCRIPT_DIR=%~dp0python and models"
set "DATASET=%~1"
if "%DATASET%"=="" set /p "DATASET=Dataset folder (the one with images\ in it): "
set "DATASET=%DATASET:"=%"
if not exist "%DATASET%\images\" (
    echo No "images" folder in "%DATASET%".
    pause
    exit /b 1
)
if not exist "%SCRIPT_DIR%\venv\" (
    echo Run "manual dataset edit.bat" once first so it can set up the venv and model.
    pause
    exit /b 1
)

:: New dataset: create the 12 category folders
set "HAS_CATS=0"
for /l %%N in (1,1,30) do if exist "%DATASET%\%%N. *" set "HAS_CATS=1"
if "!HAS_CATS!"=="0" (
    for %%C in ("1. GENDER" "2. LIGHTING" "3. ANGLE AND COMPOSITION" "4. CHARACTER" "5. POSE AND ACTION" "6. EXPRESSIONS" "7. CLOTHES" "8. PROPORTIONS" "9. LOWER ANATOMY" "10. LIQUIDS" "11. BACKGROUND" "12. SYMBOLS") do mkdir "%DATASET%\%%~C"
)

call "%SCRIPT_DIR%\venv\Scripts\activate"
cd /d "%SCRIPT_DIR%"

for /l %%N in (1,1,30) do (
    for /d %%D in ("%DATASET%\%%N. *") do (
        set "NAME=%%~nxD"
        echo "!NAME!" | findstr /c:"~" >nul
        if errorlevel 1 (
            echo ---------------------------------------
            echo Tagging: !NAME!
            python manual_tagger.py ^
             --input "%DATASET%\images" ^
             --output "%%~fD" ^
             --dict "./models/master_taglist.csv" ^
             --presets "%SCRIPT_DIR%\presets.txt" ^
             --lora-mode
        ) else (
            echo Skipping ^(marked done^): !NAME!
        )
    )
)

echo.
echo All categories done. Compile with _tools\compiler.py (or the trainer's Compare tab) before training.
pause
