from flask import Flask
from flask import request

from files import load_files
from sim import Sim

app = Flask(__name__)

data_dict = load_files()
sim = Sim(data_dict)

@app.route("/")
def root():
  time = f"{sim.game_time}\n" 
  endpoints = []
  for rule in app.url_map.iter_rules():
    endpoints.append(rule.endpoint)
  return time + '<br>'.join(endpoints) 

@app.route("/time")
def time():
  return f"{sim.game_time}"

@app.route("/clear", methods=["POST"])
def clear():
  sim.clear()
  return ('', 204)

@app.route("/spawn", methods=["POST"])
def spawn():
  item = request.args.get('item')
  amount = request.args.get('amount')
  sim.place_in_inventory(item, int(amount))
  return ('', 200)

@app.route("/inventory")
def inventory():
  return sim.current_items

@app.route("/research", methods=["POST"])
def research():
  technology = request.args.get('technology')
  res, msg = sim.research(technology)
  # TODO: do better result handling than this
  if res == 0:
    return (msg, 200)
  else:
    return (msg, 400)

@app.route("/place", methods=["POST"])
def place():
  machine = request.args.get('machine')
  item = request.args.get('item')
  amount = int(request.args.get('amount'))
  res, msg = sim.place_machine(machine, item, amount)
  if res == 0:
    return (msg, 200)
  else:
    return (msg, 400)