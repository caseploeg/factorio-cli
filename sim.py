import functools
import json
from collections import defaultdict, Counter
from types import SimpleNamespace
import math

from errors import * 
from constants import *
from files import load_files
from init import *

def convert_to_sh(d):
    sh = dict()
    for k, v in d.items():
        sh[k] = {'name': k, 'amount': v}
    return sh

def is_mineable(resource):
    if resource in {'stone', 'coal', 'iron-ore', 'copper-ore'}:
        return 0, None 
    else:
        return 1, f'{resource} cannot be mined'

def is_smeltable(resource):
    if resource in {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}:
        return 0, None
    else:
        return 1, f'{resource} cannont be smelted'

class Sim():
    def __init__(self, data_dict):
        self.clear()
        data = SimpleNamespace(**data_dict)
        self.data = data

    def ratio(self, item):
        """Find the optimal production ratio for assembling an item"""
        sh = self.shopping_list(convert_to_sh({item: 1}), 0)
        r_list = []
        for k, v in sh.items():
            r_list.append(int(self.craft_time(k, v['amount']) * 10))
        denom = math.gcd(*r_list)
        for k, v in sh.items():
            sh[k]['amount'] = self.craft_time(k, v['amount']) * 10 // denom
        return sh
        

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
    # with all items required to build the items in the shopping list
    # if level == 0 -> only the direct ingredients are calculated
    # if level == 1 -> all resources required are calculated (raw materials, sub-components...)
    # if level == 2 -> only raw materials are calculated (iron ore, coal, etc)
    # NOTE: shopping_list respects bulk recipes, but rounds up when the production ratio does not match the amount needed
    # ex: wish iron-stick 2 -> need 1 iron-plate , but wish iron-stick 1 -> need 1 iron-plate as well - no fractions
    # see grant_excess_production() to see how extra items from bulk orders get placed in player inventory
    def shopping_list(self, items, level): 
        # avoid side effects >:)
        all_items = items.copy()
        def helper(items):
            ing_lists = list(
                map(lambda x: [{'name': k['name'], 'amount': k['amount'] * math.ceil(items[x[0]]['amount'] / self.data.recipes[items[x[0]]['name']]['main_product']['amount'])} for k in x[1]], 
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
            return 0, None
        else:
            return 1, f'{item} is not unlocked'

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
    def check_item(self, item, amount, ci=None, ret_missing=False):
        if ci == None:
            ci = self.current_items
        res = ci[item] >= amount 
        if ret_missing:
            return res, max(0, amount - ci[item])
        else:
            return res

    def check_list(self, sh, ci=None, ret_missing=False):
        def reduce_sh(accum, x):
            res, missing = accum
            r, m = self.check_item(x['name'], x['amount'], ci, ret_missing=True)
            res = r and res
            missing[x['name']] = m
            return res, missing
            
        if ci == None:
            ci = self.current_items
        if ret_missing:
            vals = [True, dict()]
            res, missing = functools.reduce(lambda x, y: reduce_sh(x, y), sh.values(), vals)
            return 0 if res else 1, missing 
        else:
            return functools.reduce(lambda x, y: x and self.check_item(y['name'], y['amount'], ci), sh.values(), True) 

    def deduct_item(self, item, amount, ci=None):
        if ci == None:
            ci = self.current_items
        if self.check_item(item, amount):
            ci[item] -= amount
            return 0, None
        else:
            return 1, f'player has < {amount} of {item} in inventory'

    def deduct_list(self, sh, ci=None):
        if ci == None:
            ci = self.current_items
        for k, v in sh.items():
            ci[k] -= v['amount']

    def place_in_inventory(self, item, amount, ci=None):
        if ci == None:
            ci = self.current_items
        # enfore integral system - avoid very real issues
        ci[item] += int(amount)
    
    def is_machine_compatible(self, machine, item):
        machine_types = zip([self.data.mining_drills, self.data.assemblers, self.data.furnaces], [x for x in range(3)])
        predicates = {0: is_mineable, 1: self.is_recipe_unlocked, 2: is_smeltable}
        for mt, key in machine_types:
            if machine in mt:
                return predicates[key](item)

    def place_machine(self, machine, item, amount=1):
        def store(machine, item, amount):
            machine_types = [(self.data.mining_drills, 0), (self.data.assemblers, 1), (self.data.furnaces, 2)]
            storage = {0: self.miners, 1: self.assemblers, 2: self.furnaces}
            for mt, key in machine_types:
                if machine in mt:
                    storage[key][(item, machine)] += amount

        res, msg = self.deduct_item(machine, amount)
        if res != 0:
            return res, f'failed to place {amount} of {machine}, {msg}'
            
        res, msg = self.is_machine_compatible(machine, item)
        if res != 0:
            self.place_in_inventory(machine, amount)
            return res, f'failed to place {machine} producing {item}, {msg}'

        store(machine, item, amount)
        return 0, None

    def craftable(self, item, amount):
        """return type: res, missing, available"""
        # check if item recipe is unlocked
        res, msg = self.is_recipe_unlocked(item)
        if res != 0:
            return 1, None, None 
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

    def craft_time_list(self, craft_list):
        time = 0
        for name, amount in craft_list.items():
            time += self.craft_time(name, amount) 
        return time
    
    def craft_time(self, name, amount):
        return self.data.recipes[name]['energy'] / self.data.recipes[name]['main_product']['amount'] * amount

    def grant_excess_production(self, craft_list):
        for name, amount in craft_list.items():
            ratio = self.data.recipes[name]['main_product']['amount']
            if amount % ratio != 0:
                self.place_in_inventory(name, (ratio * (1 + (amount // ratio))) - amount)

    def craft(self, item, amount):
        res, missing, available = self.craftable(item, amount)
        if res == 0:
            missing[item] = amount
            av_sh = convert_to_sh(available)
            self.deduct_list(av_sh)
            self.place_in_inventory(item, amount)
            time_spent = self.craft_time_list(missing)
            # put excess production into player inventory based on bulk orders 
            self.grant_excess_production(missing)
            if time_spent > 0:
                self.next(time_spent)
            return 0, None
        elif res == 2:
            return 1, f'crafting {amount} {item} failed'

    def set_limit(self, item, amount):
        self.limited_items[item] = amount

    

    def mine(self, resource, amount):
        res, msg = is_mineable(resource)
        if res != 0:
            return 1, f'failed to mine {amount} {resource}, {msg}'
        else:
            self.place_in_inventory(resource, amount)
            time_spent = self.data.resources[resource]['mineable_properties']['mining_time'] * amount
            self.next(time_spent)
            return 0, None

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
        res, missing = self.check_list(pl, ret_missing=True) 
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

    def clear(self):
        # time-related
        self.game_time = 0
        # possessions
        self.current_tech = get_starter_tech() 
        self.current_recipes = get_starter_recipes() 
        self.current_items = get_starter_inventory() 
        # machines
        self.miners = defaultdict(int)
        self.assemblers = defaultdict(int)
        self.furnaces = defaultdict(int)
        self.limited_items = dict() 

    # simulate production for a given number of seconds 
    # todo: fix simulation so assemblers and furnaces produce based on available
    # materials -- do *not* use `craft()`
    # NOTE: two consecutive calls to next() do not have the same effect as one long next()
    # because production depends on the current state of inventory before next() was called
    # next(60) + next(60) != next(120)
    def next(self, seconds, check_rates=False):
        """Simulate the next given seconds of production

        If check_rates=True, do not advance game time and do not actually craft items, only calculate production rates 
        """
        def produce(ci):
            def machine_craft(item, num_produced, ci):
                wish = {item: {'name': item, 'amount': num_produced}}
                if item not in self.data.resources:
                    self.deduct_list(self.shopping_list(wish, 0), ci)
                self.place_in_inventory(item, num_produced, ci)

            miner_potential = lambda miner, item, amount, seconds: self.data.mining_drills[miner]['mining_speed'] * amount * seconds
            assembler_potential = lambda assembler, item, amount, seconds: self.data.assemblers[assembler]['crafting_speed'] * amount * self.data.recipes[item]['main_product']['amount'] * (seconds // self.data.recipes[item]['energy']) 
            furnace_potential = lambda furnace, item, amount, seconds: self.data.furnaces[furnace]['crafting_speed'] * amount * (seconds // self.data.recipes[item]['energy'])

            def miner_actual(item, potential):
                return potential 
            
            def assembler_actual(item, potential):
                # respect rate limits
                if item in self.limited_items:
                    potential = min(potential, self.limited_items[item] - ci[item])
                # find actual production rate 
                wish = {item: {'name': item, 'amount': potential}}
                while not self.check_list(self.shopping_list(wish, 0), ci):
                    wish[item]['amount'] -= 1
                return wish[item]['amount']
            
            def furnace_actual(item, potential):
                return assembler_actual(item, potential) 

            prod_rates = defaultdict(lambda: defaultdict(int))
            machine_groups = zip([self.miners, self.assemblers, self.furnaces], [x for x in range(3)])
            calc_actual = {0: miner_actual, 1: assembler_actual, 2: furnace_actual}
            calc_potential = {0: miner_potential, 1: assembler_potential, 2: furnace_potential}

            # core algo: for each machine: potential -> actual -> craft
            for machine_group, key in machine_groups: 
                for (item, machine), amount in machine_group.items():
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
            self.game_time += seconds
            ci = self.current_items
        return produce(ci)
