import cmd2
import argparse

import datetime
import json

class FactorioShell(cmd2.Cmd):
    intro = "Welcome to factorio-cli. Type help or ? to list cmds \n"
    prompt = "(0:00:00) "

    mineable = ['stone', 'coal', 'iron-ore', 'copper-ore']

    def __init__(self, sim):
        super().__init__()
        self.register_postcmd_hook(self.update_prompt)
        self.sim = sim
    
    def update_prompt(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        """Update shell prompt with the amount of time elapsed in the simulation"""
        self.prompt = f'({datetime.timedelta(0, self.sim.game_time)}) '
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

    def do_machines(self, args):
        """ Return all machines currently running
        """
        self.poutput(self.sim.current_miners)
        self.poutput(self.sim.current_assemblers)
        self.poutput(self.sim.current_furnaces)
    
    wish_parser = cmd2.Cmd2ArgumentParser()
    wish_parser.add_argument('item', help='item type')
    wish_parser.add_argument('amount', nargs='?', default=1, type=int, help='amount of the given item, defaults to 1')
    wish_parser.add_argument('-l', '--level', nargs='?', default=0, type=int, choices=[0,1,2], help='determines type of items included in the wishlist.\nlevel=zero, by default, returns only immediate ingredients for a recipe.\nlevel=one, returns all intermediate ingredients required.\nlevel=two, returns only the raw materials required.')

    @cmd2.with_argparser(wish_parser)
    def do_wish(self, args):
        """ Return a shopping list for a given item
        """
        request = {
            args.item: {
                'name': args.item,
                'amount': args.amount
            }
        }
        if args.item in self.sim.data.recipes:
            self.poutput(json.dumps(self.sim.shopping_list(request, args.level), indent=4))
        else:
            self.poutput(f'could not find {item}')

    '''
    def complete_place(self, text, line, begidx, endidx):
        """Completion function for place cmd"""
        return self.basic_complete(text, line, begidx, endidx, self.sim.data.mining_drills)
    '''

    def place_machine_choices(self, arg_tokens):
        # todo: change this to only display machines currently in inventory
        return list(self.sim.data.mining_drills.keys()) + list(self.sim.data.furnaces.keys()) + list(self.sim.data.assemblers.keys())
     
    def place_item_choices(self, arg_tokens):
        """Choices provider for place cmd"""
        machine = arg_tokens['machine'][0]
        if machine in self.sim.data.mining_drills:
            return {'stone', 'coal', 'iron-ore', 'copper-ore'}       
        elif machine in self.sim.data.furnaces:
            return {'stone-brick', 'iron-plate', 'copper-plate', 'steel-plate'}
        elif machine in self.sim.data.assemblers:
            return self.sim.current_recipes

    place_parser = cmd2.Cmd2ArgumentParser()
    place_parser.add_argument('machine', choices_provider=place_machine_choices, help='machine type to be placed')
    place_parser.add_argument('item', choices_provider=place_item_choices, help='item type this machine will generate')

    @cmd2.with_argparser(place_parser)
    def do_place(self, args):
        """Given a machine type and an item type, place a machine that will generate that item\nWill fail if:
        - machine is not in inventory
        - item is not compatible with the machine
        """
        res, msg = self.sim.place_machine(args.machine, args.item)
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

