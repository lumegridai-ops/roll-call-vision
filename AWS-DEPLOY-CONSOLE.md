# Roll Call Vision: AWS console deploy checklist (v0.2.2)
Account: LumeGrid root `matt@lumegrid.ai` (Free plan). Region: **US East (Ohio) us-east-2**, check the top-right region picker on EVERY page.
Stay inside the free tier: Lambda (1M requests and 400k GB-s per month), S3 (a few MB), CloudWatch Logs (under 5 GB). Do **not** create: ECR, API Gateway, NAT, EC2, provisioned concurrency, or Lambda SnapStart. Never click "Upgrade plan".

Artifacts on the box (`dist/` is gitignored; rebuild steps are at the bottom):
| File | Size | Use |
|---|---|---|
| `dist/rcv-opencv5-layer-py312-x86_64.zip` | 71.6 MB zipped / 193 MB unzipped | Lambda layer (OpenCV 5.0.0.93 headless + numpy 2.5.4, cp312 x86_64) |
| `dist/rcv-function.zip` | 1.7 MB | Function code (`rcv/` + 4 bundled synthetic demo clips) |
| `deploy/iam-policy-rcv-deployer.json` | n/a | Least-privilege policy for the CLI user |
| `deploy/smoke.sh` | n/a | Smoke test |
The layer and function together are about 195 MB unzipped, under Lambda's 250 MB limit. The layer is over the 50 MB console direct-upload limit, so it goes through S3 (step B). This means no container image or ECR is needed.

## A. Sign in
1. Go to https://console.aws.amazon.com/ and sign in as the root user `matt@lumegrid.ai`. Hand the screen to Matt for any MFA step.
2. Set the region (top right) to **US East (Ohio)**.

