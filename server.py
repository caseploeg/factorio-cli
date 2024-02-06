"""Flask server running a factorio simulation"""

from flask import Flask
from flask import request

from files import load_files
from sim import Sim
from shell import *
from craft import *

app = Flask(__name__)

data_dict = load_files()
sim = Sim(data_dict)

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

    return '<br>'.join(endpoints)

# GET REQUESTS
@app.route("/time", methods=["GET"])
def time():
  return f"{sim.game_time}"

@app.route("/cookbook", methods=["GET"])
def cookbook():
  return '\n'.join(sim.current_recipes)

@app.route("/techbook", methods=["GET"])
def techbook():
  return '\n'.join(sim.current_tech)

@app.route("/limits", methods=["GET"])
def limits():
  return '\n'.join(sim.limited_items)

@app.route("/machines", methods=["GET"])
def machines():
  return sim.machines()

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
def research():
  technology = request.args.get('technology')
  res, msg = sim.research(technology)
  # TODO: do better result handling than this
  if res == 0:
    return ('pog', 200)
  else:
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

@app.route("/next", methods=["POST"])
def next():
    minutes = int(request.args.get('minutes'))
    sim.next(minutes * 60)
    return '', 200

@app.route("/craft", methods=["POST"])
def craft():
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  res, msg = sim.craft(item, amount)
  if res == 0:
    return 'pog', 200
  else:
    return msg, 200


@app.route("/mine", methods=["POST"])
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


@app.shell_context_processor
def make_shell_context():
  return {'sim': sim}