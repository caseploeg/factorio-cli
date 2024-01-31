"""functions that operate on static game data"""

from utils import *

def craft_time(data, name, amount):
    return data.recipes[name]['energy'] / data.recipes[name]['main_product']['amount'] * amount

# each machine type can only interact with specific items
# return errors for combinations that aren't allowed
def is_machine_compatible(data, machine, item):
    if machine in data.mining_drills:
        item_category = data.resources[item]['resource_category']
        machine_categories = data.mining_drills[machine]['resource_categories']
        return is_mineable(item, item_category, machine_categories) 
    elif machine in data.assemblers: 
        item_category = data.recipes[item]['category']
        machine_categories = data.assemblers[machine]['crafting_categories']
        if item_category in machine_categories:
            return 0, 'pog'
        else:
            return 1, f'incompatible combination, item: {item} has crafting category {item_category} but machine {machine} has categories {machine_categories}'
    elif machine in data.furnaces:
        return is_smeltable(item) 