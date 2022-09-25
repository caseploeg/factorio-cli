import cmd2_ext_test
import pytest
import cmd2

from cmd2 import CommandResult
from shell import *
from files import load_files
from sim import Sim

class FactorioShellTester(cmd2_ext_test.ExternalTestMixin, FactorioShell):
    def __init__(self, *args, **kwargs):
      data_dict = load_files()
      sim = Sim(data_dict)
      super().__init__(sim, *args, **kwargs)

@pytest.fixture
def s():
    app = FactorioShellTester()

    # simulate running the start up scripts
    # todo: submit request for this to be added into the cmd2_ext_test code
    app.runcmds_plus_hooks(app._startup_commands)
    app._startup_commands.clear()
    
    app.fixture_setup()
    yield app
    app.fixture_teardown()


def test_startup(s):
  s.app_cmd("init")
  out = s.app_cmd("alias list")
  print(out)
  assert isinstance(out, CommandResult)
  assert "init" in out.stdout


def test_starting_recipes(s):
  out = s.app_cmd("cookbook")
  recipes = out.stdout.split()
  assert len(recipes) == 28 

def test_next_no_machines(s):
  before = s.app_cmd("i").stdout
  s.app_cmd("next 5")
  after = s.app_cmd("i").stdout
  assert before == after


def test_one_drill(s):
  s.app_cmd("place bmd io")
  s.app_cmd("next 5")
  out = s.app_cmd("i")
  # 5 * 60 seconds * 0.25 mining speed
  assert '"iron-ore": 75' in out.stdout 

def test_craft(s):
  # craft should move time forwards
  # craft should use up the necessary materials
  s.app_cmd("place bmd stone")
  s.app_cmd("next 1")
  before_i = s.app_cmd("i").stdout
  out = s.app_cmd("craft sf")
  assert out.stderr == '' 
  after_i = s.app_cmd("i").stdout
  after_time = s.app_cmd("time").stdout
  assert float(after_time) == 60.5
  assert '"stone-furnace": 1' in before_i
  assert '"stone-furnace": 2' in after_i
  assert '"stone": 15' in before_i 
  assert '"stone": 10' in after_i
  
def test_craft2(s):
  s.app_cmd("place bmd stone")
  s.app_cmd("next 1")
  before_time = s.app_cmd("time").stdout
  before_i = s.app_cmd("i").stdout
  out = s.app_cmd("craft sf 4")
  assert out.stderr != '' 
  after_i = s.app_cmd("i").stdout
  after_time = s.app_cmd("time").stdout
  assert float(after_time) == float(before_time) 
  assert before_i == after_i

def test_mine(s):
  s.app_cmd("mine stone 20")
  s.app_cmd("mine iron-ore 20")
  s.app_cmd("mine copper-ore 10")
  time = s.app_cmd("time").stdout
  after_i = s.app_cmd("i").stdout
  assert '"iron-ore": 20' in after_i
  assert '"stone": 20' in after_i
  assert '"copper-ore": 10' in after_i
  assert 50 == float(time) 


def test_production(s):
  s.app_cmd("run scripts/test_setup.txt")
















"""
def test_help(factorio_shell):
  out = factorio_shell.app_cmd("help")

  assert isinstance(out, CommandResult)
  print(out.stdout)
  print(out.data)
  
def test_init(factorio_shell):
  out = factorio_shell.app_cmd("init")
  print(out)
  out = factorio_shell.app_cmd("inventory")
  print(out)
  assert False

def test_inventory(factorio_shell):
  out = factorio_shell.app_cmd("inventory")
  print(out.stdout)
  assert False

def test_alias_list(factorio_shell):
  out = factorio_shell.app_cmd("alias list")
  print(out)
  print(factorio_shell.app_cmd("@ scripts/startup.txt"))
  print(factorio_shell.app_cmd("init"))
  assert False

"""
