"""Factorio simulation"""

# stdlib imports
import functools
import json
from collections import defaultdict, Counter
from types import SimpleNamespace
import math

# project imports
from errors import * 
from files import load_files
from init import *
from utils import *
from craft import *
from data import *

# operations:
# craft
# next
# place
# mine
# research

class Sim():
    def __init__(self, data_dict):
        self.data = SimpleNamespace(**data_dict)
        self.clear()

    # TODO: error message on crafting can return the full missing list
    def craft(self, item, amount):
        res, missing, available, msg = craftable(self, item, amount)
        if res == 0:
            missing[item] = amount
            self.deduct_list(available)
            self.place_in_inventory(self.data.recipes[item]['products'][0]['name'], amount)
            time_spent = self.craft_time_list(missing)
            print(time_spent)
            # put excess production into player inventory based on bulk orders 
            self.grant_excess_production(missing)
            if time_spent > 0:
                self.next(time_spent)
            return 0, None
        elif res == 2:
            return 1, f'crafting {amount} {item} failed, {msg}'
        else:
            return 1, f'something went wrong, {msg}'

    def next(self, seconds, check_rates=False):
        # simulate factory production, moving forwards in time
        # depends on current state of inventory before next() was called.
        # next(60) + next(60) != next(120), because state changes after each call 
        def produce(ci):
            def miner_potential(miner, item, amount, seconds):
                return (self.data.mining_drills[miner]['mining_speed']
                      * amount 
                      * seconds)
            def assembler_potential(assembler, item, amount, seconds):
                return (self.data.assemblers[assembler]['crafting_speed'] 
                      * amount 
                      * self.data.recipes[item]['products'][0]['amount'] 
                      * (seconds // self.data.recipes[item]['energy']))
            def furnace_potential(furnace, item, amount, seconds):
                return (self.data.furnaces[furnace]['crafting_speed']
                      * amount
                      * (seconds // self.data.recipes[item]['energy']))
            def machine_craft(item, num_produced, ci):
                if item not in self.data.resources:
                    self.deduct_list(shopping_list(self.data.recipes, {item: num_produced}), ci)
                    self.place_in_inventory(self.data.recipes[item]['products'][0]['name'], num_produced, ci)
                else:
                    self.place_in_inventory(item, num_produced, ci)
            def miner_actual(item, potential):
                return potential 
            def assembler_actual(item, potential):
                # respect rate limits
                if item in self.limited_items:
                    potential = min(potential, self.limited_items[item] - ci[item])
                # find actual production rate, make as many items as possible as long as the ingredients
                # are in inventory
                wish = {item: potential}
                is_missing, _, _ = self.check_list(shopping_list(self.data.recipes, wish), ci)
                while is_missing:
                    wish[item] -= 1
                    is_missing, _, _ = self.check_list(shopping_list(self.data.recipes, wish), ci)
                return wish[item]
            def furnace_actual(item, potential):
                return assembler_actual(item, potential) 
            prod_rates = defaultdict(lambda: defaultdict(int))
            calc_actual = {0: miner_actual, 1: assembler_actual, 2: furnace_actual}
            calc_potential = {0: miner_potential, 1: assembler_potential, 2: furnace_potential}
            # core algo: for each machine: potential -> actual -> craft
            for key, machine_group, in enumerate([self.miners, self.assemblers, self.furnaces]): 
                for machine_item_key, amount in machine_group.items():
                    item, machine = machine_item_key.split(':')
                    potential = calc_potential[key](machine, item, amount, seconds)  
                    actual = calc_actual[key](item, potential) 
                    prod_rates[item]['potential'] += potential 
                    prod_rates[item]['actual'] += actual
                    machine_craft(item, actual, ci)
            return prod_rates
        # ---- end of produce() helper function                    
        if check_rates:
            ci = self.current_items.copy()
        else:
            # move time forwards and commit to item changes
            self.game_time += seconds
            ci = self.current_items
        return produce(ci)

    def place_machine(self, machine, item, amount=1):
        def store(machine, item, amount):
            storage = {0: self.miners, 1: self.assemblers, 2: self.furnaces}
            for key, mt in enumerate([self.data.mining_drills, self.data.assemblers, self.data.furnaces]):
                if machine in mt:
                    storage[key][f'{item}:{machine}'] += amount
        res, msg = self.deduct_item(machine, amount)
        if res != 0:
            return res, f'failed to place {amount} of {machine}, {msg}'
        res, msg = is_machine_compatible(self.data, machine, item)
        if res != 0:
            self.place_in_inventory(machine, amount)
            return res, f'failed to place {machine} producing {item}, {msg}'
        if machine in self.data.assemblers:
            res, msg = self.is_recipe_unlocked(item)
            if res != 0:
                self.place_in_inventory(machine, amount)
                return res, f'failed to place {machine} producing {item}, {msg}'
        store(machine, item, amount)
        return 0, None

    def mine(self, resource, amount):
        if resource in {'stone', 'coal', 'iron-ore', 'copper-ore', 'crude-oil'}:
            self.place_in_inventory(resource, amount)
            time_spent = self.data.resources[resource]['mineable_properties']['mining_time'] * amount
            self.next(time_spent)
            return 0, None
        else:
            return 1, f'{resource} cannot be mined'

    def research(self, tech):
        # research a given technology, raise exception if potions not available
        # or given technology can not be researched yet
        res, msg = self.researchable(tech)
        if res == 0:
            pl = get_potion_list(self.data.technology, tech)
            self.deduct_list(pl)
            self.current_tech.add(tech)
            # unlock recipes
            for effect in self.data.technology[tech]['effects']:
                if effect['type'] == 'unlock-recipe':
                    self.current_recipes.add(effect['recipe'])
            return 0, None
        else:
            return res, msg

    def check_item(self, item, amount, ci=None):
        if ci == None:
            ci = self.current_items
        res = ci[item] >= amount 
        return res, max(0, amount - ci[item]), min(amount, ci[item])

    def check_list(self, sh, ci):
        def reduce_sh(accum, x):
            res, missing, available = accum
            r, m, av = self.check_item(x[0], x[1], ci)
            res = r and res
            if m > 0:
                missing[x[0]] = m
            if av > 0:
                available[x[0]] = av
            return res, missing, available
            
        vals = [True, Counter(), Counter()]
        res, missing, available = functools.reduce(lambda accum, x: reduce_sh(accum, x), sh.items(), vals)
        return not res, missing, available 

    def deduct_item(self, item, amount, ci=None):
        if ci == None:
            ci = self.current_items
        if ci[item] < amount:
            return 1, f'player has < {amount} of {item} in inventory'
        ci[item] -= amount
        return 0, None

    def deduct_list(self, sh, ci=None):
        # NOTE: this function doesn't error check because it only gets called
        # after some validation has already been done
        if ci == None:
            ci = self.current_items
        for k, v in sh.items():
            ci[k] -= v

    def place_in_inventory(self, item, amount, ci=None):
        if ci == None:
            ci = self.current_items
        # enfore integral system - avoid very real issues
        ci[item] += int(amount)

    def craft_time_list(self, craft_list):
        time = 0
        for name, amount in craft_list.items():
            time += craft_time(self.data, name, amount) 
            print(time, name, amount)
        return time

    # TODO: is this correct?
    def grant_excess_production(self, craft_list):
        for name, amount in craft_list.items():
            ratio = self.data.recipes[name]['main_product']['amount']
            if amount % ratio != 0:
                self.place_in_inventory(name, (ratio * (1 + (amount // ratio))) - amount)

    def set_limit(self, item, amount):
        self.limited_items[item] = amount

    def preqs_researched(self, tech):
        preq = self.data.technology[tech]['prerequisites']    
        return functools.reduce(lambda x, y: x and y in self.current_tech, preq, True)

    def researchable(self, tech):
        """Decide whether a given technology can be researched or not"""
        if tech not in self.data.technology:
            return 1, f'researchable - {tech} could not be found in the list of tecnologies'
        if tech in self.current_tech:
            return 1, f'researchable - {tech} has already been researched'
        pl = get_potion_list(self.data.technology, tech)
        preq = self.data.technology[tech]['prerequisites']    
        if not self.preqs_researched(tech):
            return 1, f'researchable - one or more prerequisite technologies for {tech} have not been researched'
        res, missing, _ = self.check_list(pl, self.current_items) 
        if res != 0: 
            return res, f'researchable - missing the potions required to research {tech}, {missing}'
        return 0, None

    # find all technologies that could be researched next 
    def all_researchable(self):
        res = set()
        for tech in self.data.technology:
            if tech not in self.current_tech and self.preqs_researched(tech):
                res.add(tech)
        return res

    def get_starter_recipes(self):
        enabled = set()
        for key, value in self.data.recipes.items():
          if value['enabled']:
            enabled.add(key)
        return enabled
          
    def clear(self):
        self.game_time = 0
        self.current_tech = get_starter_tech() 
        self.current_recipes = self.get_starter_recipes() 
        self.current_items = get_starter_inventory() 
        self.miners = defaultdict(int)
        self.assemblers = defaultdict(int)
        self.furnaces = defaultdict(int)
        self.limited_items = dict() 

    def update_state(self, game_time, current_tech, current_recipes, current_items, miners, assemblers, furnaces, limited_items):
        self.game_time = game_time 
        self.current_tech = current_tech 
        self.current_recipes = current_recipes 
        self.current_items = current_items
        self.miners = miners 
        self.assemblers = assemblers 
        self.furnaces = furnaces 
        self.limited_items = limited_items 

    def serialize_state(self):
        # every field is sorted so that this function is deterministic. 
        # the same actions performed in a simulation should produce the exact same
        # save file every time! Important for running tests
        def get_state():
            return {
                'game_time': self.game_time,
                'current_tech': sorted(list(self.current_tech)),
                'current_recipes': sorted(list(self.current_recipes)),
                'current_items': dict(sorted(self.current_items.items())),
                'miners': dict(sorted(self.miners.items())),
                'assemblers': dict(sorted(self.assemblers.items())),
                'furnaces': dict(sorted(self.furnaces.items())),
                'limited_items': dict(sorted(self.limited_items))
            }
        # Sort the outer dictionary and ensure inner dictionaries are sorted as well
        s = {k: v if isinstance(v, (int, str, list, float)) else dict(sorted(v.items())) for k, v in get_state().items()}
        return json.dumps(s, sort_keys=True)

    def deserialize_state(self, s_json):
        s = json.loads(s_json)
        self.game_time = s['game_time']
        self.current_tech = set(s['current_tech'])
        self.current_recipes = set(s['current_recipes'])
        self.current_items = defaultdict(int, s['current_items'])
        self.miners = defaultdict(int, s['miners'])
        self.assemblers = defaultdict(int, s['assemblers'])
        self.furnaces = defaultdict(int, s['furnaces'])
        self.limited_items = s['limited_items']

    def machines(self):
        combined = defaultdict()
        combined.update(self.miners)
        combined.update(self.assemblers)
        combined.update(self.furnaces)
        return '\n'.join([f'{k} : {v}' for k,v in combined.items()])

    def production(self):
        production = self.next(60, True)
        data = [[k, v['actual'], v['potential'], self.current_items[k], (self.limited_items[k] if k in self.limited_items else '')] for k, v in production.items()]
        return data

    def is_recipe_unlocked(self, item):
        if item in self.current_recipes:
            return 0, None
        else:
            return 1, f'{item} is not unlocked'

    