"""トマト選果 統合ループ (Phase 3):
  ACTが掴んで持ち上げ → Claude(VLM)が判定 → ルール表で箱決定 → 記憶ポーズ再生で箱へ → 開いて戻る

前提:
  - tomato_sort/poses.json が capture_pose.py で作成済み
  - 環境変数 ANTHROPIC_API_KEY が設定済み
  - アームを home 付近の構えにしてから起動する

usage: python tomato_sort/tomato_sort.py [--cycles 5] [--grasp-seconds 15]
中断: Ctrl+C (アームはその場で固まる)
"""
import argparse
import base64
import json
import os
import threading
import time
from copy import copy
from contextlib import nullcontext

import cv2
import numpy as np
import torch

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies import get_policy_class, make_pre_post_processors
from lerobot.policies.utils import prepare_observation_for_inference
from lerobot.processor.factory import make_default_processors
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.utils.constants import OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts, hw_to_dataset_features

HERE = os.path.dirname(__file__)
PORT = "/dev/cu.usbmodem5B7B0090111"
POLICY_PATH = "outputs/train/act_tomato_grasp/checkpoints/last/pretrained_model"
TASK = "Pick up a tomato and lift it up"
VLM_MODEL = "claude-fable-5"
LOG_DIR = os.path.join(HERE, "logs")

# 判定ラベル → 箱ポーズ名 (ルール表: ここを書き換えれば振り分け変更)
LABEL_TO_BOX = {
    "seihin": "seihin",        # 色づき良品 → 正品箱
    "greenback": "greenback",  # グリーンヘッド → グリーンバック箱
    "kikakugai": "kikakugai",  # 真緑 or シワ/傷み → 規格外箱
}

VLM_PROMPT = """この画像はロボットアームのグリッパ周辺を切り出して拡大したものです。グリッパ(白い樹脂の指)が画像内にあり、ミニトマト(細長いプラム型)を掴んで持ち上げている場合があります。掴んでいるかを確認し、掴んでいる場合はそのトマトを分類してください。トマトの一部がグリッパの指に隠れている場合もありますが、見えている部分で判断してください。

重要: このカメラは暗所で彩度が落ちるため、実物の「緑」は画像上では【淡い黄緑〜黄色っぽい色ムラ】程度にしか写りません。グリッパが保持しているトマトの先端・肩・端の色を注意深く観察してください。

分類基準:
- greenback: 保持しているトマトの先端や肩や端に、わずかでも黄緑〜黄色がかった部分が見える(画像上では薄い黄色ムラに見えることが多い)。疑わしければgreenback
- seihin: 先端まで完全に均一な橙〜赤で、黄緑がかった部分が全くない
- kikakugai: ほぼ全体が緑〜白緑(未熟)、または表面にシワ・黒ずみ・傷みがある

必ず次のJSONだけを出力してください(説明文なし):
{"held": true/false, "label": "seihin"|"greenback"|"kikakugai"|null, "reason": "10文字程度"}
heldは「グリッパがトマトを保持して宙に浮いているか」。箱の中に置かれているトマトは無視してください。"""


def clear_overload(robot, name: str):
    """過負荷保護でロックしたモーターをトルク入れ直しで復帰させる"""
    print(f"  (モーター{name}の過負荷を検知 → 自動復帰)")
    try:
        robot.bus.write("Torque_Enable", name, 0, normalize=False, num_retry=3)
        time.sleep(0.15)
        robot.bus.write("Torque_Enable", name, 1, normalize=False, num_retry=3)
        time.sleep(0.1)
    except Exception as e:
        print(f"  (復帰失敗: {str(e)[:60]})")


def safe_write_goal(robot, name: str, val: int):
    """Goal_Position書き込み。Overloadなら復帰させ、押し付けをやめて現在位置で保持"""
    try:
        robot.bus.write("Goal_Position", name, val, normalize=False, num_retry=1)
    except RuntimeError as e:
        if "Overload" in str(e):
            clear_overload(robot, name)
            try:
                # 同じ目標に再度押し付けない。今いる位置を目標にして無理をやめる
                cur = robot.bus.sync_read("Present_Position", normalize=False, num_retry=2)[name]
                robot.bus.write("Goal_Position", name, int(cur), normalize=False, num_retry=2)
            except Exception:
                pass
        else:
            raise


