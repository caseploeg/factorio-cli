# factorio-cli
automation, rockets, and wizardry

turn based factorio for the command line. build a rocket u win. 

## project goals:
- simulate factory automation 
- build a powerful CLI to run the factory 
- write cool software on top of the simulation, 
    - bots
    - visualization
    - multiplayer 

## implementation
- CLI built with [cmd2](https://github.com/python-cmd2/cmd2), an extension of [cmd](https://docs.python.org/3/library/cmd.html) from the python standard library 
- data extraction done using [Data Exporter to JSON](https://mods.factorio.com/mod/recipelister) mod by Erythion.
- simulation runs on a Flask server

## simulation features
- inventory system
- mine resources
- craft items
- research technology
- place machines that automate crafting and mining
- track automated production statistics
- limit production of specific items

## cool software ./robots 
- graph.py outputs production statistics overtime
- fbot.py randomly crafts and places items

## local setup (WIP)
https://www.b-list.org/weblog/2022/may/13/boring-python-dependencies/
```
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt 
$ flask --app server run
$ python3 ./main.py
```
