"""Minimal Flask server for testing - no shell dependency"""

from flask import Flask, request
from files import load_files
from sim import Sim

app = Flask(__name__)

data_dict = load_files()
sim = Sim(data_dict)

@app.route("/time", methods=["GET"])
def game_time():
    return f"{sim.game_time}"

@app.route("/state", methods=["GET"])
def state():
    return sim.serialize_state()

@app.route("/inventory", methods=["GET"])
def inventory():
    return sim.current_items

@app.route("/cookbook", methods=["GET"])
def cookbook():
    return '\n'.join(sim.current_recipes)

@app.route("/suggest", methods=["GET"])
def suggest():
    return '\n'.join(sim.all_researchable())

@app.route("/production", methods=["GET"])
def production():
    return str(sim.production())

@app.route("/clear", methods=["POST"])
def clear():
    sim.clear()
    return '', 204

@app.route("/mine", methods=["POST"])
def mine():
    resource = request.args.get('resource')
    amount = int(request.args.get('amount'))
    res, msg = sim.mine(resource, amount)
    return (msg or 'ok', 200) if res == 0 else (msg, 400)

@app.route("/craft", methods=["POST"])
def craft():
    item = request.args.get('item')
    amount = int(request.args.get('amount', 1))
    res, msg = sim.craft(item, amount)
    return ('ok', 200) if res == 0 else (msg, 400)

@app.route("/place", methods=["POST"])
def place():
    machine = request.args.get('machine')
    item = request.args.get('item')
    amount = int(request.args.get('amount', 1))
    res, msg = sim.place_machine(machine, item, amount)
    return ('ok', 200) if res == 0 else (msg, 400)

@app.route("/research", methods=["POST"])
def research():
    tech = request.args.get('technology')
    res, msg = sim.research(tech)
    return (msg or 'ok', 200)

@app.route("/next", methods=["POST"])
def next_turn():
    minutes = int(request.args.get('minutes', 1))
    sim.next(minutes * 60)
    return '', 200

@app.route("/limit", methods=["POST"])
def limit():
    item = request.args.get('item')
    amount = int(request.args.get('amount'))
    sim.set_limit(item, amount)
    return 'ok', 200

@app.route("/launch", methods=["POST"])
def launch():
    if sim.launch():
        return 'LIFT OFF!', 200
    return 'NOT ENOUGH ROCKET PARTS', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
