@echo off
setlocal

echo ... waking up .........
timeout /t 1 /nobreak > nul
echo ... okay i'll start initializing !
timeout /t 1 /nobreak > nul

:: code first! or something idk yeah
cd /d "%~dp0python and models"

:: checking if you have a venv! most likely not if you are running this for the first time!
if not exist "venv\" (
    python -m venv venv
    call venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install torch torchvision pillow tqdm transformers einops huggingface-hub pandas
) else (
    call venv\Scripts\activate
)

echo ... okay! everything SHOULD be working, it might take a bit of time, do not worry!

::
::        edit threshold if you want to change the descriptive-ness?... or whatever it is
::     

:: um 0.20 is more in depth but maybe hallucinations, 0.4 is very bare, matter of fact i think, i have not tested ngl
set THRESHOLD=0.20

::
::        add the tags you want in every single image here ! vvv
::
set EXTRA_TAGS=""

:: running the tagger!
:: make sure there are NO BLANK LINES between the carets below
python batch_tagger.py ^
 --input "../input" ^
 --output "../output" ^
 --threshold %THRESHOLD% ^
 --append %EXTRA_TAGS% ^
 --blacklist "../blacklist.txt" ^
 --rules "../rules.txt"

timeout /t 1 /nobreak > nul
echo ... okay im done now! i hope it worked byee!
echo ... thank you for using !!

pause