"""Phase 2.5: 掴んだ状態の判定テスト。

アームを判定ポーズに動かし、あなたが手でトマトをグリッパに挟ませ、
その状態の写真を撮ってVLM判定を実行。写真と判定結果で「見えてるか」を確認する。

usage: python tomato_sort/check_inspect.py
繰り返し: 何個でも連続でテストできる(qで終了)
"""
import base64
import json
import os
import time

import cv2

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig

HERE = os.path.dirname(__file__)
PORT = "/dev/cu.usbmodem5B7B0090111"
VLM_MODEL = "claude-sonnet-5"
LOG_DIR = os.path.join(HERE, "logs")

import sys
sys.path.insert(0, HERE)
from tomato_sort import VLM_PROMPT, goto, judge_with_vlm, set_gripper  # 再利用

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY を設定してください")
    import anthropic
    client = anthropic.Anthropic()

    with open(os.path.join(HERE, "poses.json")) as f:
        poses = json.load(f)
    if "inspect" not in poses:
        raise SystemExit("先に judge ポーズを登録してください: python tomato_sort/capture_pose.py inspect")
    gripper_open = poses["home"]["gripper"]
    os.makedirs(LOG_DIR, exist_ok=True)

    rcfg = SOFollowerRobotConfig(
        port=PORT,
        cameras={"overhead": OpenCVCameraConfig(index_or_path=0, width=640, height=480, fps=30)},
        disable_torque_on_disconnect=False,
    )
    rcfg.id = "my_follower"
    robot = SOFollower(rcfg)
    robot.connect()
    print("判定ポーズへ移動します...")
    goto(robot, poses["inspect"], duration=2.5)
    set_gripper(robot, gripper_open)

    n = 0
    while True:
        ans = input("\nトマトをグリッパの指の間に持っていって Enter (qで終了): ")
        if ans.strip().lower() == "q":
            break
        n += 1
        # キャリブレーション基準でゆっくり閉じる (正規化値: 0=閉じ切り, 100=全開)
        print("  グリッパを閉じます(トマトは軽く支えたままで)")
        try:
            g = float(robot.bus.read("Present_Position", "gripper", normalize=True, num_retry=2))
        except Exception:
            g = 60.0
        while g > 2:
            g -= 2  # 小刻みに
            try:
                robot.bus.write("Goal_Position", "gripper", g, normalize=True, num_retry=1)
                time.sleep(0.10)
                c = robot.bus.sync_read("Present_Current", normalize=False, num_retry=1)["gripper"]
                if c > 15:  # ~100mA: 触れたら即停止(トマトを潰さない)
                    g += 2  # 少し緩めて保持
                    robot.bus.write("Goal_Position", "gripper", g, normalize=True, num_retry=1)
                    print(f"  掴みました (電流{c*6.5:.0f}mA, やさしく保持)")
                    break
            except Exception:
                pass
        time.sleep(0.5)
        print("  手を離してください。2秒後に撮影します")
        time.sleep(2.0)

        obs = robot.get_observation()
        img = obs["overhead"]
        path = os.path.join(LOG_DIR, f"inspect_test_{n}.jpg")
        crop_path = os.path.join(LOG_DIR, f"inspect_test_{n}_crop.jpg")
        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        try:
            verdict = judge_with_vlm(client, img, crop_save_path=crop_path)
            print(f"  VLM判定: {verdict}")
        except Exception as e:
            print(f"  VLM呼び出し失敗: {str(e)[:100]}")
        print(f"  画像: {path}")
        set_gripper(robot, gripper_open)
        print("  (グリッパを開きました。トマトを受け取ってください)")

    print("終了。アームは判定ポーズのまま固定です")
    robot.disconnect()


if __name__ == "__main__":
    main()
