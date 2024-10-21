import json
import sys
from collections import defaultdict, namedtuple
from mybril import *

Instruction = namedtuple("Instruction", ["pos", "uses", "dest", "instr"])

def parse_instructions(instrs):
    for i, instr in enumerate(instrs):
        inst = Instruction(pos=i, uses=list(get_var_uses(instr)), dest=instr.get("dest"), instr=instr)
        yield inst

def ldce_it(block):
    unused = defaultdict(Instruction)
    toremove = set()
    for inst in parse_instructions(block):
        for use in inst.uses:
            if use in unused:
                unused.pop(use)
        if inst.dest:
            if inst.dest in unused:
                toremove.add(unused[inst.dest].pos)
            unused[inst.dest] = inst
    block_update = [instr for i, instr in enumerate(block) if not i in toremove]
    cont = len(block) != len(block_update)
    if cont: block[:] = block_update
    return cont

def ldce(instrs):
    instrs_update = []
    for block in form_blocks(instrs):
        iterate(block, ldce_it)
        instrs_update += block
    instrs[:] = instrs_update

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        ldce(func["instrs"])
    json.dump(prog, sys.stdout, indent=4)
