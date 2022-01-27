import cmd2
import argparse

from cli import convert_aliases

import datetime
import json

class FactorioShell(cmd2.Cmd):
    intro = "Welcome to factorio-cli. Type help or ? to list cmds \n"
    prompt = "(0:00:00) "

    mineable = ['stone', 'coal', 'iron-ore', 'copper-ore']

    def __init__(self, sim):
        super().__init__()
        # register hooks
        self.register_postcmd_hook(self.update_prompt)
        self.register_postparsing_hook(self.arg_alias_hook)
        # handle args 
        self.sim = sim

    def update_prompt(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        """Update shell prompt with the amount of time elapsed in the simulation"""
        self.prompt = f'({datetime.timedelta(0, self.sim.game_time)}) '
        return data

    def arg_alias_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A hook to convert argument aliases to full-name versions"""
        full_name_args = ' '.join(convert_aliases(data.statement.arg_list))
        data.statement = self.statement_parser.parse(f"{data.statement.command} {full_name_args}")
        return data

    def do_clear(self, args):
        """Reset the simulation and wipe all data"""
        self.sim.clear()

    spawn_parser = cmd2.Cmd2ArgumentParser()
    spawn_parser.add_argument('item', help='item type to spawn in')
    spawn_parser.add_argument('amount', type=int, help='amount of the given item to be spawned in')

    @cmd2.with_argparser(spawn_parser)
    def do_spawn(self, args):
        """grant items to player without spending resources or using crafting time"""
        self.sim.place_in_inventory(args.item, args.amount)

    def research_tech_choices(self):
        return self.sim.all_researchable()

    research_parser = cmd2.Cmd2ArgumentParser()
    research_parser.add_argument('tech', choices_provider=research_tech_choices, help='name of technology to research')

    @cmd2.with_argparser(research_parser)
    def do_research(self, args): 
        """
        Research a given technology

        Will fail if:
        - prerequisites are not met
        - `tech` is already researched
        - missing required resources
        """
        res, msg = self.sim.research(args.tech)
        if res == 0:
            self.poutput(f'successfully researched {args.tech}')
        else:
            self.poutput(msg)
    
    tech_needed_parser = cmd2.Cmd2ArgumentParser()
    tech_needed_parser.add_argument('tech', help='name of goal technology')

    @cmd2.with_argparser(tech_needed_parser)
    def do_tech_needed(self, args):
        """ Given a goal technology, return all the technologies required to unlock it, as well as all the science packs
        """
        self.poutput(self.sim.tech_needed(args.tech))

    def do_suggest(self, args):
        """ Return all technologies that could be researched next
        """ 
        self.poutput(self.sim.all_researchable())

    def do_cookbook(self, args):
        """ Return all recipes currently available to the player
        """
        self.poutput(self.sim.current_recipes)

    machines_parser = cmd2.Cmd2ArgumentParser()
    group = machines_parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--assemblers', action='store_true', help='display only assemblers')
    group.add_argument('-f', '--furnaces', action='store_true', help='display only furnaces')
    group.add_argument('-m', '--miners', action='store_true', help='display only miners')

    @cmd2.with_argparser(machines_parser)
    def do_machines(self, args):
        """ Return all machines currently running
        """
        miners = {str(k): v for k,v in self.sim.miners.items()}
        assemblers = {str(k): v for k,v in self.sim.assemblers.items()}
        furnaces = {str(k): v for k,v in self.sim.furnaces.items()}
        if args.miners:
            self.poutput(json.dumps(miners, indent=4))
        elif args.assemblers:
            self.poutput(json.dumps(assemblers, indent=4))
        elif args.furnaces:
            self.poutput(json.dumps(furnaces, indent=4))
        else:
            self.poutput(json.dumps(miners, indent=4))
            self.poutput(json.dumps(assemblers, indent=4))
            self.poutput(json.dumps(furnaces, indent=4))

    def wish_item_choices(self):
        # suggest recipes and technology
        return set(self.sim.data.recipes.keys()).union(set(self.sim.data.technology.keys()))
    
    wish_parser = cmd2.Cmd2ArgumentParser()
    wish_parser.add_argument('item', choices_provider=wish_item_choices, help='item type')
    wish_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')
    wish_parser.add_argument('-l', '--level', nargs='?', default=0, type=int, choices=[0,1,2], help='determines type of items included in the wishlist.\nlevel=zero, by default, returns only immediate ingredients for a recipe.\nlevel=one, returns all intermediate ingredients required.\nlevel=two, returns only the raw materials required.')

    @cmd2.with_argparser(wish_parser)
    def do_wish(self, args):
        """Return a shopping list for a given item, will also produce a potion list for technologies"""
        request = {
            args.item: {
                'name': args.item,
                'amount': args.amount
            }
        }
        found = False
        if args.item in self.sim.data.recipes:
            self.poutput(json.dumps(self.sim.shopping_list(request, args.level), indent=4))
            found = True
        if args.item in self.sim.data.technology:
            # if the player wished for a technology, output the list of potions required for research
            self.poutput(json.dumps(self.sim.get_potion_list(args.item)))
            found = True
        if not found: 
            self.poutput(f'could not find {item}')

    def place_machine_choices(self, arg_tokens):
        # todo: change this to only display machines currently in inventory
        return list(self.sim.data.mining_drills.keys()) + list(self.sim.data.furnaces.keys()) + list(self.sim.data.assemblers.keys())
     
    def place_item_choices(self, arg_tokens):
        """Choices provider for place cmd"""
        # todo: make this work with machine aliases as well
        machine = arg_tokens['machine'][0]
        if machine in self.sim.data.mining_drills:
            return {'stone', 'coal', 'iron-ore', 'copper-ore'}       
        elif machine in self.sim.data.furnaces:
            return {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}
        elif machine in self.sim.data.assemblers:
            return self.sim.current_recipes
        else:
            return self.sim.current_recipes.union({'stone', 'coal', 'iron-ore', 'copper-ore', 'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'})

    place_parser = cmd2.Cmd2ArgumentParser()
    place_parser.add_argument('machine', choices_provider=place_machine_choices, help='machine type to be placed')
    place_parser.add_argument('item', choices_provider=place_item_choices, help='item type this machine will generate')
    place_parser.add_argument('amount', type=int, default=1, nargs='?', help='number of machines to place with the given config')

    @cmd2.with_argparser(place_parser)
    def do_place(self, args):
        """Given a machine type and an item type, place a machine that will generate that item\nWill fail if:
        - machine is not in inventory
        - item is not compatible with the machine
        """
        res, msg = self.sim.place_machine(args.machine, args.item, args.amount)
        if res == 0:
            self.poutput(f'successfully placed {args.machine}, processing {args.item}')
        else:
            self.poutput(msg)

    def do_inventory(self, args):
        """Return the player's inventory"""
        print(json.dumps(self.sim.current_items, indent=4))

    next_parser = cmd2.Cmd2ArgumentParser()
    next_parser.add_argument('minutes', type=int, help='the number of minutes to run the simulation for')

    @cmd2.with_argparser(next_parser)
    def do_next(self, args):
        """Simulate factory production for a given number of minutes"""
        seconds = args.minutes * 60
        self.sim.next(seconds)
    
    def do_prod(self, args):
        """Return production statistcs for the current state of the factory"""
        self.poutput('running the factory for one minute will have the following effect:') 
        self.poutput(json.dumps(self.sim.next(60, True), indent=4))

    mine_parser = cmd2.Cmd2ArgumentParser()
    mine_parser.add_argument('resource', choices=mineable, help='resource type')
    mine_parser.add_argument('amount', type=int, help='amount of the given resource to be mined')

    @cmd2.with_argparser(mine_parser) 
    def do_mine(self, args):
        """Mine a resource"""
        res, msg = self.sim.mine(args.resource, args.amount)
        if res == 0:
            self.poutput(f'successfully mined {args.resource}')
        else:
            self.poutput(msg)

    def craft_item_choices(self, arg_tokens):
        # only suggest items that the player has the resources to actually craft
        return filter(lambda x: self.sim.craftable(x, 1)[0] == 0, self.sim.current_recipes)

    craft_parser = cmd2.Cmd2ArgumentParser()
    craft_parser.add_argument('item', choices_provider=craft_item_choices, help='item type')
    craft_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')

    @cmd2.with_argparser(craft_parser)
    def do_craft(self, args):
        """Craft an item in the player's inventory"""
        res, msg = self.sim.craft(args.item, args.amount)
        if res == 0:
            self.poutput(f'successfully crafted {args.item}')
        else:
            self.poutput(msg)


    def ratio_item_choices(self):
        return self.sim.data.recipes.keys()

    ratio_parser = cmd2.Cmd2ArgumentParser()
    ratio_parser.add_argument('item', choices_provider=ratio_item_choices, help='item type')

    @cmd2.with_argparser(ratio_parser)
    def do_ratio(self, args):
        """Find the optimal production ratio for an item"""
        self.poutput(json.dumps(self.sim.ratio(args.item), indent=4))

    limit_parser = cmd2.Cmd2ArgumentParser() 
    limit_parser.add_argument('item', help='item type')
    limit_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')

    @cmd2.with_argparser(limit_parser)
    def do_limit(self, args):
        """Set rate limit on production for certain items"""
        self.sim.set_limit(args.item, args.amount)
