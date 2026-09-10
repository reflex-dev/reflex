| label | mode | rounds | exact | ev_per_s | p50_ms | p99_ms | worker_cpu_us_per_event | server_cpu_us_per_event | rss_mb | server_py | load_before |
|---|---|---|---|---|---|---|---|---|---|---|---|
| new311 | concurrent_20x100 | 3 | True | 1467.2 | 13.44 | 26.25 | 745.0 | 745.0 | 119.9 |  | 1.15/0.91/0.86 |
| new313 | concurrent_20x100 | 3 | True | 1798.1 | 10.97 | 17.58 | 615.0 | 615.0 | 122.2 |  | 1.15/0.81/1.21 |
| old311 | concurrent_20x100 | 3 | True | 1253.4 | 15.57 | 28.91 | 865.0 | 865.0 | 135.2 |  | 1.11/0.85/1.26 |
| old313 | concurrent_20x100 | 3 | True | 1486.2 | 13.4 | 20.17 | 735.0 | 735.0 | 137.4 |  | 0.97/0.92/1.29 |
| new311 | pipelined_2000 | 3 | True | 1111.3 | None | None | 985.0 | 985.0 | 119.0 |  | 1.22/0.91/0.95 |
| new313 | pipelined_2000 | 3 | True | 1154.5 | None | None | 955.0 | 955.0 | 122.0 |  | 1.15/0.81/1.43 |
| old311 | pipelined_2000 | 3 | True | 1026.5 | None | None | 1055.0 | 1055.0 | 134.3 |  | 1.11/0.86/1.26 |
| old313 | pipelined_2000 | 3 | True | 1018.7 | None | None | 1060.0 | 1060.0 | 136.9 |  | 0.98/0.92/1.29 |
| new311 | serial_2000 | 3 | True | 869.5 | 1.1 | 1.79 | 985.0 | 990.0 | 114.7 | 3.11.15 | 1.15/0.90/0.86 |
| new313 | serial_2000 | 3 | True | 949.1 | 1.01 | 1.6 | 935.0 | 935.0 | 117.0 | 3.13.12 | 1.17/0.79/1.21 |
| old311 | serial_2000 | 3 | True | 777.8 | 1.13 | 4.17 | 1040.0 | 1040.0 | 129.9 | 3.11.15 | 1.12/0.85/1.19 |
| old313 | serial_2000 | 3 | True | 957.4 | 1.01 | 1.51 | 980.0 | 980.0 | 132.1 | 3.13.12 | 0.97/0.74/1.32 |

py311 concurrent_20x100    new vs old: throughput +17.1%  p50 -13.7%  p99 -9.2%  worker CPU/event -13.9%  tree CPU/event -13.9%
py311 pipelined_2000       new vs old: throughput +8.3%  p50 n/a  p99 n/a  worker CPU/event -6.6%  tree CPU/event -6.6%
py311 serial_2000          new vs old: throughput +11.8%  p50 -2.7%  p99 -57.1%  worker CPU/event -5.3%  tree CPU/event -4.8%
py313 concurrent_20x100    new vs old: throughput +21.0%  p50 -18.1%  p99 -12.8%  worker CPU/event -16.3%  tree CPU/event -16.3%
py313 pipelined_2000       new vs old: throughput +13.3%  p50 n/a  p99 n/a  worker CPU/event -9.9%  tree CPU/event -9.9%
py313 serial_2000          new vs old: throughput -0.9%  p50 +0.0%  p99 +6.0%  worker CPU/event -4.6%  tree CPU/event -4.6%
