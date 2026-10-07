
#### disk/memory

| case (primary var) | 0.8.26 dev disk | 0.9.0 dev disk | 0.9.12 dev disk | 0.10.0a1 dev disk | 0.10.0a2 dev disk | 0.10.0a2 dev disk (run 2) | 0.10.0a2 dev memory | 0.10.0a2 prod disk | 0.9.12 prod disk |
|---|---|---|---|---|---|---|---|---|---|
| direct (`status`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| async (`status`) | OK | - | STALE | STALE | STALE | STALE | - | STALE | - |
| chain (`log`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| gen (`status`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| agen (`status`) | OK | - | STALE | STALE | STALE | STALE | - | STALE | - |
| spinner (`spinner`) | OK | STALE | STALE | STALE | STALE | STALE | STALE | STALE | STALE |
| bg_inside (`status`) | OK | OK | OK | OK | OK | OK | OK | OK | OK |
| bg_two (`status`) | OK | - | OK | OK | OK | OK | - | OK | - |
| onload_initial (`load_note`) | OK | OK | OK | OK | OK | OK | OK | OK | OK |
| sup_split (`log`) | - | - | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` | `a:start,a:after-yield` |
| sup_same (`log`) | - | - | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | `a:start,a:after-yield,b:start,b:after-yield,b:end` | - |

#### redis

| case (primary var) | 0.8.26 dev redis | 0.9.0 dev redis | 0.9.12 dev redis | 0.10.0a1 dev redis | 0.10.0a2 dev redis | 0.10.0a2 prod redis (1 worker) | 0.10.0a2 prod redis (9 workers) | 0.9.12 prod redis (1 worker) | 0.10.0a2 dev redis + OPLOCK |
|---|---|---|---|---|---|---|---|---|---|
| direct (`status`) | OK | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | DROPPED | STALE |
| async (`status`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | - | - |
| chain (`log`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | DROPPED | STALE |
| gen (`status`) | OK | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | STALE |
| agen (`status`) | OK | - | DIVERGED | DIVERGED | DIVERGED | DIVERGED | - | - | - |
| spinner (`spinner`) | OK | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | STALE |
| bg_inside (`status`) | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | OK |
| bg_two (`status`) | DIVERGED | - | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | - | OK |
| onload_initial (`load_note`) | OK | - | DROPPED | DROPPED | DROPPED | DROPPED | - | DROPPED | OK |
| sup_split (`log`) | - | `a:start,a:after-yield,a:end` | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | DIVERGED | `a:start,a:after-yield` |
| sup_same (`log`) | - | - | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | `b:start,b:after-yield,b:end` | - | `a:start,a:after-yield,b:start,b:after-yield,b:end` |
