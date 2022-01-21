from shell import *
from calc import Sim

if __name__ == "__main__":
    sim = Sim()
    shell = FactorioShell(sim)
    shell.cmdloop()