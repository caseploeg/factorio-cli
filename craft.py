"""Code related to crafting items"""

from utils import shopping_list

# data dependent, not state dependent
def is_crafting_recipe(sim, item):
    return sim.data.recipes[item]['category'] == 'crafting'

# state dependent
# check if a recipe exists, if the recipe is unlocked, and
# the player has all the required items
def craftable(sim, item, amount):
    """return type: res, missing, available"""
    # check if item recipe is unlocked
    res, msg = sim.is_recipe_unlocked(item)
    if res != 0:
        return 1, None, None, f'{item} recipe is locked' 
    # check if crafting recipe
    if not is_crafting_recipe(sim, item):
        return 1, None, None, f'{item} does not have a crafting recipe'
    sh = shopping_list(sim.data.recipes, {
        item: {
            'name': item,
            'amount': amount
        }
    }, 0) 
    # check if the player has the items available to craft
    return sim.has_items(sh, sim.current_items.copy())
