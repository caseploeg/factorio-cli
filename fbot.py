import client
import random
import time



from shell import *
from files import load_files
from sim import Sim

# TODO: fbot does not do research :( 
if __name__ == "__main__":
    data_dict = load_files()
    shell = FactorioShell(data_dict)

    while True: 
        client.mine('stone', 5)
        client.mine('iron-ore', 5)
        client.mine('copper-ore', 5)

        
        recipes = client.cookbook().split()
        recipe = recipes[random.randint(0, len(recipes)-1)]
        msg = client.craft(recipe, 1)
        if msg == 'pog':
            options = list(shell.place_item_helper(recipe))
            option = None
            if options:
                option = options[random.randint(0, len(options)-1)]
            if option: 
                print(recipe, option)
                client.place(recipe, option, 1)

        """
        client.craft('stone-furnace', 1)
        client.craft('burner-mining-drill', 1)
        client.place('stone-furnace', 'iron-plate', 1)
        client.place('burner-mining-drill', 'iron-ore', 1)
        """
        time.sleep(5)
       