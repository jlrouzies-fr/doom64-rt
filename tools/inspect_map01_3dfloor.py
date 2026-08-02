import re

t = open(r"G:\AI\Doom64-RT\tools\_map_cmp\MAP01_TEXTMAP.txt", encoding="utf-8").read()
for m in re.finditer(r"(?ms)^sector\s*\{(.*?)\}", t):
    b = m.group(1)
    if re.search(r"(?m)^\s*id\s*=\s*18\s*;", b):
        print("SECTOR id=18:")
        print(b[:900])
for m in re.finditer(r"(?ms)^linedef\s*\{(.*?)\}", t):
    b = m.group(1)
    if "special = 160" in b:
        print("--- linedef special 160 ---")
        print(b)
        sf = re.search(r"sidefront\s*=\s*(\d+)", b)
        if sf:
            idx = int(sf.group(1))
            for i, sm in enumerate(re.finditer(r"(?ms)^sidedef\s*\{(.*?)\}", t)):
                if i == idx:
                    print("SIDEFRONT:")
                    print(sm.group(1)[:500])
                    break
