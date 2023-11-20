"""Code related to crafting items"""

# data dependent, not state dependent
def is_crafting_recipe(sim, item):
    return sim.data.recipes[item]['category'] == 'crafting'