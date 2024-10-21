import json
import sys
#  from mybril import *

def flatten(iters):
    result = []
    for it in iters: result += list(it)
    return result

def iterate(obj, f):
    while f(obj): pass

def get_var_uses(instr):
    for ref in instr.get("args", []): yield ref

def get_var_defs(instr):
    dest = instr.get("dest")
    if dest: yield dest

def get_var_refs(instr):
    for ref in get_var_uses(instr): yield ref
    for ref in get_var_defs(instr): yield ref

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

def kill_undefined_it(instrs):
    kill = set(["__undefined"])
    for instr in instrs:
        if instr.get("op") == "id" and instr["args"][0] in kill:
            kill.add(instr.get("dest"))
    instrs_update = [instr for instr in instrs if instr.get("dest") not in kill]
    cont = len(instrs) != len(instrs_update)
    if cont: instrs[:] = instrs_update
    return cont

def kill_undefined(instrs):
    iterate(instrs, kill_undefined_it)

#  def triv_id_chain(instrs):
    #  instrs_update = []
    #  for i, instr in enumerate(instrs[:-1]):
        #  if instrs[i+1].get("op") == "id" and instrs[i+1].get("args")[0] == instr.get("dest"):
            #  instr[""]

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        tdce(func["instrs"])
        kill_undefined(func["instrs"])
    json.dump(prog, sys.stdout, indent=4)
