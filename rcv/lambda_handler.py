"""AWS Lambda entry (zip or container). Works for direct invoke AND Lambda Function URL.
Request JSON (direct event, or Function URL body):
  {"demo": "clean"|"transcript_error"|"occluded"|"lighting_drift"}   -> bundled synthetic clip, no S3
  {"s3_video": "s3://bucket/key", "transcript": {...}, "seats": 7}   -> video from S3
Agent trace is printed to CloudWatch Logs."""
import base64, json, os, tempfile, time
from .agent import check_meeting

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "demo_clips")
DEMO_TRANSCRIPTS = {
    "clean": {"votes": [{"motion": "M1", "start": 2, "end": 4, "ayes_said": 4}, {"motion": "M2", "start": 5.5, "end": 7.5, "ayes_said": 5}]},
    "transcript_error": {"votes": [{"motion": "M1", "start": 2, "end": 4, "ayes_said": 4}]},
    "occluded": {"votes": [{"motion": "M1", "start": 2, "end": 4, "ayes_said": 4}]},
    "lighting_drift": {"votes": [{"motion": "M1", "start": 2, "end": 4, "ayes_said": 4}]},
}

def _req(event):
    if isinstance(event, dict) and "requestContext" in event and "http" in event.get("requestContext", {}):
        body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode()
        return json.loads(body), True
    return event, False

def _resp(obj, url, code=200):
    if not url:
        return obj
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(obj)}

def handler(event, context=None):
    t0 = time.time()
    try:
        req, url = _req(event)
    except Exception:
        return _resp({"error": "body must be JSON"}, True, 400)
    try:
        if req.get("demo"):
            name = req["demo"]
            if name not in DEMO_TRANSCRIPTS:
                return _resp({"error": "unknown demo", "choices": sorted(DEMO_TRANSCRIPTS)}, url, 400)
            p, tr, seats = os.path.join(DEMO_DIR, name + ".mp4"), DEMO_TRANSCRIPTS[name], 7
        elif req.get("s3_video", "").startswith("s3://"):
            import boto3
            b, k = req["s3_video"][5:].split("/", 1)
            p = os.path.join(tempfile.gettempdir(), "v.mp4")
            boto3.client("s3").download_file(b, k, p)
            tr, seats = req["transcript"], req.get("seats", 7)
        else:
            return _resp({"error": "send {\"demo\": \"clean\"} or {\"s3_video\": \"s3://...\", \"transcript\": {...}}"}, url, 400)
        r = check_meeting(p, tr, seats)
    except Exception as e:  # fail closed
        print(json.dumps({"error": repr(e)}))
        return _resp({"error": "check failed", "minutes_approvable": False}, url, 500)
    print(json.dumps({"trace": r["trace"]}))  # CloudWatch observability
    return _resp({"results": r["results"], "minutes_approvable": r["minutes_approvable"],
                  "latency_ms": int((time.time() - t0) * 1000), "version": "0.2.2"}, url)
