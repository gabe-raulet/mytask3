#!/bin/bash

bril2json < $1 | python cfg.py | python ../examples/to_ssa.py | python ../examples/lvn.py -p -c -f | python mytdce.py | python ../examples/from_ssa.py | python mytdce.py | bril2txt
