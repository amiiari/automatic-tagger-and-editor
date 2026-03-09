

@echo off


cd /d "%~dp0python and models"
call venv\Scripts\activate

python manual_tagger.py ^
 --input "../input" ^
 --output "../output" ^
 --dict "./models/master_taglist.csv" ^
 --presets "../presets.txt"

exit