#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/apps/verify_dev_server_cli
export SB_PORTS=$SB/bin/ports.py
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L0_baseline_bun 3890 8890 $W/logs
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L1_npm1        3891 8891 $W/logs 1
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L2_plain       3892 8892 $W/logs
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L3_npm0        3893 8893 $W/logs 0
$W/scripts/lock_probe.sh $SB/envs/shared $W/dsc L4_plain_again 3894 8894 $W/logs
echo LOCKDONE
