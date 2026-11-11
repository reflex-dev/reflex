import json, sys
for l in open(sys.argv[1]):
    d = json.loads(l)
    if "stop" in d:
        print(d["label"], d["stop"], "log_err", d["log_err"]); continue
    if "error" in d:
        print(d); continue
    print(f'{d["label"]:<52} ok {d["ok"]}/{d["of"]} to={d["timeouts"]} p50={d["p50"]} p99={d["p99"]} max={d["max"]} api50={d["api_p50"]} api99={d["api_p99"]} el={d["elapsed_max"]} bad={d["bad"][:1]} exc={d["exceptions"][:1]}')
