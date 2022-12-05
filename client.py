import requests

path = "http://localhost:5000/"

def get_game_time():
  r = requests.get(f'{path}time') 
  r.raise_for_status()
  return float(r.text) 

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

def research(technology):
  r = requests.post(f'{path}research?technology={technology}')
  return r.text

def place(machine, item, amount):
  r = requests.post(f'{path}place?machine={machine}&item={item}&amount={amount}')
  return r.text

def next(minutes):
  r = requests.post(f'{path}next?minutes={minutes}')
  r.raise_for_status()

def craft(item, amount):
  r = requests.post(f'{path}craft?item={item}&amount={amount}')
  return r.text

def mine(resource, amount):
  r = requests.post(f'{path}mine?resource={resource}&amount={amount}')
  return r.text

def cookbook():
  r = requests.get(f'{path}cookbook')
  return r.text

def machines():
  r = requests.get(f'{path}machines')
  return r.text

def suggest():
  r = requests.get(f'{path}suggest')
  return r.text

def production():
  r = requests.get(f'{path}production')
  return r.text

def limit(item, amount):
  r = requests.post(f'{path}limit?item={item}&amount={amount}')
  return r.text
