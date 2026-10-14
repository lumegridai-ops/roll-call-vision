"""OpenCV 5 perception: count raised hands per seat inside a time window."""
import cv2, numpy as np

def _frames(path, t0, t1, stride):
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 15
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t0 * fps)); i = int(t0 * fps); out = []
    while i <= int(t1 * fps):
        ok, fr = cap.read()
        if not ok: break
        if (i - int(t0 * fps)) % stride == 0: out.append(fr)
        i += 1
    cap.release(); return out

def baseline(path, t0=0.0, t1=1.5):
    fr = _frames(path, t0, t1, 2)
    return cv2.GaussianBlur(cv2.cvtColor(np.median(np.stack(fr), 0).astype(np.uint8), cv2.COLOR_BGR2GRAY), (5, 5), 0)

def seat_rois(n, W=960):
    return [(int(W * (i + 1) / (n + 1)) - 15, 110, 85, 150) for i in range(n)]  # x,y,w,h above head

def count_hands(path, base, n_seats, t0, t1, stride=5, thresh=35, min_area=600):
    frames = _frames(path, t0, t1, stride)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    per_seat = np.zeros((len(frames), n_seats), bool); occl = np.zeros_like(per_seat)
    for fi, fr in enumerate(frames):
        g = cv2.GaussianBlur(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        d = cv2.absdiff(g, base)
        _, m = cv2.threshold(d, thresh, 255, cv2.THRESH_BINARY)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
        for s, (x, y, w, h) in enumerate(seat_rois(n_seats)):
            roi = m[y:y + h, x:x + w]
            cs, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            area = max([cv2.contourArea(c) for c in cs], default=0)
            dark = float(np.mean(g[y:y + h, x:x + w] < 60))
            occl[fi, s] = dark > 0.5          # big dark blob = something blocking the view
            per_seat[fi, s] = area >= min_area and not occl[fi, s]
    frac = per_seat.mean(0) if len(frames) else np.zeros(n_seats)
    seen = [int(s) for s in np.where(frac >= 0.5)[0]]
    unsure = [int(s) for s in range(n_seats) if 0.2 < frac[s] < 0.5 or occl[:, s].mean() > 0.2]
    return {"ayes_seen": seen, "count": len(seen), "unsure_seats": unsure,
            "frames": len(frames), "stride": stride, "thresh": thresh}
