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
def factorio_shell():
    app = FactorioShellTester()

    # simulate running the start up scripts
    # todo: submit request for this to be added into the cmd2_ext_test code
    app.runcmds_plus_hooks(app._startup_commands)
    app._startup_commands.clear()
    

    app.fixture_setup()
    yield app
    app.fixture_teardown()


def test_startup(factorio_shell):
  factorio_shell.app_cmd("init")
  out = factorio_shell.app_cmd("alias list")
  print(out)
  assert isinstance(out, CommandResult)
  assert "init" in out.stdout


def test_starting_items(factorio_shell):
  out = factorio_shell.app_cmd("cookbook")
  recipes = out.stdout.split()
  assert len(recipes) == 28 




"""
def test_help(factorio_shell):
  out = factorio_shell.app_cmd("help")

  assert isinstance(out, CommandResult)
  print(out.stdout)
  print(out.data)
  
def test_cookbook(factorio_shell):
  out = factorio_shell.app_cmd("cookbook")
  print(out)
  assert False


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
