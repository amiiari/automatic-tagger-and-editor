# R34 Auto Tagger

this is a mega link for the installation video!! https://mega.nz/file/K2BDjLLI#2bR9g5D6dkAKE3e9mWxr71VPlW7_nm9siuQGhCymgiQ

yes! this uses both joytag and the r34 tag database (100k+ relevant tags) to tag things really easy!
- there is first the automatic tagger, you can adjust the accuracy, etc.
- a manual tagger
- i tried to include some more quality of life things, like 
	- a tag search/index thing just like the real site! 
	- presets! 
	- blacklist, some basic conditional rules

- and a raw edit text mode which makes it easy to edit datasets for training loras (honestly more for me LMAO)

---

## how to use 

1. make a subfolder with whatever finished images
2. run the r34 tag batch file, will download models, create venv, etc.
3. tags images, strips key descriptors based on a whitelist 
4. run the manual editor to... edit manually...
5. okay but for real LMAO you open it and make a preset especially useful if you are tagging multiple images of the same character, 
	a. you can enable the automatic mode which will scan posts of the character's tag, and then match what tags are most prominent with them while filtering for character descriptors that were in the whitelist.
6. now! thats it! your image is tagged!! very easy.

---

preferably once you run the tagger with the example images, you configure the system with the configure.bat which opens up a gui to edit everything.
you have to add your r34 api key and all that though to be able to refresh the master taglist and use the automatic preset maker!


if you make comics (i've made one so far) it helps a lot to run the tagger for all the individual images, and use another script to merge all the tags into one giant list. 
