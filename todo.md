# Todo

- Problem: I will have a bunch of assemblers that are using up iron plates, I want to be able to give certain assemblers
priority to resources over others. Making potions before bmd, etc.

- Problem: I have no idea what's happening in the system, need better logs for production / history of transactions. Are my mining drills keeping up with the furnaces? Is iron-plating supply low? 
- current Prod function: shows what will be produced of each item
- I want to know the projected inventory diff across time

- Problem: Current use of exception handling is inconsistent / lacks information

- Problem: When I'm running the simulation in interactive mode, I sometimes make inefficient calls to the commands, like calling `place bmd iron-ore 1` twice in a row instead of doing `place bmd iron-ore 2`. When I export my command history to a script file, these calls should be optimized

- Potion researching (labs) should be happening in the background like other machines,
  - keep track of current progress
  - notif the player when research is ready

- Implement save on quit :(
