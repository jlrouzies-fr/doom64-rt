import re
from collections import Counter

def parse(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    things = []
    for m in re.finditer(r"(?ms)^thing\s*\{(.*?)\}", t):
        body = m.group(1)
        d = dict(re.findall(r"(\w+)\s*=\s*([^;]+);", body))
        things.append({k: v.strip().strip('"') for k, v in d.items()})
    types = Counter(int(th.get("type", "0")) for th in things)
    specs = Counter()
    for m in re.finditer(r"(?ms)^linedef\s*\{(.*?)\}", t):
        body = m.group(1)
        sp = re.search(r"special\s*=\s*(\d+)", body)
        if sp:
            specs[int(sp.group(1))] += 1
    ss = Counter()
    for m in re.finditer(r"(?ms)^sector\s*\{(.*?)\}", t):
        body = m.group(1)
        sp = re.search(r"special\s*=\s*(\d+)", body)
        if sp:
            ss[int(sp.group(1))] += 1
    floors = []
    for m in re.finditer(r"(?ms)^linedef\s*\{(.*?)\}", t):
        body = m.group(1)
        if re.search(r"special\s*=\s*160", body):
            floors.append(body.strip())
    return types, specs, ss, floors

for label, p in [
    ("MAP01", r"G:\AI\Doom64-RT\tools\_map_cmp\MAP01_TEXTMAP.txt"),
    ("MAP02", r"G:\AI\Doom64-RT\tools\_map_cmp\MAP02_TEXTMAP.txt"),
]:
    types, specs, ss, floors = parse(p)
    print("====", label)
    print(" types:", sorted(types.items()))
    print(" linedef specials top:", sorted(specs.items(), key=lambda x: -x[1])[:25])
    print(" sector specials:", sorted(ss.items()))
    print(" 3dfloor count:", len(floors))
    for f in floors:
        print("  ---")
        print(f[:600])
