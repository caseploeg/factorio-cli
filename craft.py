"""Code related to crafting items"""

from collections import defaultdict, Counter
from utils import * 

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
        item: amount
    }) 
    # check if the player has the items available to craft
    return has_items(sim, sh, sim.current_items.copy())

# given a shopping list(sh) and a copy of current_items(ci)
# return:
# res = 0 -> success
# res = 1 -> missing items go deeper (recursion)
# res = 2 -> out of raw material, can't go deeper
# available: a Counter of all items that need to be deducted from inventory
# missing:   a Counter of all items that need to be crafted
def has_items(sim, sh, ci):
    res, missing, available = sim.check_list(sh, ci)
    # player has all the ingredients in the shopping list in their inventory!
    if res == 0:
        return res, missing, available, ''

    # otherwise, we need to recursively craft the intermediate ingredients
    # check that missing items have unlocked crafting recipes 
    for item, v in missing.items():
        if (item not in sim.current_recipes) or (not is_crafting_recipe(sim, item)):
            return 2, None, None, f'can not craft {item}'

    # deduct the items that were available from the current copy of inventory
    for item, v in available.items():
        ci[item] -= v

    missing_sh = shopping_list(sim.data.recipes, missing)
    res, rest_missing, rest_av, msg = has_items(sim, missing_sh, ci)
    return res, missing + rest_missing, available + rest_av, msg 
    