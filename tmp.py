#!/usr/bin/env python3
def ratio(self, item):
    """Find the optimal production ratio for assembling an item"""
    sh = shopping_list(self.data.recipes, convert_to_sh({item: 1}), 0)
    r_list = []
    for k, v in sh.items():
        r_list.append(int(self.craft_time(k, v['amount']) * 10))
    denom = math.gcd(*r_list)
    for k, v in sh.items():
        sh[k]['amount'] = self.craft_time(k, v['amount']) * 10 // denom
    return sh

if __name__ == "__main__":
    from files import load_files
    from types import SimpleNamespace
    data_dict = load_files()
    data = SimpleNamespace(**data_dict)
    cache = dict()
    for m in data.mining_drills:
        cache[m] = 0
    for a in data.assemblers:
        cache[a] = 1
    for f in data.furnaces:
        cache[f] = 2
    import json
    print(json.dumps(cache))

