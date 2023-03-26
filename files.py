from contextlib import ExitStack
import json


def load_files():
    filenames = [
        'data/recipe.json',
        'data/technology.json',
        'data/mining-drill.json',
        'data/resource.json',
        'data/furnace.json',
        'data/assembling-machine.json',
        'data/rocket-silo.json',
    ]
    # data will be accessed through key names
    keys = [
        'recipes',
        'technology',
        'mining_drills',
        'resources',
        'furnaces',
        'assemblers',
        'rocket_silo',
    ]
    with ExitStack() as stack: 
        files = [
            stack.enter_context(open(filename))
            for filename in filenames
        ]
        data_dict = {keys[i]: json.load(x) for i,x in enumerate(files)}
    return data_dict
