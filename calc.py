import functools
import json
from collections import defaultdict, Counter
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

def convert_to_sh(d):
    sh = dict()
    for k, v in d.items():
        sh[k] = {'name': k, 'amount': v}
    return sh

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
    # avoid side effects >:)
    all_items = items.copy()
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


    # basically craftable()
    # given a shopping list(sh) and a copy of current_items(ci)
    # if player has enough materials to craft all items in the shopping list,
    # return 0 and a Counter containing all intermediate items needed for crafting 
    # return 2 if missing some items, returned Counter is meaningless
    # todo: if not craftable, should return which raw material the player is missing
    # or something useful like that
    def has_items(self, sh, ci):
        # ci is a copy of current_items
        # we have to make a copy of current_items to check if we have the items to
        # craft a shopping list because we need to deduct items along the way, but
        # if crafting fails, we should revert to the original state of current_items
        available = Counter()
        missing = Counter()
        # res = 0 -> success
        # res = 1 -> missing items go deeper
        # res = 2 -> out of raw material, can't go deeper
        res = 0 
        for item, v in sh.items():
            amount = v['amount']
            if ci[item] >= amount:
                available[item] = amount
                ci[item] -= amount
            elif item not in self.current_recipes:
                # this condition is met if the item needed has not been researched
                # or is a raw material, (can not be crafted)
                res = 2
                break
            else:
                res = 1 
                available[item] = ci[item]
                missing[item] = amount - ci[item]
                ci[item] = 0
        msh = convert_to_sh(missing)
        missing_sh = shopping_list(msh, 0)
        if res == 0:
            return res, missing, available 
        if res == 1:
            res, rest_missing, rest_av = self.has_items(missing_sh, ci)
            return res, missing + rest_missing, available + rest_av
        elif res == 2:
            # todo: currently no meaningful information to pass down if
            # items are not craftable
            return res, missing, available 


    # returns True iff players have more than or equal to `amount` of given `item` in their
    # inventory
    def check_item(self, item, amount):
        return self.current_items[item] >= amount 

    def check_list(self, sh):
        return functools.reduce(lambda x, y: x and self.check_item(y['name'], y['amount']), sh.values(), True) 

    def deduct_item(self, item, amount):
        if self.check_item(item, amount):
            self.current_items[item] -= amount
        else:
            raise ResourceError('deduct_item() - resource error')

    def deduct_list(self, sh):
        for k, v in sh.items():
            self.current_items[k] -= v['amount']

    def place_in_inventory(self, item, amount):
        # enfore integral system - avoid very real issues
        self.current_items[item] += int(amount)

    def place_machine(self, machine, item):
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
                self.research(tech)
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
        elif cmd_name == 'machines':
            # show current machines
            print(self.current_miners)
            print(self.current_furnaces)
            print(self.current_assemblers)
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
                res, items = self.craftable(item, amount)
                print(items)
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
            minutes = float(rest[0])
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
        elif cmd_name == 'history':
            print(self.history)
        elif cmd_name == 'exit':
            return 1
        else:
            print(f'I do not recognize `{cmd}`')
        return 0

    def craftable(self, item, amount):
        # check if item recipe is unlocked
        self.is_recipe_unlocked(item) 
        sh = shopping_list({
            item: {
                'name': item,
                'amount': amount
            }
        }, 0) 
        # check if the player has the items available to craft
        return self.has_items(sh, self.current_items.copy())

    # todo: add option for partial crafting, so if a player wants to craft 5 miners
    # but only has materials to make 3, the system will craft 3 miners and give a
    # warning that 2 could not be crafted because of resource constraints

    def craft_time(self, craft_list):
        time = 0
        for name, amount in craft_list.items():
            time += data.recipes[name]['energy'] * amount 
        return time

    # when crafting is done by a furnace or assembler, there should be no items missing from the recipe
    def craft(self, item, amount):
        res, missing, available = self.craftable(item, amount)
        if res == 0:
            missing[item] = amount
            missing_sh = convert_to_sh(missing)
            av_sh = convert_to_sh(available)
            self.deduct_list(av_sh)
            self.place_in_inventory(item, amount)
            time_spent = self.craft_time(missing)
            if time_spent > 0:
                print(item, amount, missing)
                self.next(time_spent)
        elif res == 2:
            raise CraftingError(f'crafting {amount} {item} failed')

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
                    self.current_recipes.add(effect['recipe'])
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
            if tech not in self.current_tech and self.preqs_researched(tech):
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
        # todo: change these from list to
        # dice-{(machine, item): amount}
        self.current_assemblers = [] 
        self.current_miners = [] 
        self.current_furnaces = []

    def import_history(self, cmds):
        cmd_list = cmds.split('\n')
        ignore = False
        ignore_flipped = False
        for cmd in cmd_list:
            if cmd.startswith("'''") and not ignore:
                ignore = True 
                ignore_flipped = True
            # ignore empty lines and ignore commented lines
            if not ignore and cmd != '' and not cmd.startswith('#'):
                self.run_cmd(cmd)
            if cmd.startswith("'''") and ignore and not ignore_flipped:
                ignore = False 
            ignore_flipped = False

    # simulate production for a given number of seconds 
    # todo: fix simulation so assemblers and furnaces produce based on available
    # materials -- do *not* use `craft()`
    def next(self, seconds):
        print('next')
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
            pass
            try:
                num_produced = data.assemblers[assembler]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
                # find the number of items that can *actually* be produced - brute force
                wish = {item: {'name': item, 'amount': num_produced}}
                while not self.check_list(shopping_list(wish, 0)):
                    wish[item]['amount'] -= 1
                self.machine_craft(item, wish[item]['amount'])
            except FactorioError as err:
                print(f'failed to produce {num_produced} of {item}')
                print(err)
        for furnace, item in self.current_furnaces:
            try:
                num_produced = data.furnaces[furnace]['crafting_speed'] * (seconds // data.recipes[item]['energy'])
                # find the number of items that can *actually* be produced - brute force
                wish = {item: {'name': item, 'amount': num_produced}}
                while not self.check_list(shopping_list(wish, 0)):
                    wish[item]['amount'] -= 1
                self.machine_craft(item, wish[item]['amount'])
            except FactorioError as err:
                print(f'failed to smelt {num_produced} of {item}')
                print(err)

    def machine_craft(self, item, num_produced):
        wish = {item: {'name': item, 'amount': num_produced}}
        self.deduct_list(shopping_list(wish,0))
        self.place_in_inventory(item, num_produced)

if __name__ == "__main__":
    # establish access to json files
    data_dict = load_files()
    data = SimpleNamespace(**data_dict)

    sim = Sim()
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