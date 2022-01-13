# take the args given detect aliases and convert them to proper names
def convert_aliases(args):
    aliases = {
        'i': 'inventory',
        'm': 'machines',
        'sf': 'stone-furnace',
        'bmd': 'burner-mining-drill',
        'emd': 'electric-mining-drill',
        'rp': 'automation-science-pack',
        'am1': 'assembling-machine-1',
        'igw': 'iron-gear-wheel',
        'ip': 'iron-plate',
        'cp': 'copper-plate',
        'gc': 'electronic-circuit'
    }
    converted_args = []
    for arg in args:
        if arg in aliases:
            converted_args.append(aliases[arg])
        else:
            converted_args.append(arg)
    return converted_args

