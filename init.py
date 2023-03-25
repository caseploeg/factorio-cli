from collections import defaultdict

def get_starter_inventory():
    inventory = defaultdict(int)
    inventory['stone-furnace'] = 1
    inventory['burner-mining-drill'] = 1
    inventory['iron-plate'] = 5
    inventory['water'] = 1_000_000_000
    return inventory

def get_starter_recipes():
    current_recipes = set()
    # production
    current_recipes.add('burner-mining-drill')
    current_recipes.add('electric-mining-drill')
    current_recipes.add('stone-furnace')
    current_recipes.add('lab')
    # logistics
    current_recipes.add('burner-inserter')
    current_recipes.add('inserter')
    current_recipes.add('transport-belt')
    current_recipes.add('pipe')
    current_recipes.add('pipe-to-ground')
    current_recipes.add('stone-brick')
    current_recipes.add('wooden-chest')
    current_recipes.add('iron-chest')
    current_recipes.add('small-electric-pole')
    # intermediate products
    current_recipes.add('iron-plate')
    current_recipes.add('copper-plate')
    current_recipes.add('copper-cable')
    current_recipes.add('iron-stick')
    current_recipes.add('iron-gear-wheel')
    current_recipes.add('electronic-circuit')
    current_recipes.add('automation-science-pack')
    return current_recipes

def get_starter_tech():
    current_tech = set()
    return current_tech
