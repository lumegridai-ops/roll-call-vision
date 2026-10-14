#!/usr/bin/env bash
# Rebuild dist/ (layer + function zips) for Lambda python3.12 x86_64. No docker needed.
set -euo pipefail; cd "$(dirname "$0")/.."
rm -rf dist /tmp/rcv-whl /tmp/rcv-layer /tmp/rcv-fn; mkdir -p dist /tmp/rcv-layer/python /tmp/rcv-fn/rcv/demo_clips
.venv/bin/python -m pip download -q --only-binary=:all: --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.12 --implementation cp -d /tmp/rcv-whl -r requirements.txt
for w in /tmp/rcv-whl/*.whl; do python3 -m zipfile -e "$w" /tmp/rcv-layer/python; done
find /tmp/rcv-layer -name __pycache__ -prune -exec rm -rf {} +; rm -rf /tmp/rcv-layer/python/numpy/tests /tmp/rcv-layer/python/numpy/*/tests
[ -f demo/out/clean.mp4 ] || .venv/bin/python demo/run_demo.py
cp rcv/*.py /tmp/rcv-fn/rcv/; cp demo/out/*.mp4 /tmp/rcv-fn/rcv/demo_clips/
python3 - <<'PY'
import zipfile,os
for src,out in [("/tmp/rcv-layer","dist/rcv-opencv5-layer-py312-x86_64.zip"),("/tmp/rcv-fn","dist/rcv-function.zip")]:
  with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for r,_,fs in os.walk(src):
      for f in sorted(fs):
        p=os.path.join(r,f); i=zipfile.ZipInfo.from_file(p,os.path.relpath(p,src)); i.compress_type=zipfile.ZIP_DEFLATED
        i.external_attr=(0o755 if os.access(p,os.X_OK) else 0o644)<<16; z.writestr(i,open(p,"rb").read())
PY
ls -la dist; sha256sum dist/*.zip
