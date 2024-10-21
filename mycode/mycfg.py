import json
import sys
from collections import defaultdict, namedtuple
import random

def gen_blocks(instrs):
    block = []
    for instr in instrs:
        if "op" in instr:
            block.append(instr)
            if instr["op"] in {"jmp", "br", "ret"}:
                yield block
                block = []
        else:
            if block: yield block
            block = [instr]
    if block: yield block

def gen_block_names(blocks):
    for i, block in enumerate(blocks):
        yield block[0].get("label", f"bb{i+1}")

def form_blocks(instrs):
    blocks = list(gen_blocks(instrs))
    block_names = list(gen_block_names(blocks))
    for i, block in enumerate(blocks):
        name = block_names[i]
        if name != block[0].get("label"):
            block = [{"label" : name}] + block
        if i+1 != len(blocks) and block[-1].get("op") not in {"jmp", "br", "ret"}:
            block.append({"op" : "jmp", "labels" : [block_names[i+1]]})
        elif i+1 == len(blocks) and block[-1].get("op") != "ret":
            block.append({"op" : "ret"})
        yield block

def get_preds(cfg, block_map):
    preds = defaultdict(set)
    for pred, succs in cfg.items():
        for succ in succs:
            preds[succ].add(pred)
    preds = {name : list(pr) for name, pr in preds.items()}
    for name in block_map:
        if not name in preds:
            preds[name] = []
    return preds

def build_cfg(blocks):
    cfg = dict()
    block_map = dict()
    start = blocks[0][0].get("label")
    for block in blocks:
        block_map[block[0].get("label")] = block[1:]
    for name, block in block_map.items():
        cfg[name] = block[-1].get("labels", [])
    succs = cfg
    preds = get_preds(cfg, block_map)
    return succs, preds, start, block_map

def dominators(succs, preds, start, block_map):
    dom = {name : set(succs.keys()) for name in succs}
    worklist = [start]
    while worklist:
        y = worklist.pop()
        new = set(succs.keys()) if preds[y] else set()
        for x in preds[y]:
            new.intersection_update(dom[x])
        new.add(y)
        if new != dom[y]:
            dom[y] = new
            for z in succs[y]:
                worklist.append(z)
    return dom

def back_edges(dom, preds):
    for B in preds:
        for A in preds[B]:
            if B in dom[A]:
                yield (A, B)

def find_natural_loops(succs, preds, start, dom):
    for N, H in back_edges(dom, preds):
        visited = set()
        stack = [N]
        while stack:
            node = stack.pop()
            if node == H: break
            visited.add(node)
            for pred in preds[node]:
                stack.append(pred)
        yield H, list(visited)

def flatten(its):
    result = []
    for it in its: result += list(it)
    return result

#  if __name__ == "__main__":
    #  prog = json.load(sys.stdin)
    #  for func in prog["functions"]:
        #  func["instrs"] = flatten([block for block in form_blocks(func["instrs"])])
    #  json.dump(prog, sys.stdout, indent=4)

prog = json.load(open("check-primes.json", "r"))
func = prog["functions"][1]
instrs = func["instrs"]
blocks = list(form_blocks(instrs))
succs, preds, start, block_map = build_cfg(blocks)
dom = dominators(succs, preds, start, block_map)

for H, rest in find_natural_loops(succs, preds, start, dom):
    print(f"{H}: {rest}")

