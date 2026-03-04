@echo off

echo... waking up .........
timeout /t 1 /nobreak > nul
echo... okay i'll start initializing !
timeout /t 1 /nobreak > nul
echo... okay! everything SHOULD be working, it might take a bit of time, do not worry!


:: um 0.15 is more in depth but maybe hallucinations, 0.4 is very bare, matter of fact i think
set THRESHOLD=0.20

:: add the tags you want in every single image here ! vvv
set EXTRA_TAGS=""

cd "python and models"
call venv\Scripts\activate

python batch_tagger.py ^
    --input "../input" ^
    --output "../output" ^
    --threshold %THRESHOLD% ^
    --append %EXTRA_TAGS% ^
    --blacklist "../blacklist.txt" ^
    --rules "../rules.txt"

timeout /t 1 /nobreak > nul
echo ...okay im done now! i hope it worked byee!
echo ...thank you for using !!


pause