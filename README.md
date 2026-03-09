joytag was made by https://huggingface.co/fancyfeast and this was made by google gemini? i just told it what to do yeah

but! for a brief overview of how this works omg:

AI mode:

* you throw whatever stuff you want to post onto r34 into the input folder, and run "work please.bat"! this will have joytag automatically caption and tag the images.
  you can have specific tags that you want to append to every image and adjust the "depth" of the tagging in that batch file.
* in the blacklist.txt file you can... blacklist tags you dont want to see! sometimes actual artists are recognized in the ai and other hallucinations / weird tags
* in the rules.txt file you can have conditional tagging ! you can see some examples there!
* in the presets.txt file, you can have presets which you click on to add specific tags!



Manual Mode:

* while the AI mode does work! i have added a "do it yourself" function which will queue up all the images and give you an easy editor to well.. edit each of the tags / essentially polish them! its linked with a master tag list from r34, well... not all of them but a majority! so you can actually see the tags hahaha





how to start:

### **YOU MUST! FIRST download the "model.safetensors" from https://huggingface.co/fancyfeast/joytag/tree/main, put them in the models folder!**



* then put whatever images in the inputs, run "please work.bat" (please work) and hope that it works! it will generate the output folder. if you run "do it yourself" it reads both input and output folders
