#!/usr/bin/env bash
# Smoke test Roll Call Vision. Usage: deploy/smoke.sh [demo-name]   (needs aws CLI creds for rcv-deployer)
# Function URL uses AWS_IAM auth, so we call it SigV4-signed via curl --aws-sigv4.
set -euo pipefail
REGION=us-east-2; FN=roll-call-vision; DEMO=${1:-clean}
URL=$(aws lambda get-function-url-config --function-name "$FN" --region $REGION --query FunctionUrl --output text)
eval "$(aws configure export-credentials --format env)"
echo "== Function URL ($URL) demo=$DEMO"
curl -sS -w '\nHTTP %{http_code}  %{time_total}s\n' --aws-sigv4 "aws:amz:$REGION:lambda" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" ${AWS_SESSION_TOKEN:+-H "x-amz-security-token: $AWS_SESSION_TOKEN"} \
  -H 'content-type: application/json' -d "{\"demo\":\"$DEMO\"}" "$URL"
echo "== Direct invoke (all 4 demos; expect clean/lighting_drift true, transcript_error/occluded false)"
for d in clean transcript_error occluded lighting_drift; do
  aws lambda invoke --function-name "$FN" --region $REGION --cli-binary-format raw-in-base64-out \
    --payload "{\"demo\":\"$d\"}" /tmp/rcv-$d.json >/dev/null
  python3 -c "import json;r=json.load(open('/tmp/rcv-$d.json'));print('$d', r.get('minutes_approvable'), [x['action'] for x in r.get('results',[])], r.get('latency_ms'),'ms')"
done
