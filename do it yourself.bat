

@echo off


cd "python and models"
call venv\Scripts\activate
python manual_tagger.py --input "../input" --output "../output" --dict "./models/danbooru.csv"


exit