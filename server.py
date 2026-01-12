"""Flask server running a factorio simulation with multiplayer support"""

import json
import time
import uuid
import threading
from datetime import datetime

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, render_template, Response, stream_with_context

from files import load_files
from sim import Sim
from shell import *
from craft import *

app = Flask(__name__)
limiter = Limiter(
  get_remote_address,
  app=app,
  default_limits=["10000 per hour"],
  storage_uri="memory://",
)

request_history = []

# Multiplayer state
players = {}  # player_id -> {name, joined_at, last_active}
action_log = []  # List of {player_id, player_name, action, timestamp, details}
action_log_lock = threading.Lock()
players_lock = threading.Lock()

data_dict = load_files()
sim = Sim(data_dict)

### MULTIPLAYER HELPERS
from functools import wraps

def get_player_from_request():
    """Extract player ID from request header or query param"""
    player_id = request.headers.get('X-Player-ID') or request.args.get('player_id')
    return player_id

def get_player_name(player_id):
    """Get player name from player_id, or return 'Unknown' if not found"""
    with players_lock:
        if player_id and player_id in players:
            return players[player_id]['name']
    return 'Unknown'

def log_action(player_id, action, details=None):
    """Log a player action for multiplayer broadcast"""
    player_name = get_player_name(player_id)
    with action_log_lock:
        action_entry = {
            'player_id': player_id or 'anonymous',
            'player_name': player_name,
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'game_time': sim.game_time,
            'details': details or {}
        }
        action_log.append(action_entry)
        # Keep only last 100 actions
        if len(action_log) > 100:
            action_log.pop(0)

def update_player_activity(player_id):
    """Update last active timestamp for a player"""
    with players_lock:
        if player_id and player_id in players:
            players[player_id]['last_active'] = datetime.now().isoformat()

def record_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        player_id = get_player_from_request()
        update_player_activity(player_id)
        # record request details
        request_details = {
            'path': request.url,
            'player_id': player_id
        }
        request_history.append(request_details)
        return f(*args, **kwargs)
    return decorated_function

