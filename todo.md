# Todo


## Rate Limiting

- I have assemblers that are using up iron plates, I want to be able to give certain assemblers priority to resources over others. Making potions before bmd, etc.
- assembling should have sane defaults for rate-limiting, maybe global cap is 10 items per minute unless explicitly overwritten
- crafting a rate limited item should have a warning!!
    - right now craft is successful but nothing happens? where do the items go

## Production statistics

Are my mining drills keeping up with the furnaces? Is iron-plating supply low? 

- I have no idea what's happening in the system, 
- need better logs for production / history of transactions. 

- current Prod function: shows what will be produced of each item
- I want to know the projected inventory diff across time
- failed research should say what material is missing
- What percentage of iron-plates is being used on different recipes?

- show production on all ingredients for a recipe
    - find a way to do this with grep

## Error Handling

- Problem: Current use of exception handling is inconsistent / lacks information
- add useful error messaging for failed crafting! I want to know what items I'm missing


## Exporting / Sharing / Saving

- Problem: When I'm running the simulation in interactive mode, I sometimes make inefficient calls to the commands, like calling `place bmd iron-ore 1` twice in a row instead of doing `place bmd iron-ore 2`. When I export my command history to a script file, these calls should be optimized

## Simulation Feature Requests

- Potion researching (labs) should be happening in the background like other machines,
  - keep track of current progress
  - notif the player when research is ready
- chemistry recipes need to work
- assembling-machine.json -> crafting category (oil-processing, chemistry)
    - mining-drill.json -> resource category (fluids)

- energy consumption

## Shell Commands

- request: limits command, output current rate limited items
- script that visualizes the tech tree
- script that visualizes inventory over time

- bug: if the limit on an item is less than the current inventory count, production will show a negative expected value
    - this allow breaks the production graph (super negative values break the scaling)

- bug: it should not be possible to place a stone furnace that will smelt steel-plates without having steel-processing researched


## Questions

- what would a simple, but eventually succesful factorio bot look like? 
- what does a sophisticated factorio bot look like?
- what does an optimized path look like?


