"""保存済みの判定画像(crop)を、現行プロンプト+モデルで再判定する(ロボット不要)。
プロンプト/モデル改良の高速検証用。

usage: python tomato_sort/rejudge.py
"""
import glob
import json
import os
import sys

import cv2

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from tomato_sort import VLM_MODEL, VLM_PROMPT  # noqa: E402

import base64  # noqa: E402


def judge_crop(client, crop_bgr):
    ok, buf = cv2.imencode(".jpg", crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    b64 = base64.standard_b64encode(buf.tobytes()).decode()
    msg = client.messages.create(
        model=VLM_MODEL, max_tokens=4000,
        thinking={"type": "adaptive"}, output_config={"effort": "high"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": VLM_PROMPT},
        ]}],
    )
    text = next(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY を設定してください")
    import anthropic
    client = anthropic.Anthropic()
    files = sorted(glob.glob(os.path.join(HERE, "logs", "inspect_test_*_crop.jpg")))
    print(f"モデル: {VLM_MODEL} / 対象: {len(files)}枚\n")
    for f in files:
        crop = cv2.imread(f)  # 保存済みcropはBGR
        try:
            v = judge_crop(client, crop)
        except Exception as e:
            v = {"error": str(e)}
        print(f"{os.path.basename(f)}: {v}")
        if "error" in v:
            break  # 同じエラーの繰り返しを防ぐ


if __name__ == "__main__":
    main()
