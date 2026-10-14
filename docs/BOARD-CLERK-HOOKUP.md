# Board Clerk ↔ Roll Call Vision contract (not deployed)
New Board Clerk MCP tool `verify_vote_by_video` (read-only on video, writes only an evidence note):
- input: `{board_id, meeting_id, motion_id, video_ref, window:{start,end}, seats}`
- Board Clerk sends transcript ayes from its stored motion → POST `RCV_URL` `{s3_video, transcript:{votes:[{motion,start,end,ayes_said}]}, seats}` (SigV4 / shared secret in a Worker secret).
- Response `{results:[{motion, ayes_said, ayes_seen, action}], minutes_approvable}`.
- Board Clerk effect: `action == hold_approval_request_human` adds a pending confirmation, so the existing fail-closed rule blocks `approve_minutes` until a person confirms (same path as unconfirmed mover/seconder). `mark_vision_confirmed` attaches a "vision-confirmed" evidence badge.
- Ship order: deploy RCV on AWS → add tool behind env flag `RCV_URL` (absent = tool returns "not configured") → tests → deploy Board Clerk. Do not touch the judged Amazon worker before Oct 23 freeze unless Pika agrees.
