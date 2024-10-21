import json
import sys
from collections import defaultdict
import subprocess as sp

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

def get_instr_pos_map(instrs, proc):
    pos_map = defaultdict(set)
    for i, instr in enumerate(instrs):
        for var in proc(instr):
            pos_map[var].add(i)
    return pos_map

def const_instr_to_string(instr):
    """
    A Constant is an instruction that produces a literal value. It's op field must
    be the string "const". It has the dest, type, and value fields.
    """
    assert instr.get("op") == "const" and "dest" in instr and "type" in instr and "value" in instr
    dest = instr["dest"]
    dest_type = instr["type"]
    value = instr["value"]
    if dest_type == "bool": value = "true" if value else "false"
    return f"{dest}: {dest_type} = const {value};"

def value_op_instr_to_string(instr):
    """
    A Value Operation is an instruction that takes arguments, does some computation,
    and produces a value. Like a Constant, it has the dest and type fields, and also
    any of these three optional fields:

        * args, a list of strings. These are variable names defined elsewhere in the same function.
        * funcs, a list of strings. The name of any functions that this instruction references.
        * labels, a list of strings. The names of any labels within the current function that the instruction references.
    """
    assert instr.get("op") not in {"const", "jmp", "br", "ret"} and "dest" in instr and "type" in instr
    op = instr["op"]
    dest = instr["dest"]
    dest_type = instr["type"]
    args = " ".join(instr.get("args", []))
    funcs = " ".join([f"@{func}" for func in instr.get("funcs", [])])
    labels = " ".join([f".{label}" for label in instr.get("labels", [])])
    if op == "call": return f"{dest}: {dest_type} = call {funcs} {args};"
    else: return f"{dest}: {dest_type} = {op} {args};"

def effect_op_instr_to_string(instr):
    """
    An Effect Operation is like a Value Operation except that it does not produce a value.
    It has the optional args, funcs, and labels fields.
    """
    assert instr.get("op") in {"jmp", "br", "ret", "call"} and not "dest" in instr and not "type" in instr
    op = instr["op"]
    args = " ".join(instr.get("args", []))
    funcs = " ".join([f"@{func}" for func in instr.get("funcs", [])])
    labels = " ".join([f".{label}" for label in instr.get("labels", [])])
    if op == "br": return f"br {args} {labels};"
    elif op == "ret": return f"ret {args};"
    elif op == "jmp": return f"jmp {labels};"
    elif op == "call": return f"call {funcs} {args};"
    else: raise Exception()

def label_instr_to_string(instr):
    assert "label" in instr
    label = instr["label"]
    return f".{label}:"

def instr_to_string(instr):
    op = instr.get("op")
    args = " ".join(instr.get("args", []))
    if not op: return label_instr_to_string(instr)
    elif op == "print": return "\t" + f"print {args};"
    elif op == "const": return "\t" + const_instr_to_string(instr)
    elif "dest" in instr: return "\t" + value_op_instr_to_string(instr)
    else: return "\t" + effect_op_instr_to_string(instr)

def func_to_string(func):
    name = func["name"]
    instrs = func["instrs"]
    args = func.get("args")
    rtype = func.get("type")
    sig = f"@{name}"
    if args: sig += "".join(["(", ", ".join([f"{tok['name']}: {tok['type']}" for tok in args]), ")"])
    if rtype: sig += f": {rtype}"
    lines = [f"{sig} {{"] + [instr_to_string(instr) for instr in instrs] + ["}"]
    return "\n".join(lines)

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

def build_cfg(blocks):
    cfg_blocks = [] # put blocks without their initial labels here
    pos2name = [] # map block positions to names
    name2pos = dict() # map block names to positions
    name2succ = dict() # map block names to their successor block names
    for i, block in enumerate(blocks):
        if not "op" in block[0]:
            name = block[0]["label"] # label is name of block
            block = block[1:] # remove label
        else:
            name = f"bb{i+1}" # create generic block name if no label
        cfg_blocks.append(block)
        pos2name.append(name)
        name2pos[name] = i
    for i, block in enumerate(blocks):
        if block[-1].get("op") in {"jmp", "br"}: # jump and branch instructions have successor labels listed
            name2succ[pos2name[i]] = block[-1]["labels"]
        elif block[-1].get("op") == "ret" or i+1 == len(blocks): # return instruction has no successor
            name2succ[pos2name[i]] = []
        else:
            name2succ[pos2name[i]] = [pos2name[i+1]] # if not jump/branch/return then next block in list is successor
    return name2succ

def parse(bril_fname):
    cat_proc = sp.Popen(["cat", bril_fname], stdout=sp.PIPE)
    json_proc = sp.Popen(["bril2json"], stdin=cat_proc.stdout, stdout=sp.PIPE)
    prog = json.load(json_proc.stdout)
    return prog

if __name__ == "__main__":
    block_names = dict()
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        print(func_to_string(func))
        #  name2succ = build_cfg(list(form_blocks(func["instrs"])))
        #  print(f"digraph {func['name']} {{")
        #  for name in name2succ:
            #  print(f"    {name.replace('.', '')};")
        #  for name, succs in name2succ.items():
            #  for succ in succs:
                #  print(f"    {name.replace('.', '')} -> {succ.replace('.', '')};")
        #  print("}")
        #  break
