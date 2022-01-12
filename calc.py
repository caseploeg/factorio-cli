import json
import functools
from collections import defaultdict
from contextlib import ExitStack

class FactorioError(Exception):
    pass

class ResearchError(FactorioError):
    pass
class ResourceError(FactorioError):
    pass
class InvalidMachineError(FactorioError):
    pass

FIVE_MINUTES = 60 * 5

recipes = None
technology = None
mining_drills = None
filenames = [
    'recipe.json',
    'technology.json',
    'mining-drill.json',
    'resource.json',
    'furnace.json',
    'assembling-machine.json',
]
with ExitStack() as stack: 
    files = [
        stack.enter_context(open(filename))
        for filename in filenames
    ]
    recipes = json.load(files[0])
    technology = json.load(files[1])
    mining_drills = json.load(files[2])
    resources = json.load(files[3])
    furnaces = json.load(files[4])
    assembling_machines = json.load(files[5])

def get_recipe(name):
    return recipes[name]
    
def make_burner_mining_drill():
    return {
        "name" : "burner-mining-drill",
        "energy_usage" : 150000,
        "energy_source": "chemical",
        "mining_speed" : 0.25,
    }

def make_electric_mining_drill():
    return {
        "name" : "electric-mining-drill",
        "energy_usage" : 90000,
        "energy_source": "electric",
        "mining_speed" : 0.5,
    }

def miner_production(miners):
    energy_used = functools.reduce(lambda x, y: x + y['energy_usage'], miners, 0) 
    ores = functools.reduce(lambda x, y: x + y['mining_speed'], miners, 0) 
    return ores, energy_used

def tech_needed(unlocked):
    goal = 'rocket-silo'
    unlocked.add(goal)
    packs = dict()
    preq = technology[goal]['prerequisites']
    while preq:
        t = preq.pop()
        if t not in unlocked:
            unlocked.add(t)
            amount = technology[t]['research_unit_count']  
            for ing in technology[t]['research_unit_ingredients']:
                name = ing['name'] 
                if name in packs:
                    packs[name]['amount'] += amount
                else:
                    packs[name] = {'name': name, 'amount': amount}

            for new_t in technology[t]['prerequisites']:
                preq.append(new_t)
    return unlocked, packs

    

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
        place_in_inventory(resource, mining_drills[miner]['mining_speed'] * seconds)
    for assembler, item in current_assemblers:
        try:
            num_produced = assemblers[assembler]['crafting_speed'] * (seconds // recipes[item]['energy'])
            craft(item, num_produced)
            place_in_inventory(item, num_produced)
        except FactorioError as err:
            print(f'failed to produce {num_produced} of {item}')
            print(err)
    for furnace, item in current_furnaces:
        try:
            num_produced = furnaces[furnace]['crafting_speed'] * (seconds // recipes[item]['energy'])
            craft(item, num_produced)
            place_in_inventory(item, num_produced)
        except FactorioError as err:
            print(f'failed to smelt {num_produced} of {item}')
            print(err)

    return game_time
        # do the same thing as assemblers
            

# todo fill this in
def get_starter_inventory():
    inventory = defaultdict(int)
    inventory['stone-furnace'] = 1
    inventory['burner-mining-drill'] = 1
    inventory['wood'] = 1
    inventory['iron-plate'] = 5
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


if __name__ == "__main__":
    # ignore energy for now
    TEST = False 
    current_tech = get_starter_tech() 
    current_recipes = get_starter_recipes() 
    current_items = get_starter_inventory() 
    # todo: maybe change these from list to;
    # dict-{(machine, resource) : # of machines}
    current_assemblers = [] 
    current_miners = [] 
    current_furnaces = []

    history = []
    game_time = 0
    if TEST == False:
        # todo: using a cmd with the `amount` param should not break the program
        # instead, either default to 1 or ask the player what the `amount` should be
        
        # todo: restarting the program many times can be frustating, because I will
        # need to start over completely each time
        # figure out a way to import / export save-states in the simulation
        while 'rocket-silo' not in current_items:
            cmd = input('> ')
            history.append(cmd)
            pieces = cmd.split()
            cmd_name, rest = pieces[0], pieces[1:] 
            if cmd_name == 'spawn':
                item = rest[0]
                amount = int(rest[1])
                place_in_inventory(item, amount)
            elif cmd_name == 'wish':
                item = rest[0]
                if len(rest) > 1:
                    amount = int(rest[1])
                else:
                    amount = 1
                print(json.dumps(shopping_list(
                    {
                        item: {
                            'name': item,
                            'amount': amount
                        }
                    }, 0), indent=4))
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
                    time_spent = recipes[item]['energy'] * amount
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
                    time_spent = resources[resource]['mineable_properties']['mining_time']
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
    else:
        # tech needed to unlocked rocket-silo starting with no technologies already unlocked
        tech, packs = tech_needed(current_tech)
        # items required to win the game
        win_condition = dict()
        for k, v in packs.items():
            win_condition[k] = v
        
        win_condition['rocket-silo'] = {
                'name': 'rocket-silo',
                'amount': 1
            }
        win_condition['rocket-part'] = {
                'name': 'rocket-part',
                'amount': 100
        }

        # calculate the amount of each item needed to craft items for win condition 
        sh = shopping_list(win_condition, 0)
        print(json.dumps(sh, indent=4, sort_keys=True))
        
        # calculate production statistics for miners
        miners = [
            make_electric_mining_drill() for _ in range(10)
        ]
        print(miner_production(miners))

        # calculate production statistics for crafting a given recipe 