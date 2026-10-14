"""Bigger synthetic eval: 32 meetings, 5-9 seats, 2-3 votes each, with injected transcript errors,
occlusion, lighting drift and brief raises. Scores (a) vision count accuracy vs ground truth and
(b) agent decision correctness: confirm iff transcript == truth and no known hard-case exemption;
otherwise hold for a human.

Half-raise exemption covers every motion whose aye set includes a half-raised seat (not only M1).
Transcript-error fixtures mix overcount, undercount, large miss, and zero-vs-nonzero shapes.
"""
import json, os, sys, random, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rcv import synth, agent


def inject_txerr(truth_count, n_seats, meeting_id):
    """Mixed transcript-error shapes (not only +1 overcounts)."""
    shape = (meeting_id // 8) % 4  # txerr meetings are 4,12,20,28 → shapes 0..3
    s = truth_count
    if shape == 0:  # overcount by 1
        return s + 1 if s < n_seats else s - 1
    if shape == 1:  # undercount by 1
        return max(0, s - 1)
    if shape == 2:  # larger miss (±2)
        return min(n_seats, s + 2) if s + 2 <= n_seats else max(0, s - 2)
    # shape 3: zero vs nonzero (or invent one if truth is already 0)
    return 0 if s > 0 else min(n_seats, 1)


def should_confirm(said, truth, vote, occ, half):
    """Expected confirm: transcript matches truth and vote is not under a known hard-case exemption."""
    if said != truth:
        return False
    # Occlusion blob is timed to the first vote window only.
    if occ and vote["motion"] == "M1":
        return False
    # Half-raised seats half-raise whenever they are in the aye set (any motion).
    if half and any(a in half for a in vote["ayes"]):
        return False
    return True


if __name__ == "__main__":
    random.seed(26); os.makedirs("eval/out", exist_ok=True)
    rows = []; t0 = time.time()
    for m in range(32):
        n = random.randint(5, 9); votes = []; t = 2.0; said = []; truth = []
        CASES = ["none", "occlude", "drift", "brief", "txerr", "jitter", "half_raise", "none"]
        hard = CASES[m % len(CASES)]
        for k in range(random.randint(2, 3)):
            ayes = sorted(random.sample(range(n), random.randint(1, n)))
            dur = 0.8 if hard == "brief" and k == 0 else 2.0
            votes.append({"motion": f"M{k+1}", "ayes": ayes, "start": t, "end": t + dur}); t += dur + 1.5
            truth.append(len(ayes)); s = len(ayes)
            if hard == "txerr" and k == 0:
                s = inject_txerr(s, n, m)
            said.append(s)
        occ = None; half = ()
        if hard == "half_raise": half = (votes[0]["ayes"][0],)
        if hard == "occlude":
            v0 = votes[0]; occ = (v0["start"] - .2, v0["end"] + .2, v0["ayes"][0])
        p = f"eval/out/m{m:02d}.mp4"
        synth.render(p, n_seats=n, votes=votes, seed=m, occlude=occ, drift=0.08 if hard == "drift" else 0, jitter=6 if hard == "jitter" else 0, half=half)
        tr = {"votes": [{"motion": v["motion"], "start": v["start"], "end": v["end"], "ayes_said": s} for v, s in zip(votes, said)]}
        r = agent.check_meeting(p, tr, n)
        for v, s, tru, res in zip(votes, said, truth, r["results"]):
            expect_confirm = should_confirm(s, tru, v, occ, half)
            held = res["action"] != "mark_vision_confirmed"
            rows.append({"meeting": m, "seats": n, "case": hard, "motion": v["motion"], "truth": tru, "said": s,
                         "seen": res["ayes_seen"], "action": res["action"],
                         "count_ok": res["ayes_seen"] == tru,
                         "decision_ok": (res["action"] == "mark_vision_confirmed") == expect_confirm,
                         "unsafe_confirm": res["action"] == "mark_vision_confirmed" and s != tru,
                         # False hold = held while transcript matched ground truth (said == truth).
                         "false_hold": held and s == tru,
                         # Unexpected false hold = held when scorer (with correct exemptions) expected confirm.
                         "false_hold_unexpected": held and expect_confirm})
        os.remove(p)


    def rate(k, sub=rows): return f"{sum(r[k] for r in sub)}/{len(sub)}"
    summ = {"votes": len(rows), "count_accuracy": rate("count_ok"), "decision_accuracy": rate("decision_ok"),
            "unsafe_confirms": sum(r["unsafe_confirm"] for r in rows),
            "false_holds_definition": "hold while said == truth (transcript matches ground truth)",
            "false_holds": sum(r["false_hold"] for r in rows),
            "false_holds_unexpected_after_exemptions": sum(r["false_hold_unexpected"] for r in rows),
            "exemptions": "occlude on M1 only (blob timed to first vote); half_raise on any motion whose aye set includes a half-raised seat",
            "by_case": {}, "seconds": round(time.time() - t0, 1)}
    for c in sorted({r["case"] for r in rows}):
        sub = [r for r in rows if r["case"] == c]
        summ["by_case"][c] = {"count": rate("count_ok", sub), "decision": rate("decision_ok", sub),
                              "false_holds": sum(r["false_hold"] for r in sub)}
    json.dump({"summary": summ, "rows": rows}, open("eval/results.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))
