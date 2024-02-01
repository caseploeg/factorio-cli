import unittest
from types import SimpleNamespace


from utils import shopping_list
from files import load_files

class Test(unittest.TestCase):
    def test_shopping_list_level0(self):
        data_dict = load_files()
        data = SimpleNamespace(**data_dict) 
        request = {
            'iron-stick': {
                'name': 'iron-stick',
                'amount': 2 
            },
            'burner-mining-drill': {
                'name': 'burner-mining-drill',
                'amount': 1
            },
        }
        actual = shopping_list(data.recipes, request)
        expected = {
            'iron-plate': {
                'name': 'iron-plate',
                'amount': 4
            },
            'iron-gear-wheel': {
                "name" : "iron-gear-wheel",
                "amount" : 3
            },
            'stone-furnace': {
                "name" : "stone-furnace",
                "amount" : 1
            }
        }

        self.assertDictEqual(actual, expected)