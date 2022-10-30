from flask import Flask
from flask import request

from files import load_files
from sim import Sim

app = Flask(__name__)

data_dict = load_files()
sim = Sim(data_dict)

@app.route("/")
def hello_world():
  return f"{sim.game_time}"

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