## B. S3 artifact bucket
1. Search for "S3", open it, and click **Create bucket**.
2. Use General purpose. Bucket name: `rcv-lumegrid-<12-digit account id>`. The account id is in the top-right account menu.
3. Leave the defaults: Block *all* public access ON, versioning off, encryption SSE-S3. Click **Create bucket**.
4. Open the bucket, click **Upload**, then **Add files**, and pick `dist/rcv-opencv5-layer-py312-x86_64.zip`. Click **Upload** and wait for it to succeed.
5. Click the uploaded object and copy its **Object URL** (https://rcv-lumegrid-....s3.us-east-2.amazonaws.com/rcv-opencv5-layer-py312-x86_64.zip).
6. Optional (7-day video retention per the architecture doc): go to **Management**, then **Create lifecycle rule**. Name it `expire-videos`, set prefix `videos/`, choose "Expire current versions" after 7 days, and save.

## C. Layer
1. Search for "Lambda". In the left menu choose **Layers**, then **Create layer**.
2. Name: `rcv-opencv5`. Description: `OpenCV 5.0.0.93 headless + numpy 2.5.4 (py3.12)`.
3. Choose **Upload a file from Amazon S3** and paste the Object URL from B5.
4. Compatible architectures: **x86_64**. Compatible runtimes: **Python 3.12**. Click **Create**.
5. Copy the Version ARN (`arn:aws:lambda:us-east-2:<acct>:layer:rcv-opencv5:1`).

## D. Function
1. Go to Lambda, then **Functions**, then **Create function**, and choose **Author from scratch**.
2. Name: `roll-call-vision`. Runtime: **Python 3.12**. Architecture: **x86_64**.
3. Permissions: "Create a new role with basic Lambda permissions" (CloudWatch Logs only). Leave the Advanced settings alone: **do NOT** tick "Enable function URL" here, since step F does it with IAM auth. Click **Create function**.
4. On the **Code** tab, click **Upload from**, then **.zip file**, and choose `dist/rcv-function.zip`. Click Save.
5. Still on the Code tab, scroll to **Runtime settings**, click **Edit**, and set Handler to `rcv.lambda_handler.handler`. Save.
6. Scroll to **Layers**, click **Add a layer**, then **Custom layers**. Pick `rcv-opencv5` version 1 and click **Add**.
7. Go to **Configuration**, then **General configuration**, then **Edit**. Set Memory to `1024` MB, Ephemeral storage to `512` MB, and Timeout to `1 min 0 sec`. Save.

## E. Console test (no CLI needed)
1. On the **Test** tab, create a new event named `clean` with JSON `{"demo": "clean"}` and click **Test**.
2. Expect a green result with `"minutes_approvable": true`, two `mark_vision_confirmed` entries, and `"version": "0.2.2"`. The first cold start takes a few seconds; note `latency_ms` for the report.
3. Repeat with `{"demo": "transcript_error"}`. Expect `false` and `hold_approval_request_human`, which is the fail-closed path.
4. Under **Monitor**, click **View CloudWatch logs**. The latest stream should show the `{"trace": ...}` JSON, which is the agent trace for the report and video.

## F. Function URL (IAM auth)
1. Go to **Configuration**, then **Function URL**, then **Create function URL**.
2. Auth type: **AWS_IAM**. Do not choose NONE, because a public URL could burn free-tier compute. Leave CORS off and click **Save**.
3. Copy the Function URL (`https://<id>.lambda-url.us-east-2.on.aws/`) into SUBMIT.md and the Devpost "endpoint" field.

## G. (Optional) S3 video input for real meetings
Only needed for non-demo calls (`{"s3_video": "s3://rcv-lumegrid-<acct>/videos/x.mp4", "transcript": {...}}`):
1. Go to Configuration, then **Permissions**, and click the role name to open IAM.
2. Click **Add permissions**, then **Create inline policy**, then the JSON tab, and paste:
```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::rcv-lumegrid-*/videos/*"}]}
```
3. Name it `rcv-read-videos` and create it.

## H. Least-privilege IAM user for CLI (later deploys come from the box)
1. Search for "IAM", open **Users**, and click **Create user**. Name: `rcv-deployer`. Leave console access **unticked**. Click Next.
2. Choose **Attach policies directly**, then **Create policy**. This opens a new tab.
3. On the JSON tab, paste all of `deploy/iam-policy-rcv-deployer.json` (below). Name the policy `rcv-deployer-policy` and create it.
4. Back on the user tab, click refresh, tick `rcv-deployer-policy`, then Next and **Create user**.
5. Open the user, go to **Security credentials**, then **Create access key**. Choose "Command Line Interface (CLI)", tick the confirmation, and click Create.
6. The key pair must go **straight into the box CLI config**, not into chat, notes or files in git. On the box, run `aws configure --profile rcv` (region `us-east-2`, output `json`), then `export AWS_PROFILE=rcv`. Install the CLI first if missing (see the bottom of this doc). Click Done.

Policy (`deploy/iam-policy-rcv-deployer.json`): Lambda manage/invoke **only** `roll-call-vision*`, publish **only** layer `rcv-opencv5`, S3 put/get/list **only** `rcv-lumegrid-*`, read logs **only** `/aws/lambda/roll-call-vision*`, and `sts:GetCallerIdentity`. It has no IAM, no create/delete function and no billing permissions.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "LambdaManageRcvOnly", "Effect": "Allow",
     "Action": ["lambda:GetFunction","lambda:GetFunctionConfiguration","lambda:UpdateFunctionCode","lambda:UpdateFunctionConfiguration",
                "lambda:PublishVersion","lambda:InvokeFunction","lambda:InvokeFunctionUrl","lambda:GetFunctionUrlConfig",
                "lambda:UpdateFunctionUrlConfig","lambda:ListVersionsByFunction"],
     "Resource": "arn:aws:lambda:us-east-2:*:function:roll-call-vision*"},
    {"Sid": "LambdaLayerRcvOnly", "Effect": "Allow",
     "Action": ["lambda:PublishLayerVersion","lambda:GetLayerVersion","lambda:ListLayerVersions"],
     "Resource": ["arn:aws:lambda:us-east-2:*:layer:rcv-opencv5","arn:aws:lambda:us-east-2:*:layer:rcv-opencv5:*"]},
    {"Sid": "ArtifactBucket", "Effect": "Allow",
     "Action": ["s3:PutObject","s3:GetObject","s3:ListBucket"],
     "Resource": ["arn:aws:s3:::rcv-lumegrid-*","arn:aws:s3:::rcv-lumegrid-*/*"]},
    {"Sid": "ReadLogs", "Effect": "Allow",
     "Action": ["logs:FilterLogEvents","logs:GetLogEvents","logs:DescribeLogStreams"],
     "Resource": "arn:aws:logs:us-east-2:*:log-group:/aws/lambda/roll-call-vision*"},
    {"Sid": "WhoAmI", "Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"}
  ]
}
```

## I. Smoke test (box)
```bash
cd /workspace/lumegrid/ventures/hackathons/roll-call-vision
AWS_PROFILE=rcv aws sts get-caller-identity          # expect user/rcv-deployer
AWS_PROFILE=rcv deploy/smoke.sh clean                # SigV4-signed curl to Function URL + 4 direct invokes
```
Expected output:
- `HTTP 200` with a body containing `"minutes_approvable": true`.
- `clean True` and `lighting_drift True`.
- `transcript_error False` and `occluded False`, each with `['hold_approval_request_human']`.

Unsigned check: `curl -s -o /dev/null -w '%{http_code}\n' -X POST <FunctionURL>` should return **403**, which proves the URL is not public.

## J. Later redeploys (CLI, from the box)
```bash
cd /workspace/lumegrid/ventures/hackathons/roll-call-vision
deploy/build.sh   # rebuilds dist/*.zip
aws lambda update-function-code --function-name roll-call-vision --region us-east-2 --zip-file fileb://dist/rcv-function.zip
# layer only if deps change:
aws s3 cp dist/rcv-opencv5-layer-py312-x86_64.zip s3://rcv-lumegrid-<acct>/
aws lambda publish-layer-version --layer-name rcv-opencv5 --region us-east-2 --compatible-runtimes python3.12 --compatible-architectures x86_64 \
  --content S3Bucket=rcv-lumegrid-<acct>,S3Key=rcv-opencv5-layer-py312-x86_64.zip
aws lambda update-function-configuration --function-name roll-call-vision --region us-east-2 --layers <new layer version ARN>
```
AWS CLI v2 install (box, user-space): `curl -sSo /tmp/awscli.zip https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip && cd /tmp && python3 -m zipfile -e awscli.zip . && chmod +x aws/install aws/dist/aws && ./aws/install -i ~/.local/aws-cli -b ~/.local/bin`

## Cost guardrails
- Optional: go to Billing, then **Budgets**, then Create budget, choose the "Zero spend budget" template, and add the email matt@lumegrid.ai. Budgets are free.
- IAM auth on the URL, a 60 s timeout and 1024 MB memory mean each demo call uses about 1–3 GB-s, against 400,000 GB-s free per month.
