import cmd2
import cmd2.ansi
from cmd2.table_creator import (
    Column, 
    SimpleTable
)
import argparse
import datetime
import json
import ast
from types import SimpleNamespace

from shortcuts import convert_aliases
import client
import utils


class FactorioShell(cmd2.Cmd):
    intro = "Welcome to factorio-cli. Type help or ? to list cmds \n"
    prompt = "(0:00:00) "

    mineable = ['stone', 'coal', 'iron-ore', 'copper-ore']
    def __init__(self, data_dict):
        super().__init__(startup_script='scripts/startup.txt', silence_startup_script=True)
        # register hooks
        self.register_postcmd_hook(self.update_prompt)
        self.register_postparsing_hook(self.arg_alias_hook)
        # handle args 
        self.data = SimpleNamespace(**data_dict) 
        self.allow_ansi = cmd2.ansi.allow_style 

    def update_prompt(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        """Update shell prompt with the amount of time elapsed in the simulation"""
        game_time = client.get_game_time()
        self.prompt = f'({datetime.timedelta(0, game_time)})'
        return data

    def arg_alias_hook(self, params: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A hook to dynamically convert aliases to full-name versions"""
        converted = ' '.join(convert_aliases(params.statement.raw.split()))
        params.statement = self.statement_parser.parse(converted)
        return params 


    def do_time(self, args):
        """Return the current time elapased in the sim (in seconds)"""
        game_time = client.get_game_time()
        self.poutput(game_time)

    def do_clear(self, args):
        """Reset the simulation and wipe all data"""
        client.clear()

    spawn_parser = cmd2.Cmd2ArgumentParser()
    spawn_parser.add_argument('item', help='item type to spawn in')
    spawn_parser.add_argument('amount', type=int, help='amount of the given item to be spawned in')

    @cmd2.with_argparser(spawn_parser)
    def do_spawn(self, args):
        """grant items to player without spending resources or using crafting time"""
        client.spawn(args.item, args.amount)

    def research_tech_choices(self):
        options = client.suggest().split()
        items = []
        for i in range(len(options)):
            researchable = client.researchable(options[i])
            if researchable == 'pog':
                description = cmd2.ansi.style("researchable",fg=cmd2.ansi.Fg.LIGHT_GREEN)
            else:
                description = cmd2.ansi.style("researchable",fg=cmd2.ansi.Fg.LIGHT_RED)
            items.append(cmd2.CompletionItem(options[i], description))
        return items 

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
        msg = client.research(args.tech)
        print(msg)
    
    tech_needed_parser = cmd2.Cmd2ArgumentParser()
    tech_needed_parser.add_argument('tech', help='name of goal technology')

    @cmd2.with_argparser(tech_needed_parser)
    def do_tech_needed(self, args):
        """ Given a goal technology, return all the technologies required to unlock it, as well as all the science packs
        """
        self.poutput(utils.tech_needed(self.data.technology, args.tech))

    def do_suggest(self, args):
        """ Return all technologies that could be researched next
        """ 
        msg = client.suggest()
        self.poutput(msg)

    def do_techbook(self, args):
        msg = client.techbook()
        self.poutput(msg)

    def do_limits(self, args):
        msg = client.limits()
        self.poutput(msg)

    def do_cookbook(self, args):
        """ Return all recipes currently available to the player
        """
        msg = client.cookbook()
        self.poutput(msg)

    machines_parser = cmd2.Cmd2ArgumentParser()
    group = machines_parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--assemblers', action='store_true', help='display only assemblers')
    group.add_argument('-f', '--furnaces', action='store_true', help='display only furnaces')
    group.add_argument('-m', '--miners', action='store_true', help='display only miners')

    @cmd2.with_argparser(machines_parser)
    def do_machines(self, args):
        """ Return all machines currently running
        """
        msg = client.machines()
        if msg:
            self.poutput(msg)
        else:
            self.poutput("no machines :(")

    def wish_item_choices(self):
        # suggest recipes and technology
        return set(self.data.recipes.keys()).union(set(self.data.technology.keys()))
    
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
        if args.item in self.data.recipes:
            self.poutput(json.dumps(utils.shopping_list(self.data.recipes, request, args.level), indent=4))
            found = True
        if args.item in self.data.technology:
            # if the player wished for a technology, output the list of potions required for research
            self.poutput(json.dumps(utils.get_potion_list(self.data.technology, args.item)))
            found = True
        if not found: 
            self.poutput(f'could not find {args.item}')

    def place_machine_choices(self, arg_tokens):
        # todo: change this to only display machines currently in inventory
        return list(self.data.mining_drills.keys()) + list(self.data.furnaces.keys()) + list(self.data.assemblers.keys())

    def place_item_helper(self, machine):
        if machine in self.data.mining_drills:
            return {'stone', 'coal', 'iron-ore', 'copper-ore'}       
        elif machine in self.data.furnaces:
            return {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}
        elif machine in self.data.assemblers:
            return self.data.recipes
        else:
            return {}

    def place_item_choices(self, arg_tokens):
        """Choices provider for place cmd"""
        # todo: make this work with machine aliases as well
        machine = arg_tokens['machine'][0]
        return self.place_item_helper(machine)


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
        msg = client.place(args.machine, args.item, args.amount)
        self.poutput(msg)

    def do_inventory(self, args):
        """Return the player's inventory"""
        current_items = client.get_inventory()
        print(json.dumps(current_items, indent=4))

    next_parser = cmd2.Cmd2ArgumentParser()
    next_parser.add_argument('minutes', type=int, default=1, nargs='?', help='the number of minutes to run the simulation for')

    @cmd2.with_argparser(next_parser)
    def do_next(self, args):
        """Simulate factory production for a given number of minutes"""
        client.next(args.minutes)
    
    def do_prod(self, args):
        """Return production statistcs for the current state of the factory"""
        self.poutput('running the factory for one minute will have the following effect:') 
        data_str = client.production()
        #TODO: just send JSON from the server instead
        data = ast.literal_eval(data_str)
        cols = [Column("Item", width=30), Column("Actual", width=10), Column("Potential", width=10)]
        st = SimpleTable(cols)
        table = st.generate_table(data)
        self.poutput(table)

    mine_parser = cmd2.Cmd2ArgumentParser()
    mine_parser.add_argument('resource', choices=mineable, help='resource type')
    mine_parser.add_argument('amount', type=int, help='amount of the given resource to be mined')

    @cmd2.with_argparser(mine_parser) 
    def do_mine(self, args):
        """Mine a resource"""
        msg = client.mine(args.resource, args.amount)
        self.poutput(msg)

    def craft_item_choices(self, arg_tokens):
        # only suggest items that the player has the resources to actually craft
        # TODO: cache / send less requests
        return filter(lambda x: client.craftable(x, 1) == 'pog', client.cookbook().split())


    craft_parser = cmd2.Cmd2ArgumentParser()
    craft_parser.add_argument('item', choices_provider=craft_item_choices, help='item type')
    craft_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')

    @cmd2.with_argparser(craft_parser)
    def do_craft(self, args):
        """Craft an item in the player's inventory"""
        msg = client.craft(args.item, args.amount)
        self.poutput(msg)

    limit_parser = cmd2.Cmd2ArgumentParser() 
    limit_parser.add_argument('item', help='item type')
    limit_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')

    @cmd2.with_argparser(limit_parser)
    def do_limit(self, args):
        """Set rate limit on production for certain items"""
        msg = client.limit(args.item, args.amount)
        self.poutput(msg)

    loadsave_parser = cmd2.Cmd2ArgumentParser()
    loadsave_parser.add_argument('file', help='path to save file')

    @cmd2.with_argparser(loadsave_parser)
    def do_load(self, args):
        with open(args.file) as save_file:
            content = ''.join(save_file.readlines())
            client.update(content)

    @cmd2.with_argparser(loadsave_parser)
    def do_save(self, args):
        with open(args.file, 'w') as save_file:
            cur_state = client.state()
            save_file.write(cur_state)
