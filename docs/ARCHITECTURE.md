# Roll Call Vision — architecture

```mermaid
flowchart LR
  subgraph Client
    BC[Board Clerk MCP server\nCloudflare Worker] -- "verify_vote_by_video(meeting, motion)" --> API
  end
  subgraph AWS["AWS us-east-2 (deployed: zip + layer rcv-opencv5:1, v0.2.2)"]
    API[Lambda Function URL\nAWS_IAM auth] --> L[Lambda roll-call-vision\nPython 3.12 + OpenCV 5.0.0 layer]
    S3[(S3: meeting video,\nSSE, 7-day lifecycle)] --> L
    L --> CW[CloudWatch Logs\nagent trace JSON]
  end
  subgraph Agent["Agent loop inside Lambda (rcv/agent.py)"]
    P1[Perceive: count_hands stride 5, thresh 35] --> D{transcript ayes == seen\nand no unsure seats?}
    D -- yes --> A1[Action: mark_vision_confirmed]
    D -- no --> P2[Re-perceive: stride 1, thresh 25]
    P2 --> D2{match?}
    D2 -- yes --> A1
    D2 -- no --> A2[Action: hold minutes approval,\nrequest human confirmation]
  end
  L --- Agent
  A2 --> BC
```

OpenCV 5 pipeline per seat ROI: grayscale → Gaussian blur → absdiff vs median baseline (pre-vote frames) → binary threshold → morphological open → external contours → largest-area test; dark-fraction occlusion flag. Per-frame votes aggregated over the vote window (>=50% of frames = aye; 20–50% = unsure).

Live endpoint (IAM): `https://hj6wfy2lilbbllikwriblbsx3m0thfif.lambda-url.us-east-2.on.aws/` — Function URL with AWS_IAM auth (not public). Deploy path is zip function code + OpenCV layer (no container / ECR).
