`EnvVar` now supports `timedelta`. A bare number is read as seconds, and `ms`, `s`, `m`, `h` and `d` suffixes are understood, so `TIMEOUT=30`, `TIMEOUT=30s` and `TIMEOUT=5m` are all valid.
