# events_await cluster — reflex 0.11.0a1 (#7673 / #7770 / #7782 / #7715 / #7752 / #7755 / #7754 / #7696 / #7412 / #7738)

## Status / resume here
- [x] awaitapp (await matrix + middleware + upload + on_load) written; dev + memory run done (`out/new_dev_mem.json`)
- [ ] awaitapp prod + memory, dev + redis, prod + redis
- [ ] legacyapp (decorator stacking + failure paths) on 0.11.0a1 and 0.10.1, memory + redis
- [ ] typing module (pyright + mypy, 0.11.0a1 vs 0.10.1)
- [ ] report written to `../reports/events_await.md`

All paths below are relative to `$SB/apps/events_await/` (scratch) = this directory (repo copy).
`$SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`. Ports: fe 3180-3199, be 8180-8199, redis 8199.

## How to rerun
```
scripts/srv.sh start new  $SB/apps/events_await/awaitapp dev  3180 8180 new_dev_mem          # dev, memory
scripts/srv.sh start new  $SB/apps/events_await/awaitapp prod 3181 3181 new_prod_mem         # prod, memory
scripts/srv.sh redis-start; scripts/srv.sh start new .../awaitapp dev 3182 8182 new_dev_redis redis
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_await.py http://localhost:3180/ logs/new_dev_mem.log out/new_dev_mem.json [case ...|special]
scripts/srv.sh stop new_dev_mem
```
`srv.sh` starts `reflex run` under `setsid`, waits for 200, and `stop` sends SIGINT to the group and reports how long shutdown took.
