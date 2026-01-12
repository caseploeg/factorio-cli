"""requests client library. glue between cli and server running the simulation"""

import requests
import json
import os

#path = "https://factorio-cli.replit.app/"
#path = "http://127.0.0.1:5000/"
path = os.getenv('SERVER_URL')

# Multiplayer session state
_player_id = None
_player_name = None

def _get_headers():
    """Get headers including player ID if available"""
    headers = {}
    if _player_id:
        headers['X-Player-ID'] = _player_id
    return headers

def _add_player_param(params):
    """Add player_id to request params as fallback"""
    if _player_id:
        params['player_id'] = _player_id
    return params

# MULTIPLAYER FUNCTIONS
def join(name='Player'):
    """Join the game and get a player ID"""
    global _player_id, _player_name
    r = requests.post(f'{path}join?name={name}')
    r.raise_for_status()
    data = r.json()
    _player_id = data['player_id']
    _player_name = data['name']
    return data

def leave():
    """Leave the game"""
    global _player_id, _player_name
    r = requests.post(f'{path}leave', headers=_get_headers())
    _player_id = None
    _player_name = None
    return r.text

def get_players():
    """Get list of connected players"""
    r = requests.get(f'{path}players')
    r.raise_for_status()
    return r.json()

def get_actions(since=None):
    """Get recent action log"""
    url = f'{path}actions'
    if since:
        url += f'?since={since}'
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def rename(new_name):
    """Rename the current player"""
    global _player_name
    r = requests.post(f'{path}rename?name={new_name}', headers=_get_headers())
    r.raise_for_status()
    if r.status_code == 200:
        data = r.json()
        _player_name = data['name']
        return data
    return None

def get_player_info():
    """Get current player info"""
    return {'player_id': _player_id, 'name': _player_name}

def is_connected():
    """Check if player is connected to multiplayer"""
    return _player_id is not None

# END MULTIPLAYER FUNCTIONS

# todo some obvious way to client source code to correponding server source code
# why does source code not have hyperlinks to more code
# put the endpoint as its formatted on the server here, so it's easy to cross reference
def get_game_time():
  # /time
  r = requests.get(f'{path}time', headers=_get_headers())
  r.raise_for_status()
  return float(r.text) 

def launch():
  r = requests.post(f'{path}launch', headers=_get_headers())
  return r.text

def clear():
  # /clear
  r = requests.post(f'{path}clear', headers=_get_headers())
  r.raise_for_status()

def spawn(item, amount):
  # /spawn
  r = requests.post(f'{path}spawn?item={item}&amount={amount}', headers=_get_headers())
  r.raise_for_status()

def get_inventory():
  # /inventory
  r = requests.get(f'{path}inventory')
  r.raise_for_status()
  return r.json()

def research(technology):
  # /research
  r = requests.post(f'{path}research?technology={technology}', headers=_get_headers())
  return r.text

def researchable(technology):
  # /researchable
  r = requests.post(f'{path}researchable?technology={technology}', headers=_get_headers())
  return r.text

def place(machine, item, amount):
  r = requests.post(f'{path}place?machine={machine}&item={item}&amount={amount}', headers=_get_headers())
  return r.text

def next(minutes):
  r = requests.post(f'{path}next?minutes={minutes}', headers=_get_headers())
  r.raise_for_status()

def craft(item, amount):
  r = requests.post(f'{path}craft?item={item}&amount={amount}', headers=_get_headers())
  return r.text

def craftable(item, amount):
  r = requests.get(f'{path}craftable?item={item}&amount={amount}')
  return r.text

def mine(resource, amount):
  r = requests.post(f'{path}mine?resource={resource}&amount={amount}', headers=_get_headers())
  return r.text

def cookbook():
  r = requests.get(f'{path}cookbook')
  return r.text

def limits():
  r = requests.get(f'{path}limits')
  return r.text

def suggest():
  r = requests.get(f'{path}suggest')
  return r.text

def production():
  r = requests.get(f'{path}production')
  return r.text

def limit(item, amount):
  r = requests.post(f'{path}limit?item={item}&amount={amount}', headers=_get_headers())
  return r.text

def prio(machine,item,old,new):
  r = requests.post(f'{path}prio?machine={machine}&item={item}&oldprio={old}&newprio={new}', headers=_get_headers())
  return r.text

def state():
  r = requests.get(f'{path}state')
  return r.text

def update(state):
  headers = {
      "Content-Type": "application/json"
  }
  r = requests.post(f'{path}update', data=json.dumps(state), headers=headers)
  return r.text