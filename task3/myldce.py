import json
import sys
from collections import defaultdict, namedtuple

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

def form_blocks(instrs):
    """
    Basic blocks are maximal sequences of instructions that have the single-entry/single-exit property:
    Once the first instruction in the block is executed, the last one will be executed eventually
    in all execution paths.
    """
    block = []
    for instr in instrs:
        if "op" in instr: # An actual instruction
            block.append(instr)
            if instr["op"] in {"jmp", "br", "ret"}: # jmp, br, and ret all change the program flow, and therefore terminate basic blocks
                if block: yield block
                block = []
        else: # A label
            # labels are entry points to new blocks, via jmp/br isntructions.
            if block: yield block
            block = [instr] # next basic block starts with its label
    if block: yield block

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
