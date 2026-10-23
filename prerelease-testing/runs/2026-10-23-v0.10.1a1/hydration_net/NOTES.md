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

| leg | control (must fail) | new (0.10.1a1) | verdict |
|---|---|---|---|
| probe `cs_storage_default_probe.py` | — | `assign_*` #7516 TypeError, `field_plain`/`field_none` ordinary, `field_storage` LocalStorage `box_pref_dark` | = 0.10.0 |
| HYD-01 / F-002 `run_f002.sh <v> prod ... 3140 3140` | 0.10.0a1: fresh profile's localStorage holds `cu_ls, wt_ls, wu_ls, wu_sync` (+ SS, cookies) after the first load; v2 returning visitor keeps `wu-light` (stale default) | fresh x2 and same-build returning: localStorage only `theme=system`; v2 returning + fresh show `*-dark-v2` / `wu-sync-v2`; sync tabs converge on `sync-from-tabA` | **fixed, unchanged vs 0.10.0** |
| HYD-02 / F-003 `run_cv.sh <v> dev ... 3142 8142 <vars> PYTHONHASHSEED=4` | 0.10.0a1 a/b/g: `reload [l='bad']` (browser keeps the bad token through reload/probe/noop) | `CVSTORE MATCHES cvstore_dev.summary.txt` (a–j, 0-byte diff vs the 0.10.0 expected file; b keeps N-016) | **fixed, unchanged** |
| HYD-08 / A3-11 `run_storm.sh <v> dev 3 3142 8142 S 6` | 0.10.0a3 Part S: **0/3 storms on this box** (README recorded 3/4 on a quieter machine — Part S is timing dependent; see the Part R control below) | 0/3 storms, 59–65 frames, 0 in the quiet window, all 7 tabs + localStorage `s5` | pass (control via Part R) |
| HYD-09 / A3-12 `run_stamp2.sh <v> dev 3142 8142 2 1 6` | 0.10.0a3: run 1 **storm** (1,108,630 frames, 306k/299k per 5 s window, tabs split `36382b-1`/`2a91e1-1`); run 2 quiet (timing) | (below) | |