def goto(robot, target: dict, duration: float = 2.0, hold_gripper: float | None = None, hz: int = 25):
    """現在位置から target(生tick) へゆっくり補間移動。hold_gripper指定時はグリッパ値を固定。"""
    cur = robot.bus.sync_read("Present_Position", normalize=False, num_retry=2)
    tgt = dict(target)
    if hold_gripper is not None:
        tgt["gripper"] = hold_gripper
    steps = max(2, int(duration * hz))
    for s in range(1, steps + 1):
        a = s / steps
        for name in cur:
            val = int(round(cur[name] + (tgt[name] - cur[name]) * a))
            safe_write_goal(robot, name, val)
        time.sleep(1.0 / hz)


def set_gripper(robot, value: float, duration: float = 0.8, hz: int = 25):
    cur = robot.bus.sync_read("Present_Position", normalize=False, num_retry=2)["gripper"]
    steps = max(2, int(duration * hz))
    for s in range(1, steps + 1):
        a = s / steps
        val = int(round(cur + (value - cur) * a))
        safe_write_goal(robot, "gripper", val)
        time.sleep(1.0 / hz)


# 判定ポーズ到達時にグリッパ+トマトが写る領域 (640x480基準, 12枚の実測から)
CROP_X0, CROP_X1, CROP_Y0, CROP_Y1 = 10, 320, 0, 240


