import functools
import json
from collections import defaultdict
from types import SimpleNamespace

from errors import * 
from constants import *
from files import load_files
from init import *
from cli import *

# given a goal technology, return all the technologies required to unlock it,
# as well as all the science packs
def tech_needed():
    seen = set()
    goal = 'rocket-silo'
    packs = dict()
    preq = set() 
    preq.add(goal)
    while preq:
        t = preq.pop()
        if t not in seen:
            seen.add(t)
            amount = data.technology[t]['research_unit_count']  
            for ing in data.technology[t]['research_unit_ingredients']:
                name = ing['name'] 
                if name in packs:
                    packs[name]['amount'] += amount
                else:
                    packs[name] = {'name': name, 'amount': amount}
            for new_t in data.technology[t]['prerequisites']:
                preq.add(new_t)
    return seen, packs

# give a dictionary
# {
#   item_name: {'name': item_name, 'amount': amount_wanted},
# }
# return a new dictionary of the same format,
# will all items required to build the items in the
# shopping list
# if level == 0 -> only the direct ingredients are calculated
# if level == 1 -> all resources required are calculated (raw materials, sub-components...)
# if level == 2 -> only raw materials are calculated (iron ore, coal, etc)
def shopping_list(items, level): 
    all_items = items
    def helper(items):
        ing_lists = list(
            map(lambda x: [{'name': k['name'], 'amount': k['amount'] * items[x[0]]['amount']} for k in x[1]], 
            map(lambda y: [y['name'], y['ingredients']],
            filter(lambda z: z['name'] in items.keys(),
            data.recipes.values()))))
        ing_lists.append(list(filter(lambda x: x['name'] not in data.recipes, items.values())))  
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
                    if name in data.recipes:
                        done = False
                # update count for all items required, based on latest information
                all_items[name] = master_list[name]
        if level > 0 and not done:
            res = helper(master_list)
            return res 
        elif level == 1 and done:
            return all_items # return a complete shopping list with all sub-components
        elif level == 2 and done:
            return master_list # return raw resources (max depth, no sub-components)
        else:
            return master_list # return shopping list of depth 1 
    return helper(items)

# returns True iff players have more than or equal to `amount` of given `item` in their
# inventory
def check_item(item, amount):
    if current_items[item] >= amount:
        return True
    raise ResourceError('not enough resources in inventory!')

def check_list(sh):
    if functools.reduce(lambda x, y: x and current_items[y['name']] >= y['amount'], sh.values(), True):
        return True
    raise ResourceError('not enough resources in inventory!')
    
def place_machine(machine, item):
    check_item(machine, 1)
    deduct_item(machine, 1)
    if 'mining-drill' in machine:
        # check item to make sure it's as valid resoure for that machine
        try:
            is_mineable(item)
            current_miners.append((machine, item))
        except FactorioError as err:
            place_in_inventory(machine, 1)
            raise err
    elif 'assembling' in machine:
        try:
            is_recipe_unlocked(item) 
            current_assemblers.append((machine, item))
        except FactorioError as err:
            place_in_inventory(machine, 1)
            raise err
    elif 'furnace' in machine:
        try:
            is_smeltable(item)
            current_furnaces.append((machine, item))
        except FactorioError as err:
            place_in_inventory(machine, 1)
            raise err
    else:
        place_in_inventory(machine, 1)
        raise InvalidMachineError(f'{machine} cannot be placed! try a mining drill or assembler')

def place_in_inventory(item, amount):
    current_items[item] += amount

def deduct_list(sh):
    for k, v in sh.items():
        current_items[k] -= v['amount']

def deduct_item(item, amount):
    check_item(item, amount)
    current_items[item] -= amount

# todo: add option for partial crafting, so if a player wants to craft 5 miners
# but only has materials to make 3, the system will craft 3 miners and give a
# warning that 2 could not be crafted because of resource constraints
def craft(item, amount):
    if craftable(item, amount):
        sh = shopping_list({
            item: {
                'name': item,
                'amount': amount
            }
        }, 0)
        deduct_list(sh)
        return (item, amount) 

def get_potion_list(tech):
    packs = defaultdict(int)
    amount = data.technology[tech]['research_unit_count']  
    for ing in data.technology[tech]['research_unit_ingredients']:
        name = ing['name'] 
        if name in packs:
            packs[name]['amount'] += amount
        else:
            packs[name] = {'name': name, 'amount': amount}
    return packs

def preqs_researched(tech):
    preq = data.technology[tech]['prerequisites']    
    return functools.reduce(lambda x, y: x and y in current_tech, preq, True)

def researchable(tech):
    # possible things to go wrong
    # tech DNE
    # tech already researched 
    # not enough resources
    # preqs are not already researched
    if tech in data.technology and tech not in current_tech:
        pl = get_potion_list(tech)
        preq = data.technology[tech]['prerequisites']    
        return check_list(pl) and preqs_researched(tech)
    else:
        # todo: create invalid name exception
        return False

# find all technologies that are currently researchable
def all_researchable():
    res = set()
    for tech in data.technology:
        preq = data.technology[tech]['prerequisites']    
        if tech not in current_tech and preqs_researched(tech):
            res.add(tech)
    return res

# research a given technology, raise exception if potions not available
# or given technology can not be researched yet
def research(tech):
    if researchable(tech):
        pl = get_potion_list(tech)
        deduct_list(pl)
        current_tech.add(tech)
        # unlock recipes
        for effect in data.technology[tech]['effects']:
            if effect['type'] == 'unlock-recipe':
                current_recipes.add(effect['recipe'])
    else:
        # todo: make it more clear
        raise ResearchError('something went wrong')

