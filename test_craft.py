import pytest

from files import load_files
from sim import Sim

from collections import defaultdict

data_dict = load_files()
sim = Sim(data_dict)

# without iron plates, crafting the bmd should fail
def test_craft_bmd_no_plates():
    sim.clear()
    sim.mine('iron-ore', 20)
    res, msg = sim.craft('burner-mining-drill', 1)
    print(sim.current_items)
    assert res != 0

# with the exact items needed for the recipe,
# crafting the bmd should succeed
def test_craft_bmd_perfect_items():
    sim.clear()
    sim.current_items = defaultdict(int)
    sim.current_items['iron-plate'] = 3
    sim.current_items['iron-gear-wheel'] = 3
    sim.current_items['stone-furnace'] = 1
    print(sim.game_time)
    res, msg = sim.craft('burner-mining-drill', 1)
    assert res == 0
    assert sim.game_time == 2

# with the just iron plates and stone, 
# crafting the bmd should succeed
def test_craft_bmd_perfect_items():
    sim.clear()
    sim.current_items = defaultdict(int)
    sim.current_items['iron-plate'] = 9
    sim.current_items['stone-furnace'] = 1
    print(sim.game_time)
    res, msg = sim.craft('burner-mining-drill', 1)
    assert res == 0
    # 2.0 for bmd + 1.5 for the three igw needed
    assert sim.game_time == 3.5 
    assert sim.current_items['iron-plate'] == 0
