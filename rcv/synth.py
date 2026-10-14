"""Synthetic board-meeting video (no real people). Draws N seated figures; during each vote
window the 'aye' members raise an arm. Optional occlusion + lighting drift for hard cases."""
import cv2, numpy as np, json

W, H, FPS = 960, 540, 15

def seat_xy(i, n):
    return int(W * (i + 1) / (n + 1)), 330

def render(path, n_seats=7, votes=None, seed=0, occlude=None, drift=0.0, jitter=0, half=()):
    rng = np.random.default_rng(seed)
    votes = votes or [{"motion": "M1", "ayes": [0, 1, 2, 4], "start": 2.0, "end": 4.0}]
    total = max(v["end"] for v in votes) + 1.5
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for f in range(int(total * FPS)):
        t = f / FPS
        img = np.full((H, W, 3), 200, np.uint8)
        cv2.rectangle(img, (0, 380), (W, H), (90, 60, 40), -1)  # table
        raised = set()
        for v in votes:
            if v["start"] <= t <= v["end"]:
                raised |= set(v["ayes"])
        for i in range(n_seats):
            x, y = seat_xy(i, n_seats)
            col = (60 + 20 * i % 120, 80, 140)
            cv2.rectangle(img, (x - 35, y - 20), (x + 35, y + 60), col, -1)
            cv2.circle(img, (x, y - 45), 24, (150, 170, 210), -1)
            if i in raised:
                top = y - 60 if i in half else y - 120   # half = hand only to head height
                cv2.line(img, (x + 30, y - 10), (x + 40, top), col, 16)
                cv2.circle(img, (x + 40, top - 5), 11, (150, 170, 210), -1)
        if occlude is not None and occlude[0] <= t <= occlude[1]:
            ox, _ = seat_xy(occlude[2], n_seats)
            cv2.rectangle(img, (ox - 10, 120), (ox + 70, 260), (40, 40, 40), -1)
        img = cv2.convertScaleAbs(img, alpha=1.0 + drift * np.sin(t), beta=0)
        img = cv2.add(img, rng.integers(0, 12, img.shape, dtype=np.uint8))
        if jitter:
            M = np.float32([[1, 0, rng.integers(-jitter, jitter + 1)], [0, 1, rng.integers(-jitter, jitter + 1)]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
        vw.write(img)
    vw.release()
    return {"seats": n_seats, "fps": FPS, "votes": votes}
