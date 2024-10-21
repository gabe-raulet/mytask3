import sys
import json
from collections import defaultdict, namedtuple

class CFG(object):

    def __init__(self, succs, preds, block_map, entry):
        self.succs = succs
        self.preds = preds
        self.block_map = block_map
        self.entry = entry

    def stream_cfg(self):
        visited = set()
        stack = [self.entry]
        while stack:
            node = stack.pop()
            block = [{"label": node}] + self.block_map[node]
            stack += [n for n in block[-1].get("labels", []) if not n in visited]
            if block[-1].get("op") == "jmp":
                if block[-1]["labels"][0] not in visited:
                    block = block[:-1]
            visited.add(node)
            for instr in block:
                yield instr

    #  def stream_cfg(self):
        #  blocks = []
        #  for label, cfg_block in self.block_map.items():
            #  block = [{"label": label}] + cfg_block.instrs
            #  blocks.append((cfg_block.pos, block))
        #  blocks = [block for pos, block in sorted(blocks) if pos >= 0]
        #  for i, block in enumerate(blocks[:-1]):
            #  if block[-1].get("op") == "jmp" and blocks[i+1][0]["label"] == block[-1].get("labels")[0]:
                #  block = block[:-1]
            #  for instr in block:
                #  yield instr
        #  for instr in blocks[-1][:-1]:
            #  yield instr
        #  last_instr = blocks[-1][-1]
        #  if last_instr.get("op") != "ret":
            #  yield last_instr
        #  elif last_instr.get("args"):
            #  yield last_instr

    def dfs(self, start):
        visited, stack = set(), [start]
        while stack:
            cur = stack.pop()
            yield cur
            visited.add(cur)
            for succ in self.succs[cur]:
                if not succ in visited:
                    stack.append(succ)

    def init_doms(self):
        names = set(self.block_map.keys())
        dom = {name : names for name in names}
        worklist = [self.entry]
        while worklist:
            y = worklist.pop()
            new = names if self.preds[y] else set()
            for x in self.preds[y]:
                new.intersection_update(dom[x])
            new.add(y)
            if new != dom[y]:
                dom[y] = new
                for z in self.succs[y]:
                    worklist.append(z)
        return dom

    def find_natural_loops(self):
        natloops = dict()
        dom = self.init_doms()
        for H in self.preds:
            for N in self.preds[H]:
                if H in dom[N]:
                    visited = set()
                    stack = [N]
                    while stack:
                        node = stack.pop()
                        if node == H: break
                        visited.add(node)
                        for pred in self.preds[node]:
                            stack.append(pred)
                    natloops[H] = list(visited)
        return natloops

    def hoist_consts(self, header, nodes):
        const_defs = []
        for node in nodes:
            block_update = []
            for instr in self.block_map[node]:
                if instr.get("op") == "const":
                    const_defs.append(instr)
                else:
                    block_update.append(instr)
            self.block_map[node] = block_update

        if const_defs:
            pre_header = f"pre.{header}"
            instrs = const_defs + [{"op": "jmp", "labels": [header]}]
            self.block_map[pre_header] = instrs
            self.succs[pre_header] = [header]
            self.preds[pre_header] = self.preds[header][:]
            self.preds[header] = [pre_header]
            #  for pred in self.preds[pre_header]:
                #  block = self.block_map[pred]
                #  labels = block[-1].get("labels")
                #  if labels:
                    #  for i, label in enumerate(labels):
                        #  if label == header and not label in nodes:
                            #  labels[i] = pre_header
                    #  block[-1]["labels"] = labels
                #  self.block_map[pred] = block

    @classmethod
    def from_instrs(cls, instrs):
        cfg_blocks = cls.init_cfg_blocks(cls.init_basic_blocks(instrs))
        block_map = cls.init_block_map(cfg_blocks)
        succs = cls.init_succs_map(block_map)
        preds = cls.init_preds_map(block_map)
        entry = cfg_blocks[0][0]["label"]
        if preds[entry]: # add a unique entry if necessary
            succs["unique.entry"] = [entry]
            preds["unique.entry"] = []
            block_map["unique.entry"] = [{"op" : "jmp", "labels" : [entry]}]
            entry = "unique.entry"
        return cls(succs, preds, block_map, entry)

    @staticmethod
    def init_block_map(cfg_blocks):
        return {block[0]["label"] : block[1:] for block in cfg_blocks}

    @staticmethod
    def init_succs_map(block_map):
        succs = dict()
        for label, block in block_map.items():
            succs[label] = block[-1].get("labels", [])
        return succs

    @staticmethod
    def init_preds_map(block_map):
        preds = {label : [] for label in block_map}
        for label, block in block_map.items():
            for succ in block[-1].get("labels", []):
                preds[succ].append(label)
        return preds

    @staticmethod
    def init_cfg_blocks(blocks):
        for i, block in enumerate(blocks):
            if i+1 != len(blocks) and block[-1].get("op") not in {"jmp", "br", "ret"}:
                block.append({"op": "jmp", "labels": [blocks[i+1][0]["label"]]})
            elif i+1 == len(blocks) and block[-1].get("op") not in {"jmp", "ret"}:
                block.append({"op": "ret"})
            blocks[i] = block
        return blocks


    @staticmethod
    def init_basic_blocks(instrs):
        """
        Takes list of instructions as input and produces list of maximal basic blocks
        with label prepended (if not already present) to each block.
        """
        blocks, block = [], []
        for instr in instrs:
            if "op" in instr:
                block.append(instr)
                if instr["op"] in {"jmp", "br", "ret"}:
                    blocks.append(block)
                    block = []
            else:
                assert "label" in instr
                if block: blocks.append(block)
                block = [instr]
        if block: blocks.append(block)

        for i, block in enumerate(blocks):
            if not "label" in block[0]:
                blocks[i] = [{"label": f"bb{i+1}"}] + block

        return blocks

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    hoist = '-p' in sys.argv
    for func in prog["functions"]:
        cfg = CFG.from_instrs(func["instrs"])
        if hoist:
            natloops = cfg.find_natural_loops()
            for header, nodes in natloops.items():
                cfg.hoist_consts(header, nodes)
        func["instrs"] = list(cfg.stream_cfg())
    json.dump(prog, sys.stdout, indent=4)
