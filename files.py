from contextlib import ExitStack
import json


def load_files():
    filenames = [
        'recipe.json',
        'technology.json',
        'mining-drill.json',
        'resource.json',
        'furnace.json',
        'assembling-machine.json',
    ]
    # data will be referred to through key names
    keys = [
        'recipes',
        'technology',
        'mining-drills',
        'resources',
        'furnaces',
        'assemblers',
    ]
    with ExitStack() as stack: 
        files = [
            stack.enter_context(open(filename))
            for filename in filenames
        ]
        data_dict = {keys[i]: json.load(x) for i,x in enumerate(files)}
    return data_dict
