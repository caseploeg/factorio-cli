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

class Sim():
    def __init__(self, data_dict):
        self.data = SimpleNamespace(**data_dict)
        self.clear()

    def launch(self):
        if self.current_items['rocket-part'] >= 100:
            self.current_items['rocket-part'] -= 100
            return True
        return False
    
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
            # potential = amount_of_machines * craft_speed * seconds // energy
            def p_eq(amount_machines, amount_produced, speed, seconds, energy):
                return amount_machines * speed * amount_produced * (seconds if energy == 1 else (seconds // energy))

            def miner_potential(miner, item, amount, seconds):
                return p_eq(amount, 1, self.data.mining_drills[miner]['mining_speed'], seconds, 1)

            def assembler_potential(assembler, item, amount, seconds):
                return p_eq(amount, self.data.recipes[item]['products'][0]['amount'], self.data.assemblers[assembler]['crafting_speed'], seconds, self.data.recipes[item]['energy'])

            def furnace_potential(furnace, item, amount, seconds):
                return p_eq(amount, 1, self.data.furnaces[furnace]['crafting_speed'], seconds, self.data.recipes[item]['energy'])

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
                    # should almost always be > 0 but if the limit was set after getting a lot of items we could go negative
                    potential = min(potential, max(0, self.limited_items[item] - ci[item]))
                # find the bottleneck ingredient ratio and multiply by amount produced by recipe
                # TODO: can we surface the bottleneck information to the player? 
                a = min([ci[x] // amount for x, amount in shopping_list(self.data.recipes, {item:1}).items()]) * self.data.recipes[item]['products'][0]['amount']

                return min(a, potential) 

            def furnace_actual(item, potential):
                return assembler_actual(item, potential) 

            prod_rates = defaultdict(lambda: defaultdict(int))
            calc_actual = {0: miner_actual, 1: assembler_actual, 2: furnace_actual}
            calc_potential = {0: miner_potential, 1: assembler_potential, 2: furnace_potential}
            # core algo: for each machine: potential -> actual -> craft
            # TODO: ordering of machines processed matters, because inventory is affected immediately
            # players probably will probably want more control of this ordering
            # having something deterministic will help with testing as well
            
            # iterate through sorted keys - sort by priority! 
            for machine_item_key, amount in sorted(self.machines.items(), key=lambda item: int(item[0].split(':')[-1])):
                item, machine, _ = machine_item_key.split(':')
                key = self.data.machines[machine]
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
        res, msg = is_machine_compatible(self.data, machine, item)
        if res != 0:
            return res, f'failed to place {machine} producing {item}, {msg}'
        if machine in self.data.assemblers:
            if item not in self.current_recipes:
                return 1, f'failed to place {machine} producing {item}, recipe locked' 
        
        # deduct the item *after* validation, so that we don't have to put it back if something goes wrong
        res, msg = self.deduct_item(machine, amount)
        if res != 0:
            return res, f'failed to place {amount} of {machine}, {msg}'
        priority = 0
        self.machines[f'{item}:{machine}:{priority}'] += amount
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
            unlocked = []
            for effect in self.data.technology[tech]['effects']:
                if effect['type'] == 'unlock-recipe':
                    self.current_recipes.add(effect['recipe'])
                    unlocked.append(effect['recipe'])
            unlocked_str = '\n'.join(unlocked)
            msg = f'unlocked the following recipes:\n\n{unlocked_str}' 
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
    
    def set_machine_prio(self, machine, item, oldprio, newprio):
        oldkey = f'{item}:{machine}:{oldprio}'
        newkey = f'{item}:{machine}:{newprio}'
        if self.machines[oldkey] > 0:
            self.machines[oldkey] -= 1
            self.machines[newkey] += 1

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
        if not self.preqs_researched(tech):
            return 1, f'researchable - one or more prerequisite technologies for {tech} have not been researched'
        res, missing, _ = self.check_list(pl, self.current_items) 
        if res != 0: 
            return res, f'researchable - missing the potions required to research {tech}, {missing}'
        return 0, None

    def all_researchable(self):
        return set(filter(lambda tech: tech not in self.current_tech and self.preqs_researched(tech), self.data.technology))

    def clear(self):
        self.game_time = 0
        self.current_tech = get_starter_tech() 
        self.current_recipes = get_starter_recipes(self.data.recipes) 
        self.current_items = get_starter_inventory() 
        self.limited_items = dict() 
        self.machines = defaultdict(int)

    def update_state(self, game_time, current_tech, current_recipes, current_items, machines, limited_items):
        self.game_time = game_time 
        self.current_tech = current_tech 
        self.current_recipes = current_recipes 
        self.current_items = current_items
        self.machines = machines 
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
                'machines': dict(sorted(self.machines.items())),
                'limited_items': dict(sorted(self.limited_items.items()))
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
        self.machines = defaultdict(int, s['machines'])
        self.limited_items = s['limited_items']

    def production(self):
        production = self.next(60, True)
        data = [[k, v['actual'], v['potential'], self.current_items[k], (self.limited_items[k] if k in self.limited_items else '')] for k, v in production.items()]
        return data

    