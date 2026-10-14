"""Perception -> decision -> action loop. Vision output changes the next step:
match -> mark vote 'vision-confirmed'; mismatch/unsure -> re-look denser at lower threshold;
still disagree -> fail closed: hold minutes approval and ask a human (Board Clerk rule).

Fail-closed guards (Pika #2381):
- zero-frame vote window never confirms (even if ayes_said == 0)
- empty / missing transcript votes never silently set minutes_approvable True
"""
import time
from . import vision


def should_confirm(obs, ayes_said):
    """True only when vision evidence is present and matches the transcript with no unsure seats."""
    if not obs or obs.get("frames", 0) <= 0:
        return False
    return obs.get("count") == ayes_said and not obs.get("unsure_seats")


def hold_message(motion, ayes_said, obs):
    if not obs or obs.get("frames", 0) <= 0:
        return (f"{motion}: vote window yielded zero frames "
                f"(transcript says {ayes_said} ayes). Minutes stay unapproved until a person confirms.")
    return (f"{motion}: transcript says {ayes_said} ayes, video shows {obs.get('count')} "
            f"(unsure seats {obs.get('unsure_seats')}). Minutes stay unapproved until a person confirms.")


def compute_minutes_approvable(results, votes):
    """Empty or missing votes must not pass `all([])` → True."""
    if votes is None or len(votes) == 0:
        return False
    if not results:
        return False
    return all(r.get("action") == "mark_vision_confirmed" for r in results)


def check_meeting(video, transcript, n_seats):
    votes = None if transcript is None else transcript.get("votes")
    if votes is None or len(votes) == 0:
        return {
            "results": [],
            "minutes_approvable": False,
            "trace": [{"decision": "hold", "why": "empty_or_missing_votes"}],
            "error": "empty_or_missing_votes",
        }

    base = vision.baseline(video)
    trace = []
    results = []
    for v in votes:
        plan = [dict(stride=5, thresh=35), dict(stride=1, thresh=25)]
        decision = None
        obs = {"count": 0, "unsure_seats": [], "frames": 0}
        for step, p in enumerate(plan):
            t = time.time()
            obs = vision.count_hands(video, base, n_seats, v["start"], v["end"], **p)
            trace.append({"motion": v["motion"], "step": step, "tool": "count_hands", "args": p,
                          "obs": obs, "ms": round((time.time() - t) * 1000)})
            if obs.get("frames", 0) <= 0:
                decision = {"action": "hold_approval_request_human",
                            "message": hold_message(v["motion"], v["ayes_said"], obs)}
                trace.append({"motion": v["motion"], "decision": "escalate",
                              "why": "zero_frames"})
                break
            if should_confirm(obs, v["ayes_said"]):
                decision = {"action": "mark_vision_confirmed"}
                break
            trace.append({"motion": v["motion"], "decision": "re-look" if step == 0 else "escalate",
                          "why": f"transcript {v['ayes_said']} vs seen {obs['count']}, unsure {obs['unsure_seats']}"})
        if not decision:
            decision = {"action": "hold_approval_request_human",
                        "message": hold_message(v["motion"], v["ayes_said"], obs)}
        results.append({"motion": v["motion"], "ayes_said": v["ayes_said"], "ayes_seen": obs["count"], **decision})
    return {
        "results": results,
        "minutes_approvable": compute_minutes_approvable(results, votes),
        "trace": trace,
    }
