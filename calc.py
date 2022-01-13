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

class Sim():
    def __init__(self):
        self.clear()
    
    def does_recipe_exist(self, item):
        if item in data.recipes:
            return True
        raise InvalidRecipeError(f'{item} does not have a recipe!')
    
    def is_recipe_unlocked(self, item):
        if item in self.current_recipes:
            return True
        raise ResearchError(f'{item} is not unlocked yet')

    # returns True iff players have more than or equal to `amount` of given `item` in their
    # inventory
    def check_item(self, item, amount):
        if self.current_items[item] >= amount:
            return True
        raise ResourceError('not enough resources in inventory!')

    def check_list(self, sh):
        if functools.reduce(lambda x, y: x and self.current_items[y['name']] >= y['amount'], sh.values(), True):
            return True
        raise ResourceError('not enough resources in inventory!')
        
    def deduct_item(self, item, amount):
        self.check_item(item, amount)
        self.current_items[item] -= amount

    def deduct_list(self, sh):
        for k, v in sh.items():
            self.current_items[k] -= v['amount']

    def place_in_inventory(self, item, amount):
        self.current_items[item] += amount

    def place_machine(self, machine, item):
        self.check_item(machine, 1)
        self.deduct_item(machine, 1)
        if 'mining-drill' in machine:
            # check item to make sure it's as valid resoure for that machine
            try:
                is_mineable(item)
                self.current_miners.append((machine, item))
            except FactorioError as err:
                self.place_in_inventory(machine, 1)
                raise err
        elif 'assembling' in machine:
            try:
                self.is_recipe_unlocked(item) 
                self.current_assemblers.append((machine, item))
            except FactorioError as err:
                self.place_in_inventory(machine, 1)
                raise err
        elif 'furnace' in machine:
            try:
                is_smeltable(item)
                self.current_furnaces.append((machine, item))
            except FactorioError as err:
                self.place_in_inventory(machine, 1)
                raise err
        else:
            self.place_in_inventory(machine, 1)
            raise InvalidMachineError(f'{machine} cannot be placed! try a mining drill or assembler')
        
    def run_cmd(self, cmd):
        self.history.append(cmd)
        pieces = cmd.split()
        # detect any aliases used and replace them with proper names
        pieces = convert_aliases(pieces)
        cmd_name, rest = pieces[0], pieces[1:] 
        if cmd_name == 'spawn':
            item = rest[0]
            amount = int(rest[1])
            self.place_in_inventory(item, amount)
        elif cmd_name == 'research':
            tech = rest[0]
            try:
                research(tech)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'tree':
            print(tech_needed())
        elif cmd_name == 'suggest':
            print(self.all_researchable())
        elif cmd_name == 'cookbook':
            # show current recipes
            print('~~ current recipes unlocked ~~')
            print('\n'.join(self.current_recipes))
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
                res = self.craftable(item, amount)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'place':
            machine = rest[0]
            item = rest[1]
            try:
                self.place_machine(machine, item)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'craft':
            item = rest[0]
            amount = int(rest[1])
            try:
                self.craft(item, amount)
                self.place_in_inventory(item, amount)
                time_spent = data.recipes[item]['energy'] * amount
                self.next(time_spent)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'mine':
            # the same as craft, but with resources
            resource = rest[0]
            amount = int(rest[1])
            try:
                mine(resource, amount)
                self.place_in_inventory(resource, amount)
                time_spent = data.resources[resource]['mineable_properties']['mining_time']
                self.next(time_spent)
            except FactorioError as err:
                print(err)
        elif cmd_name == 'next':
            # calls the next procedure with a given number minutes
            minutes = int(rest[0])
            seconds = minutes * 60
            self.next(seconds)
        elif cmd_name == 'inventory':
            print(json.dumps(self.current_items, indent=4))
        elif cmd_name == 'time':
            # todo format this into H:M:S
            print(self.game_time / 60)
        elif cmd_name == 'import':
            filename = rest[0]
            with open(filename) as f:
                self.clear()
                self.import_history(f.read()) 
        elif cmd_name == 'exit':
            return 1
        else:
            print(f'I do not recognize `{cmd}`')
        return 0

    def craftable(self, item, amount):
        # check if item recipe is unlocked
        self.is_recipe_unlocked(item) 
        # check if resources are available
        sh = shopping_list({
            item: {
                'name': item,
                'amount': amount
            }
        }, 0) 
        return self.check_list(sh)

    # todo: add option for partial crafting, so if a player wants to craft 5 miners
    # but only has materials to make 3, the system will craft 3 miners and give a
    # warning that 2 could not be crafted because of resource constraints
    def craft(self, item, amount):
        if self.craftable(item, amount):
            sh = shopping_list({
                item: {
                    'name': item,
                    'amount': amount
                }
            }, 0)
            self.deduct_list(sh)
            return (item, amount) 

    # research a given technology, raise exception if potions not available
    # or given technology can not be researched yet
    def research(self, tech):
        if self.researchable(tech):
            pl = get_potion_list(tech)
            self.deduct_list(pl)
            self.current_tech.add(tech)
            # unlock recipes
            for effect in data.technology[tech]['effects']:
                if effect['type'] == 'unlock-recipe':
                    current_recipes.add(effect['recipe'])
        else:
            # todo: make it more clear
            raise ResearchError('something went wrong')

    def preqs_researched(self, tech):
        preq = data.technology[tech]['prerequisites']    
        return functools.reduce(lambda x, y: x and y in self.current_tech, preq, True)

    def researchable(self, tech):
        # possible things to go wrong
        # tech DNE
        # tech already researched 
        # not enough resources
        # preqs are not already researched
        if tech in data.technology and tech not in self.current_tech:
            pl = get_potion_list(tech)
            preq = data.technology[tech]['prerequisites']    
            return self.check_list(pl) and self.preqs_researched(tech)
        else:
            # todo: create invalid name exception
            return False

    # find all technologies that are currently researchable
    def all_researchable(self):
        res = set()
        for tech in data.technology:
            if tech not in current_tech and self.preqs_researched(tech):
                res.add(tech)
        return res

    def clear(self):
        # time-related
        self.game_time = 0
        self.history = []
        # possessions
        self.current_tech = get_starter_tech() 
        self.current_recipes = get_starter_recipes() 
        self.current_items = get_starter_inventory() 
        # machines
        self.current_assemblers = [] 
        self.current_miners = [] 
        self.current_furnaces = []

    def import_history(self, cmds):
        cmd_list = cmds.split('\n')
        for cmd in cmd_list:
            self.run_cmd(cmd)
    
    # simulate production for a given number of seconds 
    def next(self, seconds):
        self.game_time += seconds
        # simulate the next given seconds of production
        # mine the resources
        # assemble the products
        # and smelt the ores
        for miner, resource in self.current_miners:
            # pretend all resources have the same `mining-time`,
            # this is only true for the basic resources (iron, copper, coal, stone) 
            self.place_in_inventory(resource, data.mining_drills[miner]['mining_speed'] * seconds)
        for assembler, item in self.current_assemblers:
            try:
                num_produced = data.assemblers[assembler]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
                self.craft(item, num_produced)
                self.place_in_inventory(item, num_produced)
            except FactorioError as err:
                print(f'failed to produce {num_produced} of {item}')
                print(err)
        for furnace, item in self.current_furnaces:
            try:
                num_produced = data.furnaces[furnace]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
                self.craft(item, num_produced)
                self.place_in_inventory(item, num_produced)
            except FactorioError as err:
                print(f'failed to smelt {num_produced} of {item}')
                print(err)


if __name__ == "__main__":
    # establish access to json files
    data_dict = load_files()
    data = SimpleNamespace(**data_dict)

    sim = Sim()
    # todo: revamp with `argparse` from the standard library 

    # todo: need tech cmd to show player what tech they have / which one's
    # they don't have / tech tree

    # todo: need optional filters for inventory cmd 
    # like - just show resources, or just show potions, or just show machines, etc

    # todo: using a cmd with the `amount` param should not break the program
    # instead, either default to 1 or ask the player what the `amount` should be
    
    # todo: need ETA comamnd, figure out how long it will take to produce a certain
    # item when current production stats (machines placed)

    # todo: develop AI strategies to play game

    # todo: make a GUI / visual sim of inventory / resources / machines

    while 'rocket-silo' not in sim.current_items:
        cmd = input('> ')
        res = sim.run_cmd(cmd)
        if res == 1:
            exit()
    print('~~ victory! ~~')