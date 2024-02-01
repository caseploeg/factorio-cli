"""Stateless functions that can exist outside the simulation"""
from collections import defaultdict
from errors import * 
import math

# given a goal technology, return all the technologies required to unlock it,
# as well as all the science packs
def tech_needed(technology, goal):
    seen = set()
    packs = dict()
    preq = set() 
    preq.add(goal)
    while preq:
        t = preq.pop()
        if t not in seen:
            seen.add(t)
            amount = technology[t]['research_unit_count']  
            for ing in technology[t]['research_unit_ingredients']:
                name = ing['name'] 
                if name in packs:
                    packs[name]['amount'] += amount
                else:
                    packs[name] = {'name': name, 'amount': amount}
            for new_t in technology[t]['prerequisites']:
                preq.add(new_t)
    return seen, packs

def get_potion_list(technology, tech):
        packs = defaultdict(int)
        amount = technology[tech]['research_unit_count']  
        for ing in technology[tech]['research_unit_ingredients']:
            name = ing['name'] 
            if name in packs:
                packs[name]['amount'] += amount
            else:
                packs[name] = {'name': name, 'amount': amount}
        return packs

# given a dictionary (shopping list)
# {
#   item_name: {'name': item_name, 'amount': amount_requested},
# }

# return a new dictionary of the same format
# with all ingredients required to craft the items in the original shopping list
# if level == 0 -> only the direct ingredients are calculated

# NOTE: shopping_list respects bulk recipes, but rounds up the amount produced when the recipe does not match the amount requested 
# see grant_excess_production() to see how extra items from bulk orders get placed in player inventory

def shopping_list(recipes, items, level): 
    # for each item, create a list of dicts that map {ingredient: amount needed}, based on that item's recipe
    ing_lists = list(
        map(lambda x: [{'name': k['name'], 'amount': k['amount'] * math.ceil(items[x[0]]['amount'] / recipes[items[x[0]]['name']]['products'][0]['amount'])} for k in x[1]], 
        map(lambda y: [y['name'], y['ingredients']],
        filter(lambda z: z['name'] in items.keys(),
        recipes.values()))))
    # append the items without a recipe
    ing_lists.append(list(filter(lambda x: x['name'] not in recipes, items.values())))  
    flattened_list = defaultdict(int) 
    for ing_list in ing_lists:
        for ing in ing_list:
            name, amount = ing['name'], ing['amount']
            flattened_list[name] += amount

    # Convert defaultdict to tha expected dict format 
    flattened_list = {name: {'name': name, 'amount': amount} for name, amount in flattened_list.items()}    

    return flattened_list 

def does_recipe_exist(self, item):
    if item in self.data.recipes:
        return True
    raise InvalidRecipeError(f'{item} does not have a recipe!')

def convert_to_sh(d):
    sh = dict()
    for k, v in d.items():
        sh[k] = {'name': k, 'amount': v}
    return sh

def is_mineable(resource, item_category, miner_categories):
    if not (item_category in miner_categories):
        return 1, f'{resource} has category: {item_category} not supported by miner with categories: {miner_categories}'

    if resource in {'stone', 'coal', 'iron-ore', 'copper-ore', 'crude-oil'}:
        return 0, None 
    else:
        return 1, f'{resource} cannot be mined'

def is_smeltable(resource):
    if resource in {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}:
        return 0, None
    else:
        return 1, f'{resource} cannont be smelted'