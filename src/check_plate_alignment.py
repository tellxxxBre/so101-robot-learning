"""
学習データ収集時のカメラフレーム（基準）と、現在のカメラ画像を比較し、
各皿の位置ズレをテンプレートマッチングで検出するツール。

使い方:
    1. `lerobot-find-cameras opencv --record-time-s 2` で現在の様子を
       outputs/captured_images/opencv_0.png に撮影
    2. .venv/bin/python check_plate_alignment.py を実行
    3. 表示されるdx,dy(px)とmatch_visを見ながら皿を基準位置に戻す
    4. 皿を動かしたら1〜3を繰り返し、dxがほぼ0になるまで調整

基準フレーム(reference)はデータ収集時の学習データ1本目・1フレーム目。
plate boxesの座標は基準フレームの解像度(640x480)基準。
"""
import argparse
import cv2

DEFAULT_REFERENCE = "outputs/reference_frames/grape_sort_episode0_frame0.png"
DEFAULT_CURRENT = "outputs/captured_images/opencv_0.png"
DEFAULT_OUT = "outputs/captured_images/plate_alignment_check.png"

# 基準フレーム(640x480)上での各皿のバウンディングボックス (x1, y1, x2, y2)
PLATE_BOXES = {
    "grape_plate (白い放射状の皿)": (280, 165, 420, 295),
    "green_plate (黒っぽい柄の皿, 緑ラベル)": (130, 260, 255, 375),
    "red_plate (無地の白い皿, 赤ラベル)": (250, 330, 380, 450),
}

MARGIN = 50  # current画像側でテンプレートを探す探索範囲の余白(px)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=DEFAULT_REFERENCE)
    parser.add_argument("--current", default=DEFAULT_CURRENT)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    reference = cv2.imread(args.reference)
    current = cv2.imread(args.current)
    if reference is None:
        raise FileNotFoundError(args.reference)
    if current is None:
        raise FileNotFoundError(args.current)

    current = cv2.resize(current, (reference.shape[1], reference.shape[0]))
    vis = current.copy()

    print(f"reference: {args.reference}")
    print(f"current:   {args.current}")
    print("-" * 60)

    for name, (x1, y1, x2, y2) in PLATE_BOXES.items():
        template = reference[y1:y2, x1:x2]
        th, tw = template.shape[:2]

        sx1, sy1 = max(0, x1 - MARGIN), max(0, y1 - MARGIN)
        sx2, sy2 = min(reference.shape[1], x2 + MARGIN), min(reference.shape[0], y2 + MARGIN)
        search = current[sy1:sy2, sx1:sx2]

        res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        found_x1, found_y1 = sx1 + max_loc[0], sy1 + max_loc[1]

        dx = found_x1 - x1
        dy = found_y1 - y1
        flag = "  <-- 要調整" if abs(dx) > 15 or abs(dy) > 15 else ""
        print(f"{name}: shift(dx,dy)=({dx:+d},{dy:+d}) px, match_score={max_val:.3f}{flag}")

        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 0, 255), 2)  # red = 基準(学習データ)位置
        cv2.rectangle(vis, (found_x1, found_y1), (found_x1 + tw, found_y1 + th), (0, 255, 0), 2)  # green = 現在位置

    cv2.imwrite(args.out, vis)
    print("-" * 60)
    print(f"可視化画像を保存: {args.out}")
    print("赤枠=学習データ時点の位置 / 緑枠=現在の位置。緑枠を赤枠に合わせるように皿を動かしてください。")


if __name__ == "__main__":
    main()
