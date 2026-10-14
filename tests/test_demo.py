import subprocess, json, sys
def test_cases():
    out = subprocess.run([sys.executable, "demo/run_demo.py"], capture_output=True, text=True, check=True).stdout
    s = json.loads(out)
    assert all(r[3] == "mark_vision_confirmed" for r in s["clean"])
    assert s["transcript_error"][0][3] == "hold_approval_request_human"
    assert s["occluded"][0][3] == "hold_approval_request_human"
    assert s["lighting_drift"][0][3] == "mark_vision_confirmed"
