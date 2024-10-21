import json
import sys
from collections import defaultdict, namedtuple

def gen_blocks(instrs):
    """
    Basic block generator
    """
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
    """
    Basic block name generator (`blocks` must be a list)
    """
    for i, block in enumerate(blocks):
        yield block[0].get("label", f"bb{i+1}")

def form_blocks(instrs):
    """
    Canonized block generator. Each block gets a label (notably,
    those that don't have one already) put at the front of the block,
    and a jump/ret instruction at the end if not already there (or
    br instruction). This way, we can literally shuffle the blocks
    (except for the entry block!) without altering the correctness.
    Can reassemble later and remove unnecessary jumps/rets.
    """
    blocks = list(gen_blocks(instrs))
    block_names = list(gen_block_names(blocks))
    for i, block in enumerate(blocks):
        name = block_names[i]
        if name != block[0].get("label"):
            block = [{"label" : name}] + block
        if i+1 != len(blocks) and block[-1].get("op") not in {"jmp", "br", "ret"}:
            block.append({"op" : "jmp", "labels" : [block_names[i+1]]})
        elif i+1 == len(blocks) and block[-1].get("op") not in {"ret", "jmp"}:
            block.append({"op" : "ret"})
        yield block

CFG = namedtuple("CFG", ["succs", "preds", "start", "block_map"])

def build_cfg(blocks):
    """
    Take canonized blocks as input and produce a control flow graph.
    """
    succs, preds, block_map, start = {}, defaultdict(set), {}, blocks[0][0].get("label")
    for block in blocks:
        block_map[block[0].get("label")] = block[1:] # remove label from block; use it as key to block in the `block_map`
    for name, block in block_map.items():
        succs[name] = block[-1].get("labels", []) # jmp/br conveniently use same labels field. this is all the successors
    for pred, tos in succs.items(): # construct predecessors map
        for succ in tos:
            preds[succ].add(pred)
    preds = {name : list(pr) for name, pr in preds.items()} # listify
    for name in block_map:
        if not name in preds:
            preds[name] = []
    if preds[start]:
        # need to add an entry block with no predecessors
        entry_block = [{"op" : "jmp", "labels" : [start]}]
        block_map["entry"] = entry_block
        succs["entry"] = [start]
        preds["entry"] = []
        start = "entry"
    return CFG(succs=succs, preds=preds, start=start, block_map=block_map)

def reassemble(cfg):
    stack = [cfg.start]
    visited = set()
    while stack:
        node = stack.pop()
        block = cfg.block_map[node]
        yield {"label" : node}
        for instr in block:
            yield instr
        visited.add(node)
        for succ in cfg.succs[node]:
            if not succ in visited:
                stack.append(succ)

def get_dominators(cfg):
    dom = {name : set(cfg.succs.keys()) for name in cfg.succs}
    worklist = [cfg.start]
    while worklist:
        y = worklist.pop()
        new = set(cfg.succs.keys()) if cfg.preds[y] else set()
        for x in cfg.preds[y]:
            new.intersection_update(dom[x])
        new.add(y)
        if new != dom[y]:
            dom[y] = new
            for z in cfg.succs[y]:
                worklist.append(z)
    return dom

def back_edges(cfg, dom):
    for B in cfg.preds:
        for A in cfg.preds[B]:
            if B in dom[A]:
                yield (A, B)

def find_natural_loops(cfg, dom):
    for N, H in back_edges(cfg, dom):
        visited = set()
        stack = [N]
        while stack:
            node = stack.pop()
            if node == H: break
            visited.add(node)
            for pred in cfg.preds[node]:
                stack.append(pred)
        yield H, list(visited)

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        cfg = build_cfg(list(form_blocks(func["instrs"])))
        func["instrs"] = list(reassemble(cfg))
    json.dump(prog, sys.stdout, indent=4)

#  prog = json.load(open("loop.json"))
#  func = prog["functions"][0]
#  cfg = build_cfg(list(form_blocks(func["instrs"])))
