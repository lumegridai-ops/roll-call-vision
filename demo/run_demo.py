import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rcv import synth, agent
os.makedirs("demo/out", exist_ok=True)
cases = {
 "clean": dict(votes=[{"motion":"M1","ayes":[0,1,2,4],"start":2,"end":4},{"motion":"M2","ayes":[1,3,5,6,2],"start":5.5,"end":7.5}], said=[4,5]),
 "transcript_error": dict(votes=[{"motion":"M1","ayes":[0,1,2],"start":2,"end":4}], said=[4]),
 "occluded": dict(votes=[{"motion":"M1","ayes":[0,1,2,3],"start":2,"end":4}], said=[4], occlude=(1.8,4.2,3)),
 "lighting_drift": dict(votes=[{"motion":"M1","ayes":[0,2,4,6],"start":2,"end":4}], said=[4], drift=0.08),
}
summary = {}
for name, c in cases.items():
    p = f"demo/out/{name}.mp4"
    synth.render(p, votes=c["votes"], seed=1, occlude=c.get("occlude"), drift=c.get("drift",0))
    tr = {"votes":[{"motion":v["motion"],"start":v["start"],"end":v["end"],"ayes_said":s} for v,s in zip(c["votes"],c["said"])]}
    r = agent.check_meeting(p, tr, 7)
    json.dump(r, open(f"demo/out/{name}.json","w"), indent=1)
    summary[name] = [(x["motion"], x["ayes_said"], x["ayes_seen"], x["action"]) for x in r["results"]]
print(json.dumps(summary, indent=1))
