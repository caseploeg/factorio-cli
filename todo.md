# Todo

- Problem: I want to automate making bmd's, but don't want more than 10 in my inventory so that resources don't get wasted on them, need a way to rate limit assemblers. 

- Problem: I will have a bunch of assemblers that are using up iron plates, I want to be able to give certain assemblers
priority to resources over others. Making potions before bmd, etc.

- Problem: I have no idea what's happening in the system, need better logs for production / history of transactions. Are my mining drills keeping up with the furnaces? Is iron-plating supply low? 

- Problem: the run_cmd() procedure is getting out of hand, find a way to abstract cmds (parsing args, running them, handling errors, etc.) -- argparse

- Problem: looking at stats for machines is confusing currently 

- Problem: idk what commands are even available or what they do at this point