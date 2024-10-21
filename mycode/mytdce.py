import json
import sys
from mybril import *

def is_pure(instr):
    """
    deleting impure instructions is catastrophic, as it alters
    the control flow and/or changes program output
    """
    op = instr.get("op")
    if not op: return False
    return not op in {"load", "store", "print", "ret", "br", "jmp", "call"}

def tdce_it(instrs):
    instrs_update = []
    used = set(flatten([get_var_uses(instr) for instr in instrs])) # all 'used' variables in `instrs`
    for instr in instrs:
        if instr.get("dest") in used or not is_pure(instr):
            instrs_update.append(instr) # only append pure instructions or instructions that assign to used variables
    cont = len(instrs) != len(instrs_update)
    if cont: instrs[:] = instrs_update
    return cont

def tdce(instrs):
    iterate(instrs, tdce_it)

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        tdce(func["instrs"])
    json.dump(prog, sys.stdout, indent=4)
