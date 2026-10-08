#!/bin/bash
A=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a311
{ $A/stamp.sh fix dev 6 6; $A/stamp.sh fix dev 6 3; $A/stamp.sh fix prod 4 6; $A/storm.sh fix dev 5 6; $A/storm.sh fix prod 3 6; } 2>&1 | grep -E '^fix|^S:|^---' | cut -c1-600 > $A/out/final_matrix.txt
