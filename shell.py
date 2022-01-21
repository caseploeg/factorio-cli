import cmd2
import argparse

class FactorioShell(cmd2.Cmd):
    intro = "Welcome to factorio-cli. Type help or ? to list cmds \n"
    prompt = "> "

    def __init__(self, sim):
        super().__init__()
        self.sim = sim
    
    # --- cmds --- #
    def do_exit(self, args):
        'terminates the shell'
        exit()
    
    def do_cookbook(self, args):
        'show all recipes currently available'
        pass
    
    spawn_parser = cmd2.Cmd2ArgumentParser()
    spawn_parser.add_argument('item', help='item type to spawn in')
    spawn_parser.add_argument('amount', type=int, help='amount of the given item to be spawned in')

    @cmd2.with_argparser(spawn_parser)
    def do_spawn(self, args):
        'grant items to player without spending resources or using crafting time'
        self.sim.place_in_inventory(args.item, args.amount)
        self.poutput('~~magic~~')
