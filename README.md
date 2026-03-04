joytag was made by https://huggingface.co/fancyfeast and this was made by google gemini? i just told it what to do yeah

but! for a brief overview of how this works omg:

AI mode:

* you throw whatever stuff you want to post onto r34 into the input folder, and run "work please.bat"! this will have joytag automatically caption and tag the images.
  you can have specific tags that you want to append to every image and adjust the "depth" of the tagging in that batch file.
* in the blacklist.txt file you can... blacklist tags you dont want to see! sometimes actual artists are recognized in the ai and other hallucinations / weird tags
* in the rules.txt file you can have conditional tagging ! you can see some examples there!



Manual Mode:

* while the AI mode does work! i have added a "do it yourself" function which will queue up all the images and give you an easy editor to well.. edit each of the tags / essentially polish them! its linked with the ChenkinNoob-XL-V0.2\_underscore.csv (renamed to danbooru) from here: https://github.com/BetaDoggo/danbooru-tag-list/releases/tag/Model-Tags so you can actually see the tags, i tried to look for one for r34 but to no avail sadly. i would pay money for that .csv document arghh





if you're interested in downloading! **you need git and python 3.10+ on your machine (make sure python is added to PATH / or environement variables)** 

but besides that! to download! 
1. make a new folder, click on the path (like the empty space beside Desktop > whatever > thing), and type in cmd to open a command prompt in that directory
2. git clone https://github.com/amiiari/automatic-tagger-and-editor
3. download "model.safetensors" from https://huggingface.co/fancyfeast/joytag/tree/main
### **YOU MUST! do this first before going to step 4! ^^^
4. put that model in the models folder inside the "python and models" folder
5. put images in the input folder !!! can be anything just to see it work honestly
6. run "please work.bat" (please work[.bat {i hope it works}])



* then put whatever images in the inputs, run "please work.bat" (please work) and hope that it works! it will generate output folder. if you run "do it yourself" it reads both input and output folders