def record_action(action_name):
    """Decorator to record player actions with details"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            player_id = get_player_from_request()
            update_player_activity(player_id)
            result = f(*args, **kwargs)
            # Log the action with request params
            details = dict(request.args)
            details.pop('player_id', None)  # Remove player_id from details
            log_action(player_id, action_name, details)
            return result
        return decorated_function
    return decorator

### MULTIPLAYER HELPERS END


# ROOT
@app.route("/")
def root():
    # serve a directory GET endpoints at root
    base_url = request.url_root 
    endpoints = []
    for rule in app.url_map.iter_rules():
        if 'GET' in rule.methods and not rule.rule.startswith('/static'):
            endpoint_url = f"{base_url.rstrip('/')}{rule.rule}"
            endpoints.append(f'<a href="{endpoint_url}">{endpoint_url}</a>')
        

    def get_commit_hash():
      try:
          with open('commit_hash.txt', 'r') as file:
              return file.read().strip()  # Read the commit hash and remove any newline characters
      except FileNotFoundError:
          return "unknown"  # Return a default value if the file doesn't exist

    commit_hash = get_commit_hash()
    return render_template('frontend.html', commit_hash=commit_hash)

# MULTIPLAYER ENDPOINTS
@app.route("/join", methods=["POST"])
def join():
    """Register a new player and return their player ID"""
    name = request.args.get('name', 'Player')
    player_id = str(uuid.uuid4())[:8]  # Short unique ID

    with players_lock:
        players[player_id] = {
            'name': name,
            'joined_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat()
        }

    log_action(player_id, 'joined', {'name': name})
    return json.dumps({'player_id': player_id, 'name': name}), 200

@app.route("/leave", methods=["POST"])
def leave():
    """Remove a player from the game"""
    player_id = get_player_from_request()
    if player_id:
        with players_lock:
            if player_id in players:
                name = players[player_id]['name']
                del players[player_id]
                log_action(player_id, 'left', {'name': name})
                return 'goodbye', 200
    return 'player not found', 404

@app.route("/players", methods=["GET"])
def get_players():
    """Get list of connected players"""
    with players_lock:
        player_list = [
            {
                'player_id': pid,
                'name': info['name'],
                'joined_at': info['joined_at'],
                'last_active': info['last_active']
            }
            for pid, info in players.items()
        ]
    return json.dumps(player_list), 200

@app.route("/actions", methods=["GET"])
def get_actions():
    """Get recent action log"""
    since = request.args.get('since')  # Optional timestamp to get actions since
    with action_log_lock:
        if since:
            filtered = [a for a in action_log if a['timestamp'] > since]
            return json.dumps(filtered), 200
        return json.dumps(action_log[-20:]), 200  # Last 20 actions by default

@app.route("/actionfeed", methods=["GET"])
def action_feed():
    """SSE stream of player actions for real-time updates"""
    def generate():
        last_count = 0
        while True:
            with action_log_lock:
                current_count = len(action_log)
                if current_count > last_count:
                    new_actions = action_log[last_count:]
                    last_count = current_count
                    for action in new_actions:
                        yield f'data: {json.dumps(action)}\n\n'
            time.sleep(0.5)  # Poll every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/rename", methods=["POST"])
def rename_player():
    """Rename a player"""
    player_id = get_player_from_request()
    new_name = request.args.get('name')
    if not player_id or not new_name:
        return 'missing player_id or name', 400

    with players_lock:
        if player_id in players:
            old_name = players[player_id]['name']
            players[player_id]['name'] = new_name
            log_action(player_id, 'renamed', {'old_name': old_name, 'new_name': new_name})
            return json.dumps({'player_id': player_id, 'name': new_name}), 200
    return 'player not found', 404

# GET REQUESTS
@app.route("/time", methods=["GET"])
def game_time():
  return f"{sim.game_time}"

@app.route("/cookbook", methods=["GET"])
def cookbook():
  return '\n'.join(sim.current_recipes)

@app.route("/limits", methods=["GET"])
def limits():
  return '\n'.join(sim.limited_items)

@app.route("/suggest", methods=["GET"])
def suggest():
  return '\n'.join(sim.all_researchable())

@app.route("/production", methods=["GET"])
def production():
  return sim.production()

@app.route("/inventory")
def inventory():
  return sim.current_items

@app.route("/craftable", methods=["GET"])
def SERVERcraftable():
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  res, missing, available, not_enough_item = craftable(sim, item, amount)
  if res == 0:
    return 'pog', 200
  else:
    return 'not pog', 200

# export save file
@app.route("/state")
def state():
  return sim.serialize_state(), 200

# POST REQUESTS
@app.route("/clear", methods=["POST"])
def clear():
  sim.clear()
  return ('', 204)

# load save file
@app.route("/update", methods=["POST"])
def update():
  json_s = request.get_json() 
  sim.deserialize_state(json_s)
  return '', 200

@app.route("/spawn", methods=["POST"])
def spawn():
  item = request.args.get('item')
  amount = request.args.get('amount')
  sim.place_in_inventory(item, int(amount))
  return ('', 200)

@app.route("/research", methods=["POST"])
@record_action('research')
def research():
  technology = request.args.get('technology')
  res, msg = sim.research(technology)
  return (msg, 200)

@app.route("/researchable", methods=["POST"])
def researchable():
  technology = request.args.get('technology')
  res, msg = sim.researchable(technology)
  # TODO: do better result handling than this
  if res == 0:
    return ('pog', 200)
  else:
    return (msg, 400)

@app.route("/place", methods=["POST"])
@record_request
@record_action('place')
def place():
  machine = request.args.get('machine')
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  res, msg = sim.place_machine(machine, item, amount)
  if res == 0:
    #TODO: the sim function doesn't return anything on success
    return ('pog', 200)
  else:
    return (msg, 400)

@app.route("/prio", methods=["POST"])
def prio():
  machine = request.args.get('machine')
  item = request.args.get('item')
  oldprio = int(request.args.get('oldprio'))
  newprio = int(request.args.get('newprio'))
  sim.set_machine_prio(machine, item, oldprio, newprio)
  return 'prio set', 200

@app.route("/next", methods=["POST"])
@record_action('next')
def next():
    minutes = int(request.args.get('minutes'))
    sim.next(minutes * 60)
    return '', 200

@app.route("/craft", methods=["POST"])
@record_request
@record_action('craft')
def craft():
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  res, msg = sim.craft(item, amount)
  if res == 0:
    return 'pog', 200
  else:
    return msg, 200


@app.route("/mine", methods=["POST"])
@record_request
@record_action('mine')
def mine():
  resource = request.args.get('resource')
  amount = int(request.args.get('amount'))
  res, msg = sim.mine(resource, amount)
  if res == 0:
    return 'pog', 200
  else:
    return msg, 200

@app.route("/limit", methods=["POST"])
def limit():
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  #TODO: limits should do error handling
  sim.set_limit(item, amount)
  return 'pog', 200

@app.route("/launch", methods=["POST"])
@record_action('launch')
def launch():
  if sim.launch():
    return '3. 2. 1. LIFT OFF!!! GG', 200
  return 'NOT ENOUGH ROCKET PARTS', 200

@app.route("/ping", methods=["GET"])
def ping():
  def inventory_stream():
    while True:
        with players_lock:
            player_list = list(players.values())
        with action_log_lock:
            recent_actions = action_log[-10:]
        data = {
          'production': sim.production(),
          'state': sim.serialize_state(),
          'history': json.dumps(request_history),
          'players': player_list,
          'actions': recent_actions,
        }
        yield f'data: {json.dumps(data)}\n\n'
        time.sleep(3)

  return Response(stream_with_context(inventory_stream()), mimetype='text/event-stream')

@app.route("/stateping", methods=["GET"])
def stateping():
  def state_stream():
    while True: 
      yield f'data: {json.dumps(sim.serialize_state())}\n\n' 
      time.sleep(5)
  return Response(stream_with_context(state_stream()), mimetype='text/event-stream')


@app.route("/history", methods=["GET"])
def history():
  return str(request_history), 200

@app.shell_context_processor
def make_shell_context():
  return {'sim': sim}