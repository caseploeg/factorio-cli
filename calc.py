import functools
import json
from collections import defaultdict, Counter
from types import SimpleNamespace

from errors import * 
from constants import *
from files import load_files
from init import *
from cli import *

def convert_to_sh(d):
    sh = dict()
    for k, v in d.items():
        sh[k] = {'name': k, 'amount': v}
    return sh

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
    def __init__(self, data_dict):
        self.clear()
        data = SimpleNamespace(**data_dict)
        self.data = data

    def get_potion_list(self, tech):
        packs = defaultdict(int)
        amount = self.data.technology[tech]['research_unit_count']  
        for ing in self.data.technology[tech]['research_unit_ingredients']:
            name = ing['name'] 
            if name in packs:
                packs[name]['amount'] += amount
            else:
                packs[name] = {'name': name, 'amount': amount}
        return packs

    # given a goal technology, return all the technologies required to unlock it,
    # as well as all the science packs
    def tech_needed(self, goal):
        seen = set()
        packs = dict()
        preq = set() 
        preq.add(goal)
        while preq:
            t = preq.pop()
            if t not in seen:
                seen.add(t)
                amount = self.data.technology[t]['research_unit_count']  
                for ing in self.data.technology[t]['research_unit_ingredients']:
                    name = ing['name'] 
                    if name in packs:
                        packs[name]['amount'] += amount
                    else:
                        packs[name] = {'name': name, 'amount': amount}
                for new_t in self.data.technology[t]['prerequisites']:
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
    def shopping_list(self, items, level): 
        # avoid side effects >:)
        all_items = items.copy()
        def helper(items):
            ing_lists = list(
                map(lambda x: [{'name': k['name'], 'amount': k['amount'] * items[x[0]]['amount']} for k in x[1]], 
                map(lambda y: [y['name'], y['ingredients']],
                filter(lambda z: z['name'] in items.keys(),
                self.data.recipes.values()))))
            ing_lists.append(list(filter(lambda x: x['name'] not in self.data.recipes, items.values())))  
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
                        if name in self.data.recipes:
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

    def does_recipe_exist(self, item):
        if item in self.data.recipes:
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
        missing_sh = self.shopping_list(msh, 0)
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
        return 0, 'success'

    def craftable(self, item, amount):
        # check if item recipe is unlocked
        self.is_recipe_unlocked(item) 
        sh = self.shopping_list({
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
            time += self.data.recipes[name]['energy'] * amount 
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
            return 0, None
        elif res == 2:
            return 1, f'crafting {amount} {item} failed'

    def mine(self, resource, amount):
        if is_mineable(resource):
            self.place_in_inventory(resource, amount)
            time_spent = self.data.resources[resource]['mineable_properties']['mining_time'] * amount
            self.next(time_spent)
            return 0, None
        else:
            return 1, f'failed to mine {amount} {resource}'

    # research a given technology, raise exception if potions not available
    # or given technology can not be researched yet
    def research(self, tech):
        res, msg = self.researchable(tech)
        if res == 0:
            pl = self.get_potion_list(tech)
            self.deduct_list(pl)
            self.current_tech.add(tech)
            # unlock recipes
            for effect in self.data.technology[tech]['effects']:
                if effect['type'] == 'unlock-recipe':
                    self.current_recipes.add(effect['recipe'])
            return 0, None
        else:
            return res, msg

    def preqs_researched(self, tech):
        preq = self.data.technology[tech]['prerequisites']    
        return functools.reduce(lambda x, y: x and y in self.current_tech, preq, True)

    def researchable(self, tech):
        """Decide whether a given technology can be researched or not"""
        if tech not in self.data.technology:
            return 1, f'researchable - {tech} could not be found in the list of tecnologies'
        if tech in self.current_tech:
            return 1, f'researchable - {tech} has already been researched'
        pl = self.get_potion_list(tech)
        preq = self.data.technology[tech]['prerequisites']    
        if not self.preqs_researched(tech):
            return 1, f'researchable - one or more prerequisite technologies for {tech} have not been researched'
        if not self.check_list(pl): 
            return 1, f'researchable - missing the potions required to research {tech}'
        return 0, None

    # find all technologies that could be researched next 
    def all_researchable(self):
        res = set()
        for tech in self.data.technology:
            if tech not in self.current_tech and self.preqs_researched(tech):
                res.add(tech)
        return res

    def clear(self):
        # time-related
        self.game_time = 0
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

    # simulate production for a given number of seconds 
    # todo: fix simulation so assemblers and furnaces produce based on available
    # materials -- do *not* use `craft()`
    def next(self, seconds):
        self.game_time += seconds
        # simulate the next given seconds of production
        # mine the resources
        # assemble the products
        # and smelt the ores
        for miner, resource in self.current_miners:
            # pretend all resources have the same `mining-time`,
            # this is only true for the basic resources (iron, copper, coal, stone) 
            self.place_in_inventory(resource, self.data.mining_drills[miner]['mining_speed'] * seconds)
        for assembler, item in self.current_assemblers:
            pass
            try:
                num_produced = self.data.assemblers[assembler]['crafting_speed'] * (seconds // self.data.recipes[item]['energy'])
                # find the number of items that can *actually* be produced - brute force
                wish = {item: {'name': item, 'amount': num_produced}}
                while not self.check_list(self.shopping_list(wish, 0)):
                    wish[item]['amount'] -= 1
                self.machine_craft(item, wish[item]['amount'])
            except FactorioError as err:
                print(f'failed to produce {num_produced} of {item}')
                print(err)
        for furnace, item in self.current_furnaces:
            try:
                num_produced = self.data.furnaces[furnace]['crafting_speed'] * (seconds // self.data.recipes[item]['energy'])
                # find the number of items that can *actually* be produced - brute force
                wish = {item: {'name': item, 'amount': num_produced}}
                while not self.check_list(self.shopping_list(wish, 0)):
                    wish[item]['amount'] -= 1
                self.machine_craft(item, wish[item]['amount'])
            except FactorioError as err:
                print(f'failed to smelt {num_produced} of {item}')
                print(err)

    def machine_craft(self, item, num_produced):
        wish = {item: {'name': item, 'amount': num_produced}}
        self.deduct_list(self.shopping_list(wish,0))
        self.place_in_inventory(item, num_produced)
