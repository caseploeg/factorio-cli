import requests

path = "http://localhost:5000/"


def get_game_time():
  r = requests.get(f'{path}time') 
  r.raise_for_status()
  return int(r.text)
  

def clear():
  r = requests.post(f'{path}clear')
  r.raise_for_status()


def spawn(item, amount):
  r = requests.post(f'{path}spawn?item={item}&amount={amount}')
  r.raise_for_status()


def get_inventory():
  r = requests.get(f'{path}inventory')
  r.raise_for_status()
  return r.json()
