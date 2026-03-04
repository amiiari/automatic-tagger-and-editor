joytag was made by https://huggingface.co/fancyfeast and this was made by google gemini? i just told it what to do yeah

but! for a brief overview of how this works omg:

AI mode:

* you throw whatever stuff you want to post onto r34 into the input folder, and run "work please.bat"! this will have joytag automatically caption and tag the images.
  you can have specific tags that you want to append to every image and adjust the "depth" of the tagging in that batch file.
* in the blacklist.txt file you can... blacklist tags you dont want to see! sometimes actual artists are recognized in the ai and other hallucinations / weird tags
* in the rules.txt file you can have conditional tagging ! you can see some examples there!



Manual Mode:

* while the AI mode does work! i have added a "do it yourself" function which will queue up all the images and give you an easy editor to well.. edit each of the tags / essentially polish them! its linked with the ChenkinNoob-XL-V0.2\_underscore.csv (renamed to danbooru) from here: https://github.com/BetaDoggo/danbooru-tag-list/releases/tag/Model-Tags so you can actually see the tags, i tried to look for one for r34 but to no avail sadly. i would pay money for that .csv document arghh





how to start:

### **YOU MUST! FIRST download the "model.safetensors" from https://huggingface.co/fancyfeast/joytag/tree/main, put it in the models folder!**



* then put whatever images in the inputs, run "please work.bat" (please work) and hope that it works! it will generate output folder. if you run "do it yourself" it reads both input and output folders
