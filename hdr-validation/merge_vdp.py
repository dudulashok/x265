"""Fold vdp_results.txt ("<key> <frame> <Q_JOD>" lines) into results.json
as per-encode mean vdp_jod."""
import json, collections
res = json.load(open("results.json"))
acc = collections.defaultdict(list)
for line in open("vdp_results.txt"):
    parts = line.split()
    if len(parts) == 3:
        acc[parts[0]].append(float(parts[2]))
for key, vals in acc.items():
    if key in res:
        res[key]["vdp_jod"] = sum(vals) / len(vals)
        res[key]["vdp_n"] = len(vals)
json.dump(res, open("results.json", "w"), indent=1)
print({k: round(v["vdp_jod"], 3) for k, v in sorted(res.items()) if "vdp_jod" in v})
