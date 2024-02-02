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

# basically craftable()
# given a shopping list(sh) and a copy of current_items(ci)
# if player has enough materials to craft all items in the shopping list,
#   return:
#     0 
#     a Counter containing all intermediate items needed for crafting 
# if missing some items,
#   return:
#     2
#     a meaningless Counter
# todo: if not craftable, 
#   return which raw material the player is missing
#   or something useful like that
def has_items(sim, sh, ci):
    # ci is a copy of current_items
    # we make a copy of current_items to check if we have the items to
    # craft a shopping list because we need to deduct items along the way, but
    # if crafting fails, we should revert to the original state of current_items
    available = Counter()
    missing = Counter()
    # res = 0 -> success
    # res = 1 -> missing items go deeper
    # res = 2 -> out of raw material, can't go deeper
    res = 0 
    not_enough_item = ''
    for item, v in sh.items():
        amount = v
        if ci[item] >= amount:
            available[item] = amount
            ci[item] -= amount
        elif (item not in sim.current_recipes) or (not is_crafting_recipe(sim, item)):
            # this condition is met if the item needed has not been researched
            # or is a raw material, (can not be crafted)
            res = 2
            not_enough_item = item
            break
        else:
            res = 1 
            available[item] = ci[item]
            missing[item] = amount - ci[item]
            ci[item] = 0
    missing_sh = shopping_list(sim.data.recipes, missing)
    if res == 0:
        return res, missing, available, not_enough_item 
    if res == 1:
        res, rest_missing, rest_av, not_enough_item = has_items(sim, missing_sh, ci)
        return res, missing + rest_missing, available + rest_av, not_enough_item
    elif res == 2:
        # todo: currently no meaningful information to pass down if
        # items are not craftable
        return res, missing, available, not_enough_item