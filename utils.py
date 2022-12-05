"""Stateless functions that can exist outside the simulation"""


# given a goal technology, return all the technologies required to unlock it,
# as well as all the science packs
def tech_needed(technology, goal):
    seen = set()
    packs = dict()
    preq = set() 
    preq.add(goal)
    while preq:
        t = preq.pop()
        if t not in seen:
            seen.add(t)
            amount = technology[t]['research_unit_count']  
            for ing in technology[t]['research_unit_ingredients']:
                name = ing['name'] 
                if name in packs:
                    packs[name]['amount'] += amount
                else:
                    packs[name] = {'name': name, 'amount': amount}
            for new_t in technology[t]['prerequisites']:
                preq.add(new_t)
    return seen, packs