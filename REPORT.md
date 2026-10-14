# Roll Call Vision — technical report (draft v0.2.2, Oct 13 2026)

## Problem and users
Volunteer boards (HOAs, school boards, nonprofits) approve minutes that record each vote. Transcripts and notes often get the count wrong ("passed 5-2" when 4 hands went up). Wrong minutes are legal records. Users: board secretaries and minute-takers (LumeGrid's MinutesDesk / Board Clerk customers).

## What it does
OpenCV 5 watches the meeting video during each vote window, counts raised hands per seat, and compares the count with what the transcript says. An agent decides what happens next: confirm, look again more carefully, or block minutes approval and ask a person. Visual evidence changes the next action (Agentic Vision path).

Fail-closed guards: a vote window with zero frames never confirms; an empty or missing transcript votes list never sets `minutes_approvable` true.

## OpenCV 5 implementation
See docs/ARCHITECTURE.md. opencv-python-headless==5.0.0.93: VideoCapture seeking, median background, absdiff, threshold, morphologyEx, findContours/contourArea, occlusion heuristic. Two perception configs (fast / dense) chosen by the agent.

## AWS deployment (live, us-east-2)
Deployed 2026-10-13 ~11:26 PM MT as **zip + Lambda layer** (not a container; no ECR):

| Item | Value |
|---|---|
| Function | `roll-call-vision`, Python 3.12, x86_64 |
| Version / layer | app **v0.2.2**; layer `rcv-opencv5:1` (OpenCV 5.0.0.93 headless + numpy) |
| Region | **us-east-2** (Ohio) |
| Function URL | https://hj6wfy2lilbbllikwriblbsx3m0thfif.lambda-url.us-east-2.on.aws/ |
| Auth | **AWS_IAM** (not public; SigV4 required) |
| Live console tests | `{"demo":"clean"}` → `minutes_approvable` true (~**1.0 s**); `{"demo":"transcript_error"}` → false + `hold_approval_request_human` |

Optional S3 video input (`s3_video` + transcript) is supported by the handler; demo events use bundled synthetic clips. CloudWatch Logs carry the agent trace JSON.

## Evaluation (synthetic, reproducible: `python eval/run_eval.py`, seed 26)
32 synthetic meetings, 5–9 seats, 81 votes, cases: clean, occlusion, lighting drift, brief (0.8 s) raise, transcript error (mixed overcount / undercount / large miss / zero-vs-nonzero on the four txerr M1 votes), camera jitter (±6 px), half raise.

| Metric | Result |
|---|---|
| Hand-count accuracy | 69/81 (85%) |
| Agent decision correct (after exemptions below) | 81/81 (100%) |
| Transcript errors caught | 4/4 injected M1 errors (one per txerr meeting; txerr case has 10 votes total) |
| Unsafe confirms (confirmed a wrong transcript) | **0** |
| False holds (see definition) | **12 / 81** |
| Unexpected false holds after exemptions | **0** |

### False-hold definition (exact)
**False hold** = agent held for a human (`hold_approval_request_human`) on a vote where the transcript already matched ground truth (`said == truth`).

Denominator: all 81 votes on the seed-26 synthetic run. Count: **12 / 81** (8 half_raise + 4 occlude).

Scorer exemptions (when a hold is *expected*, not scored as a decision error):
- **Occlusion:** only M1 (the dark blob is timed to the first vote window).
- **Half-raise:** any motion whose aye set includes a half-raised seat (half seats half-raise whenever they vote — including M2/M3 on meetings such as m06).

After those exemptions, unexpected false holds are **0 / 81**. Do not use the older REPORT figure of “8 false holds” — it had no consistent denominator (raw holds-with-correct-transcript = 12; residual after the old M1-only half-raise exemption = 4).

By case (count accuracy / decision accuracy): clean 21/21 & 21/21; drift 11/11 & 11/11; brief 10/10 & 10/10; jitter 10/10 & 10/10; transcript error 10/10 & 10/10; occlusion 6/10 counts & 10/10 decisions; half raise 1/9 counts & 9/9 decisions (head-height hands missed → hold).

## Limitations (honest)
- Synthetic stick-figure video only; no real meeting footage. **No claim of holdout, production, or real-room performance.**
- Seat positions are fixed ROIs; next step is OpenCV DNN person detection for seat discovery.
- Half-height raises are undercounted on these fixtures; on the synthetic cases tested the agent holds rather than confirming a wrong count. That is a property of this eval, not a guarantee for real rooms.
- Lambda latency: live console demo ~**1.0 s** per invoke (warm); box-local synthetic meetings remain ~0.5 s per ~10 s clip. Cold starts are longer.

## Responsible use
No facial recognition or identity: seats are counted, never named by vision. Evidence only flags; a human always makes the final call. Video retention 7 days (planned S3 lifecycle on `videos/` prefix). Not for surveillance; only for meetings that are already public record and recorded with consent.
