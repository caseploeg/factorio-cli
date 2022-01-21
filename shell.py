import cmd2
import argparse

class FactorioShell(cmd2.Cmd):
    intro = "Welcome to factorio-cli. Type help or ? to list cmds \n"
    prompt = "> "

    def __init__(self, sim):
        super().__init__()
        self.sim = sim
    
    spawn_parser = cmd2.Cmd2ArgumentParser()
    spawn_parser.add_argument('item', help='item type to spawn in')
    spawn_parser.add_argument('amount', type=int, help='amount of the given item to be spawned in')

    @cmd2.with_argparser(spawn_parser)
    def do_spawn(self, args):
        'grant items to player without spending resources or using crafting time'
        self.sim.place_in_inventory(args.item, args.amount)
        self.poutput('~~magic~~')


    research_parser = cmd2.Cmd2ArgumentParser()
    research_parser.add_argument('tech', help='name of technology to research')

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

    @cmd2.with_argparser(wish_parser)
    def do_wish(self, args):
        """ Return a shopping list for a given item/technology
        """
        self.poutput(args.item)
        self.poutput(args.amount)
        