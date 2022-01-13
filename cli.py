# take the args given detect aliases and convert them to proper names
def convert_aliases(args):
    aliases = {
        'i': 'inventory',
        'sf': 'stone-furnace',
        'bmd': 'burner-mining-drill',
        'emd': 'electric-mining-drill',
        'rp': 'automation-science-pack',
        'am1': 'assembling-machine-1',
    }
    converted_args = []
    for arg in args:
        if arg in aliases:
            converted_args.append(aliases[arg])
        else:
            convert_args.append(arg)
    return converted_args

