"""接続中のカメラ(index 0..4)を開いて各1枚保存し、どのindexが何か分かるようにする。
あなたのターミナルで実行(初回はカメラ権限ダイアログ→許可)。
usage: python oyster_vla/scan_cameras.py
保存先: oyster_vla/cam_scan/index_N.jpg
"""
import os
import time

import cv2

OUT = os.path.join(os.path.dirname(__file__), "cam_scan")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))

opened = []
for idx in range(5):
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        continue
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    for _ in range(12):
        cap.read()
        time.sleep(0.03)
    ok, frame = cap.read()
    cap.release()
    if ok and frame is not None:
        h, w = frame.shape[:2]
        path = os.path.join(OUT, f"index_{idx}.jpg")
        cv2.imwrite(path, frame)
        opened.append((idx, w, h))
        print(f"index {idx}: OK ({w}x{h}) -> {path}")

print("\n開けたindex:", [i for i, _, _ in opened])
if not opened:
    print("1つも開けませんでした。カメラ権限(システム設定→プライバシー→カメラ)でターミナルを許可してください")
