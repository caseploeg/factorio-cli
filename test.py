import unittest
from types import SimpleNamespace


from utils import shopping_list
from files import load_files

class Test(unittest.TestCase):
    def test_shopping_list_level0(self):
        data_dict = load_files()
        data = SimpleNamespace(**data_dict) 
        request = {
            'iron-stick': 1, 
            'burner-mining-drill': 1, 
        }
        actual = shopping_list(data.recipes, request)
        expected = {
            'iron-plate': 4, 
            'iron-gear-wheel': 3, 
            'stone-furnace': 1, 
        }

        self.assertDictEqual(actual, expected)