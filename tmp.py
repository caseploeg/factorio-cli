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
    