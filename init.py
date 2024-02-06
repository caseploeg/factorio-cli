"""Factory functions for creating initial state for the simulation"""

from collections import defaultdict

def get_starter_inventory():
    inventory = defaultdict(int)
    inventory['stone-furnace'] = 1
    inventory['burner-mining-drill'] = 1
    inventory['iron-plate'] = 5
    inventory['water'] = 1_000_000_000
    return inventory

def get_starter_tech():
    return set() 

def get_starter_recipes(recipes):
    return set(map(lambda item: item[0], filter(lambda item: item[1]['enabled'], recipes.items())))
    