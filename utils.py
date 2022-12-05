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

# give a dictionary
# {
#   item_name: {'name': item_name, 'amount': amount_wanted},
# }
# return a new dictionary of the same format,
# with all items required to build the items in the shopping list
# if level == 0 -> only the direct ingredients are calculated
# if level == 1 -> all resources required are calculated (raw materials, sub-components...)
# if level == 2 -> only raw materials are calculated (iron ore, coal, etc)
# NOTE: shopping_list respects bulk recipes, but rounds up when the production ratio does not match the amount needed
# ex: wish iron-stick 2 -> need 1 iron-plate , but wish iron-stick 1 -> need 1 iron-plate as well - no fractions
# see grant_excess_production() to see how extra items from bulk orders get placed in player inventory

def shopping_list(recipes, items, level): 
    # avoid side effects >:)
    all_items = items.copy()
    def helper(items):
        ing_lists = list(
            map(lambda x: [{'name': k['name'], 'amount': k['amount'] * math.ceil(items[x[0]]['amount'] / recipes[items[x[0]]['name']]['main_product']['amount'])} for k in x[1]], 
            map(lambda y: [y['name'], y['ingredients']],
            filter(lambda z: z['name'] in items.keys(),
            recipes.values()))))
        ing_lists.append(list(filter(lambda x: x['name'] not in recipes, items.values())))  
        # flatten
        master_list = dict() 
        done = True
        for ing_list in ing_lists:
            for ing in ing_list:
                name, amount = ing['name'], ing['amount']
                if name in master_list:
                    master_list[name]['amount'] += amount
                else:
                    master_list[name] = ing 
                    if name in recipes:
                        done = False
                # update count for all items required, based on latest information
                all_items[name] = master_list[name]
        if level > 0 and not done:
            res = helper(master_list)
            return res 
        # return a complete shopping list with all sub-components
        elif level == 1 and done:
            return all_items 
        # return raw resources (max depth, no sub-components)
        elif level == 2 and done:
            return master_list 
        # return shopping list of depth 1 
        else:
            return master_list 
    return helper(items)

def does_recipe_exist(self, item):
    if item in self.data.recipes:
        return True
    raise InvalidRecipeError(f'{item} does not have a recipe!')

def convert_to_sh(d):
    sh = dict()
    for k, v in d.items():
        sh[k] = {'name': k, 'amount': v}
    return sh

def is_mineable(resource):
    if resource in {'stone', 'coal', 'iron-ore', 'copper-ore'}:
        return 0, None 
    else:
        return 1, f'{resource} cannot be mined'

def is_smeltable(resource):
    if resource in {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}:
        return 0, None
    else:
        return 1, f'{resource} cannont be smelted'