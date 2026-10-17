import json
P="content/2027/fixed.json"
f=json.load(open(P))
for k,v in json.load(open("fixed_patch_2027.json")).items():
    f[k]=v
json.dump(f,open(P,"w"),ensure_ascii=False,indent=1)
print("updated keys only; other keys untouched")
