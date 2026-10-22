"""牡蠣VLA 対話デモ: あなたが日本語/英語で指示 → 学習済みSmolVLAがアームを動かす。
指示を入れ替えて「箱に入れる/お辞儀/赤袋を箱に」を切り替えられるか(=言語条件付け)を体験する。

usage: python oyster_vla/oyster_interactive.py [--seconds 30] [--device mps]
中断: Ctrl+C (アームはその場で固定, 落ちない)
指示例: 牡蠣を箱に入れて / 牡蠣をお辞儀させて / 赤い袋を箱に入れて  (quitで終了)
"""
import argparse
import os
import re
import time
from copy import copy

import cv2
import numpy as np
import torch

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies import make_pre_post_processors
from lerobot.policies.factory import make_policy
from lerobot.policies.utils import prepare_observation_for_inference
from lerobot.processor.factory import make_default_processors
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.utils.constants import OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts, hw_to_dataset_features
from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata

PORT = "/dev/cu.usbmodem5B7B0090111"
POLICY_PATH = "outputs/oyster_smolvla/050000/pretrained_model"
DATASET_ROOT = "/Users/terunobuakiyama/.cache/huggingface/lerobot/local/so101_oyster_vla_20260920_20260920_182107"
REPO = "local/so101_oyster_vla_20260920_20260920_182107"
MOTOR_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

# 学習した3つの英語指示。日本語入力はキーワードでこれに写像
TASKS = {
    "box": "pick up the white oyster plush and put it in the box",
    "bow": "pick up the white oyster plush and make it bow",
    "snack": "pick up the red snack bag and put it in the box",
}


def choose_task(text: str):
    if any(k in text for k in ["袋", "スナック", "赤", "snack", "bag"]):
        return "snack"
    if any(k in text for k in ["お辞儀", "おじぎ", "辞儀", "bow", "傾"]):
        return "bow"
    if any(k in text for k in ["箱", "box", "牡蠣", "カキ", "かき", "oyster", "入れ"]):
        return "box"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30.0, help="1指示あたりの実行秒数")
    ap.add_argument("--device", default="mps")
    args = ap.parse_args()

    rcfg = SOFollowerRobotConfig(
        port=PORT,
        cameras={"overhead": OpenCVCameraConfig(index_or_path=0, width=640, height=480, fps=30)},
        disable_torque_on_disconnect=False,
    )
    rcfg.id = "my_follower"
    robot = SOFollower(rcfg)
    robot.connect()
    print("robot connected")

    pcfg = PreTrainedConfig.from_pretrained(POLICY_PATH)
    pcfg.pretrained_path = POLICY_PATH
    pcfg.device = args.device
    dm = LeRobotDatasetMetadata(REPO, root=DATASET_ROOT)
    policy = make_policy(pcfg, ds_meta=dm)  # PEFT(LoRA)を内部でロード
    policy.eval()
    pre, post = make_pre_post_processors(
        policy_cfg=pcfg, pretrained_path=POLICY_PATH, dataset_stats=None,
        preprocessor_overrides={"device_processor": {"device": args.device}},
    )
    _t, robot_action_proc, robot_obs_proc = make_default_processors()
    features = combine_feature_dicts(
        hw_to_dataset_features(robot.observation_features, "observation", True),
        hw_to_dataset_features(robot.action_features, "action", True),
    )
    action_keys = features["action"]["names"]
    device = torch.device(args.device)
    print("policy loaded (SmolVLA + LoRA)")
    print("\n=== 牡蠣VLA 対話デモ ===")
    print("指示を入力してEnter。例: 牡蠣を箱に入れて / 牡蠣をお辞儀させて / 赤い袋を箱に入れて")
    print("(quit で終了。Ctrl+C でいつでも停止=アームは固定)")

    try:
        while True:
            text = input("\n指示> ")
            if text.strip().lower() in ("quit", "q", "exit"):
                break
            key = choose_task(text)
            if key is None:
                print("  どのタスクか判別できず(箱/お辞儀/赤袋 のどれかを含めて)。もう一度")
                continue
            task = TASKS[key]
            print(f"  → 実行 [{key}]: \"{task}\"  ({args.seconds:.0f}秒、Ctrl+Cで中断)")
            # 診断: フレーム保存フォルダ
            savedir = os.path.join(os.path.dirname(__file__), "eval_frames", key)
            os.makedirs(savedir, exist_ok=True)
            for f in os.listdir(savedir):
                os.remove(os.path.join(savedir, f))
            policy.reset(); pre.reset(); post.reset()
            t0 = time.time()
            FPS = 30.0  # 学習時と同じ制御周期
            n_steps = 0
            infer_times = []
            act_log = []
            while time.time() - t0 < args.seconds:
                tick = time.perf_counter()
                try:
                    obs = robot.get_observation()
                    obs_p = robot_obs_proc(obs)
                    frame = build_dataset_frame(features, obs_p, prefix=OBS_STR)
                    _ti = time.perf_counter()
                    with torch.inference_mode():
                        ob = prepare_observation_for_inference(copy(frame), device, task, robot.name)
                        ob = pre(ob)
                        act = policy.select_action(ob)
                        act = post(act)
                    infer_times.append(time.perf_counter() - _ti)
                    act = act.squeeze(0).cpu()
                    action_dict = {k: act[i].item() for i, k in enumerate(action_keys)}
                    act_log.append([action_dict[k] for k in action_keys])
                    processed = robot_action_proc((action_dict, obs))
                    robot.send_action(processed)
                    # 診断: 5ステップに1回カメラ保存
                    if n_steps % 5 == 0 and "overhead" in obs:
                        img = obs["overhead"]
                        cv2.imwrite(os.path.join(savedir, f"{n_steps:04d}.jpg"),
                                    cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                    n_steps += 1
                except RuntimeError as e:
                    if "Overload" in str(e):
                        m = re.search(r"id_=(\d)", str(e))
                        if m:
                            name = MOTOR_NAMES[int(m.group(1)) - 1]
                            try:
                                robot.bus.write("Torque_Enable", name, 0, normalize=False, num_retry=2)
                                time.sleep(0.3)
                                robot.bus.write("Torque_Enable", name, 1, normalize=False, num_retry=2)
                            except Exception:
                                pass
                        time.sleep(0.1)
                    else:
                        raise
                time.sleep(max(0.0, 1.0 / FPS - (time.perf_counter() - tick)))
            # 診断サマリ
            elapsed = time.time() - t0
            eff_fps = n_steps / elapsed if elapsed > 0 else 0
            mean_infer = 1000 * np.mean(infer_times) if infer_times else 0
            arr = np.array(act_log) if act_log else np.zeros((1, len(action_keys)))
            print(f"  [診断] 実効{eff_fps:.1f}fps (学習30fps) / 推論{mean_infer:.0f}ms/step / "
                  f"{n_steps}step / フレーム保存: {savedir}")
            print(f"  [診断] 各関節actionのレンジ(min..max):")
            for i, k in enumerate(action_keys):
                print(f"        {k}: {arr[:, i].min():.1f} .. {arr[:, i].max():.1f}")
            print("  実行終了。次の指示をどうぞ")
    except KeyboardInterrupt:
        print("\n中断しました。アームはその場で固定です")
    finally:
        robot.disconnect()
        print("disconnected")


if __name__ == "__main__":
    main()
