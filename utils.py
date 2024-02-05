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
            packs[name] += amount
        return packs

def shopping_list(recipes, items): 
    filtered_recipes = filter(lambda z: z['name'] in items.keys(), recipes.values())
    name_to_ing = map(lambda recipe: (recipe['name'], recipe['ingredients']), filtered_recipes)
    sh = defaultdict(int) 
    for name, ingredients in name_to_ing:
        for ingredient in ingredients: 
            # amount_needed always rounds up, excess production is always put in player inventory
            # see grant_excess_production()
            amount_needed = ingredient['amount'] * math.ceil(items[name] / recipes[name]['products'][0]['amount'])
            sh[ingredient['name']] += amount_needed
    return sh 

def does_recipe_exist(self, item):
    if item in self.data.recipes:
        return True
    raise InvalidRecipeError(f'{item} does not have a recipe!')

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