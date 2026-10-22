"""俯瞰(index0)＋手首(index1)を同時に開いて、両方30fps出るか(USB帯域)を確認する。
あなたのターミナルで実行。10秒間ストリームして実効fpsを表示、最後のフレームを保存。
usage: python oyster_vla/test_dual_cam.py
"""
import os
import time

import cv2

OUT = os.path.join(os.path.dirname(__file__), "cam_scan")
os.makedirs(OUT, exist_ok=True)

caps = {}
for name, idx in [("overhead", 0), ("wrist", 1)]:
    cap = cv2.VideoCapture(idx)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        raise SystemExit(f"{name}(index{idx}) を開けませんでした")
    caps[name] = cap

# ウォームアップ
for _ in range(15):
    for c in caps.values():
        c.read()

counts = {k: 0 for k in caps}
last = {}
t0 = time.time()
DURATION = 10.0
while time.time() - t0 < DURATION:
    for name, cap in caps.items():
        ok, f = cap.read()
        if ok:
            counts[name] += 1
            last[name] = f

elapsed = time.time() - t0
print("\n=== 結果 (同時ストリーム {:.1f}秒) ===".format(elapsed))
ok_all = True
for name in caps:
    fps = counts[name] / elapsed
    verdict = "✅" if fps >= 27 else "⚠️ 低い"
    if fps < 27:
        ok_all = False
    print(f"{name}: {fps:.1f} fps {verdict}")
    if name in last:
        p = os.path.join(OUT, f"dual_{name}.jpg")
        cv2.imwrite(p, last[name])
        print(f"  最終フレーム: {p}")
for c in caps.values():
    c.release()
print("\n判定:", "✅ 2台同時30fps OK — 収録に進めます" if ok_all else "⚠️ 帯域不足の可能性 — USBの挿し口を分ける/ハブを変えるを試す")
