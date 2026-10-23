# hydration_net — reflex 0.10.1a1 pre-release pass (2026-10-23)

Item: HYD-01/02/08/09 re-verification, #7360 credential exposure, C21, and the hunt over #7614 (client_ip /
trusted_proxy_hops), #7588 / #7602 (repeated and non-UTF-8 headers), #7551 / #7605 (oversized hydrate, backoff),
#7545 / #7568 / #7603 / #7572 (storage sync / cached dependents / storage annotations / override dependents),
#7407 (global client_state late readers).

Everything ran from `$SB/apps/hydration_net/` with PUBLISHED packages only:
- `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`
- venvs: `new` = reflex 0.10.1a1 / reflex-base 0.10.1a1 (granian 2.8.5), `prev` = 0.10.0, `driver` = playwright 1.64.1 +
  websockets 17.3 + httpx; positive controls built here from PyPI: `hydration_net-0.10.0a1` (F-002/F-003),
  `hydration_net-0.10.0a3` (A3-11/A3-12 storms), `hydration_net-0.10.0a4` (#7360 leaks).
  `cd $SB && uv --no-config venv --python 3.12 $SB/envs/hydration_net-<v> && uv --no-config pip install --python
  $SB/envs/hydration_net-<v>/bin/python --prerelease=allow "reflex[db]==<v>" "reflex-base==<v>" 'pydantic<2.15'`
- fixture copy: `cp -r prerelease-testing/fixtures/hydration $SB/apps/hydration_net/src` (`F=$SB/apps/hydration_net/src`)
- my app + probes (copied here): `hnet/` (app), `probes/` (`hnet_drive.py`, `ws_probe.py`, `xff_proxy.py`,
  `close_proxy.py`), `run_hnet.sh` (how each leg was started).
- ports 3140-3159 / 8140-8159 only; one app server set at a time.

## 1. Re-verification with `run_area.sh quick` (positive controls first)

```
export SB=... WORK=$SB/apps/hydration_net NEW=new PREV=prev \
  CTRL_F002=hydration_net-0.10.0a1 CTRL_STORM=hydration_net-0.10.0a3 CTRL_RTR=hydration_net-0.10.0a4
$WORK/src/scripts/run_area.sh quick > $WORK/area_quick.txt 2>&1     # trimmed copy: area_quick.txt
```

(results filled in below as the legs complete)