def mine(resource, amount):
    if is_mineable(resource):
        return (resource, amount)

def is_mineable(resource):
    if resource in {'stone', 'coal', 'iron-ore', 'copper-ore'}:
        return True
    else:
        raise ResourceError(f'{resource} can not be mined')

def is_smeltable(resource):
    if resource in {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}:
        return True
    else:
        raise ResourceError(f'{resource} can not be smelt')

def is_recipe_unlocked(item):
    if item in current_recipes:
        return True
    raise ResearchError(f'{item} is not unlocked yet')

def craftable(item, amount):
    # check if item recipe is unlocked
    is_recipe_unlocked(item) 
    # check if resources are available
    sh = shopping_list({
        item: {
            'name': item,
            'amount': amount
        }
    }, 0) 
    return check_list(sh)


# returns the new game time after simulation production for a given number of seconds
def next(seconds, game_time):
    game_time += seconds
    # simulate the next given seconds of production
    # mine the resources
    # assemble the products
    # and smelt the ores
    for miner, resource in current_miners:
        # pretend all resources have the same `mining-time`,
        # this is only true for the basic resources (iron, copper, coal, stone) 
        place_in_inventory(resource, data.mining_drills[miner]['mining_speed'] * seconds)
    for assembler, item in current_assemblers:
        try:
            num_produced = data.assemblers[assembler]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
            craft(item, num_produced)
            place_in_inventory(item, num_produced)
        except FactorioError as err:
            print(f'failed to produce {num_produced} of {item}')
            print(err)
    for furnace, item in current_furnaces:
        try:
            num_produced = data.furnaces[furnace]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
            craft(item, num_produced)
            place_in_inventory(item, num_produced)
        except FactorioError as err:
            print(f'failed to smelt {num_produced} of {item}')
            print(err)
    return game_time
            

if __name__ == "__main__":
    # establish access to json files
    data_dict = load_files()
    data = SimpleNamespace(**data_dict)
    # init sim
    current_tech = get_starter_tech() 
    current_recipes = get_starter_recipes() 
    current_items = get_starter_inventory() 
    # todo: maybe change these from list to;
    # dict-{(machine, resource) : # of machines}
    # machines
    current_assemblers = [] 
    current_miners = [] 
    current_furnaces = []

    history = []
    game_time = 0
    # todo: revamp with `argparse` from the standard library 

    # todo: need tech cmd to show player what tech they have / which one's
    # they don't have / tech tree

    # todo: need optional filters for inventory cmd 
    # like - just show resources, or just show potions, or just show machines, etc

    # todo: using a cmd with the `amount` param should not break the program
    # instead, either default to 1 or ask the player what the `amount` should be
    
    # todo: restarting the program many times can be frustating, because I will
    # need to start over completely each time
    # figure out a way to import / export save-states in the simulation
    while 'rocket-silo' not in current_items:
        cmd = input('> ')
        history.append(cmd)
        pieces = cmd.split()
        # detect any aliases used and replace them with proper names
        pieces = convert_aliases(pieces)
        cmd_name, rest = pieces[0], pieces[1:] 
        if cmd_name == 'spawn':
            item = rest[0]
            amount = int(rest[1])
            place_in_inventory(item, amount)
        elif cmd_name == 'research':
            tech = rest[0]
            try:
                research(tech)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'tree':
            print(tech_needed())
        elif cmd_name == 'suggest':
            print(all_researchable())
        elif cmd_name == 'cookbook':
            # show current recipes
            print('~~ current recipes unlocked ~~')
            print('\n'.join(current_recipes))
        elif cmd_name == 'wish':
            item = rest[0]
            if len(rest) > 1:
                amount = int(rest[1])
            else:
                amount = 1
            found = False
            if item in data.recipes:
                found = True
                print(json.dumps(shopping_list(
                    {
                        item: {
                            'name': item,
                            'amount': amount
                        }
                }, 0), indent=4))
            if item in data.technology:
                found = True
                print(json.dumps(get_potion_list(item), indent=4))
            if not found:
                print(f'could not find {item}')
        elif cmd_name == 'craftable':
            item = rest[0]
            amount = int(rest[1])
            try:
                res = craftable(item, amount)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'place':
            machine = rest[0]
            item = rest[1]
            try:
                place_machine(machine, item)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'craft':
            item = rest[0]
            amount = int(rest[1])
            try:
                craft(item, amount)
                place_in_inventory(item, amount)
                time_spent = data.recipes[item]['energy'] * amount
                game_time = next(time_spent, game_time)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'mine':
            # the same as craft, but with resources
            resource = rest[0]
            amount = int(rest[1])
            try:
                mine(resource, amount)
                place_in_inventory(resource, amount)
                time_spent = data.resources[resource]['mineable_properties']['mining_time']
                game_time = next(time_spent, game_time)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'next':
            # calls the next procedure with a given number minutes
            minutes = int(rest[0])
            seconds = minutes * 60
            game_time = next(seconds, game_time)
        elif cmd_name == 'inventory':
            print(json.dumps(current_items, indent=4))
        elif cmd_name == 'time':
            # todo format this 
            print(game_time / 60)
        elif cmd_name == 'exit':
            break
        else:
            print(f'I do not recognize `{cmd}`')