def judge_with_vlm(client, image_rgb: np.ndarray, crop_save_path: str | None = None) -> dict:
    """グリッパ周辺を切り出し拡大してClaudeに投げ {held, label, reason} を得る"""
    crop = image_rgb[CROP_Y0:CROP_Y1, CROP_X0:CROP_X1]
    crop = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    if crop_save_path:
        cv2.imwrite(crop_save_path, cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
    bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    b64 = base64.standard_b64encode(buf.tobytes()).decode()
    msg = client.messages.create(
        model=VLM_MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"}, output_config={"effort": "high"},  # じっくり観察させる(最高精度)
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": VLM_PROMPT},
            ],
        }],
    )
    text = next(b.text for b in msg.content if getattr(b, "type", "") == "text")
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--grasp-seconds", type=float, default=15.0)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("環境変数 ANTHROPIC_API_KEY を設定してください (export ANTHROPIC_API_KEY=...)")
    import anthropic
    client = anthropic.Anthropic()

    with open(os.path.join(HERE, "poses.json")) as f:
        poses = json.load(f)
    gripper_open = poses["home"]["gripper"]
    os.makedirs(LOG_DIR, exist_ok=True)

    # --- ロボット ---
    rcfg = SOFollowerRobotConfig(
        port=PORT,
        cameras={"overhead": OpenCVCameraConfig(index_or_path=0, width=640, height=480, fps=30)},
        disable_torque_on_disconnect=False,
    )
    rcfg.id = "my_follower"
    robot = SOFollower(rcfg)
    robot.connect()
    print("robot connected")

    # --- ポリシー ---
    pcfg = PreTrainedConfig.from_pretrained(POLICY_PATH)
    pcfg.pretrained_path = POLICY_PATH
    pcfg.device = "mps"
    policy = get_policy_class(pcfg.type).from_pretrained(POLICY_PATH, config=pcfg)
    policy.to("mps").eval()
    pre, post = make_pre_post_processors(
        policy_cfg=pcfg, pretrained_path=POLICY_PATH, dataset_stats=None,
        preprocessor_overrides={"device_processor": {"device": "mps"}},
    )
    _t, robot_action_proc, robot_obs_proc = make_default_processors()
    features = combine_feature_dicts(
        hw_to_dataset_features(robot.observation_features, "observation", True),
        hw_to_dataset_features(robot.action_features, "action", True),
    )
    action_keys = features["action"]["names"]
    device = torch.device("mps")
    print("policy loaded")

    # 起動時: どんな姿勢からでも、ゆっくり構え(home)へ移動
    print("構え(home)へゆっくり移動します...")
    goto(robot, poses["transit"], duration=2.5)
    goto(robot, poses["home"], duration=2.5)
    print("構え完了")

    results = []
    try:
        for cycle in range(1, args.cycles + 1):
            input(f"\n=== サイクル {cycle}/{args.cycles} === トマトを得意ゾーンに置いて Enter: ")

            # --- ① ACTで掴む ---
            policy.reset(); pre.reset(); post.reset()
            t0 = time.time()
            FPS = 30.0  # 学習時と同じ制御周期に厳密に合わせる(速すぎると暴走する)
            while time.time() - t0 < args.grasp_seconds:
                tick = time.perf_counter()
                try:
                    obs = robot.get_observation()
                    obs_p = robot_obs_proc(obs)
                    frame = build_dataset_frame(features, obs_p, prefix=OBS_STR)
                    with torch.inference_mode():
                        ob = prepare_observation_for_inference(copy(frame), device, TASK, robot.name)
                        ob = pre(ob)
                        act = policy.select_action(ob)
                        act = post(act)
                    act = act.squeeze(0).cpu()
                    action_dict = {k: act[i].item() for i, k in enumerate(action_keys)}
                    processed = robot_action_proc((action_dict, obs))
                    robot.send_action(processed)
                except RuntimeError as e:
                    if "Overload" in str(e):
                        # どのモーターか特定してその場で復帰
                        import re
                        m = re.search(r"id_=(\d)", str(e))
                        if m:
                            clear_overload(robot, ["shoulder_pan","shoulder_lift","elbow_flex","wrist_flex","wrist_roll","gripper"][int(m.group(1))-1])
                        time.sleep(0.1)
                    else:
                        raise
                elapsed = time.perf_counter() - tick
                time.sleep(max(0.0, 1.0 / FPS - elapsed))
            print("  掴みフェーズ終了 → 判定ポーズへ移動して判定します")

            # --- ② 判定ポーズで撮影 → 判定と移動を並行 ---
            hold_now = robot.bus.sync_read("Present_Position", normalize=False, num_retry=2)["gripper"]
            goto(robot, poses["inspect"], duration=2.0, hold_gripper=hold_now)
            time.sleep(0.6)
            obs = robot.get_observation()
            img = obs["overhead"]
            stamp = time.strftime("%H%M%S")
            crop_path = os.path.join(LOG_DIR, f"cycle{cycle}_{stamp}_crop.jpg")

            # 判定APIを別スレッドで開始し、待たずに中継点へ動き出す
            holder = {}
            def _judge():
                try:
                    holder["v"] = judge_with_vlm(client, img, crop_save_path=crop_path)
                except Exception as e:
                    holder["e"] = e
            t_judge0 = time.time()
            th = threading.Thread(target=_judge, daemon=True)
            th.start()
            print("  判定中...(考えてる間に中継点へ移動)")
            goto(robot, poses["transit"], duration=2.0, hold_gripper=hold_now)
            th.join()  # 移動で隠しきれなかった分だけここで待つ
            judge_s = time.time() - t_judge0
            if "e" in holder:
                print(f"  VLM呼び出し失敗: {str(holder['e'])[:100]} → 規格外扱い")
                verdict = {"held": True, "label": "kikakugai", "reason": "judge error"}
            else:
                verdict = holder["v"]
            cv2.imwrite(os.path.join(LOG_DIR, f"cycle{cycle}_{stamp}_{verdict.get('label')}.jpg"),
                        cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print(f"  VLM判定({judge_s:.1f}秒): {verdict}")

            # --- ③ 箱へ (すでに中継点にいる) ---
            if not verdict.get("held"):
                print("  → 掴めていない。構えに戻って開きます")
                goto(robot, poses["home"], duration=2.0, hold_gripper=hold_now)
                set_gripper(robot, gripper_open)
                results.append((cycle, "MISS", None))
                continue

            label = verdict.get("label") or "kikakugai"
            box = LABEL_TO_BOX.get(label, "kikakugai")
            print(f"  → {label} と判定 → {box} 箱へ")
            goto(robot, poses[box], duration=2.0, hold_gripper=hold_now)
            set_gripper(robot, gripper_open)   # 落とす
            time.sleep(0.4)
            goto(robot, poses["transit"], duration=1.5)
            goto(robot, poses["home"], duration=2.0)
            results.append((cycle, "OK", label))

    except KeyboardInterrupt:
        print("\n中断。アームは保持状態のままです")
    finally:
        print("\n=== 結果 ===")
        for c, st, lb in results:
            print(f"  cycle{c}: {st} {lb or ''}")
        ok = sum(1 for _, st, _ in results if st == "OK")
        print(f"  通し成功: {ok}/{len(results)}")
        robot.disconnect()


if __name__ == "__main__":
    main()
