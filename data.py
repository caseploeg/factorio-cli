"""functions that operate on static game data"""
def craft_time(data, name, amount):
    return data.recipes[name]['energy'] / data.recipes[name]['main_product']['amount'] * amount