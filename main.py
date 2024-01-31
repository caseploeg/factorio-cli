#!/usr/bin/env python3

"""Runs a CLI that interacts with the factorio simulation"""

from shell import *
from files import load_files
from sim import Sim

if __name__ == "__main__":
    data_dict = load_files()
    shell = FactorioShell(data_dict)
    shell.cmdloop()
