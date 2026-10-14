# Roll Call Vision: OpenCV AI Competition 2026 (powered by AWS)
Verified live Oct 13, 7:40 PM MT: deadline **Mon Oct 26, 11:45 PM PDT = Tue Oct 27, 12:45 AM MDT** (overview text also says 11:59 PM PT; use 11:45). Target submit **Sun Oct 25, 6 PM MT**.
Hard rules: OpenCV 5 for substantive video analysis (yes, 5.0.0) AND a meaningful AWS component (**DONE**: Lambda zip+layer live in us-east-2). Report, pinned deps, build/deploy/test docs, architecture diagram, working web endpoint or live screen-share, video <= 5 min showing team + app + architecture + results, evaluation incl. failures. Repo may be private if judge-accessible. Opt into Agentic Vision Award ($1k).

## Built (box, git see `git log`; v0.2.2 Oct 13 PM — AWS live)
- rcv/vision.py: OpenCV 5 baseline (median), absdiff, threshold, morphology, contours per seat ROI, occlusion flag.
- rcv/agent.py: perceive -> decide -> act. Mismatch/unsure => denser re-look at lower threshold => still off => hold minutes approval, ask a human (Board Clerk fail-closed rule). Zero-frame windows and empty votes fail closed (never silent approve). Full trace JSON.
- Synthetic eval (demo/run_demo.py, tests/test_demo.py): clean 2/2 confirmed; transcript error caught; occluded seat escalated; lighting drift confirmed.
- rcv/lambda_handler.py + zip deploy + layer `rcv-opencv5:1` (no ECR): **deployed** us-east-2. See Deployed below.

## Left
1. **DONE:** AWS account + Lambda `roll-call-vision` live (us-east-2, v0.2.2, Function URL IAM). See Deployed.
2. Board Clerk contract written (docs/BOARD-CLERK-HOOKUP.md); wire Board Clerk MCP to the live Function URL (IAM-signed invoke).
3. DONE v0.2.1: 32-meeting eval + fail-closed guards + false-hold definition in REPORT.md; next: real seat detection (OpenCV DNN), fix half-raise misses.
4. Report REPORT.md + docs/ARCHITECTURE.md updated for live AWS; architecture PNG at docs/architecture.png. **Still need:** Devpost draft/submit + demo video (<=5 min).
5. Repo: public or judge-accessible GitHub/archive link for Devpost (box has local git; GitHub push needs Matt / LumeGrid GitHub).

## Browser steps (Matt / browser agent, account mbrady14)
1. https://opencv26.devpost.com/ -> Join hackathon (accept rules).
2. "Enter a submission" -> Project name "Roll Call Vision"; tagline: "OpenCV 5 checks every board vote on video and refuses to approve minutes until the count matches."
3. Fill: description (from report summary), built-with: opencv5, python, aws-lambda, amazon-s3, cloudwatch, mcp; repo/archive link; endpoint URL (Function URL above — note IAM auth); video URL (YouTube unlisted ok); tick Agentic Vision Award; upload report + diagrams.
4. Submit before Oct 26 11:45 PM PDT.

## Deployed (2026-10-13 11:26 PM MT)
- AWS Lambda `roll-call-vision`, us-east-2, v0.2.2 with layer rcv-opencv5:1
- Function URL (AWS_IAM auth): https://hj6wfy2lilbbllikwriblbsx3m0thfif.lambda-url.us-east-2.on.aws/
- Live console tests: demo clean, minutes_approvable true (~1.0 s); demo transcript_error, false + hold_approval_request_human
