"""どのモーターを「動かす」とバスが死ぬかを1個ずつ特定する。
各モーターをその場で±小さく往復させ(±40tick≈3.5度)、直後に全員の生存確認。
❌が出た関節の配線区間が犯人(動いた時の振動で接触が切れる/ショート)。
アームの近くで見守りながら実行してください。
usage: python oyster_vla/find_move_killer.py
"""
import time

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = "/dev/cu.usbmodem5B7B0090111"
D = MotorNormMode.DEGREES
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
motors = {n: Motor(i + 1, "sts3215", D if n != "gripper" else MotorNormMode.RANGE_0_100) for i, n in enumerate(NAMES)}

bus = FeetechMotorsBus(port=PORT, motors=motors)
bus.connect(handshake=False)
print("connected\n")

def bus_alive():
    try:
        vals = bus.sync_read("Present_Position", normalize=False, num_retry=2)
        return len(vals) == 6
    except Exception:
        return False

print("ベースライン:", "OK" if bus_alive() else "NG")

killer = None
for n in NAMES:
    try:
        pos = int(bus.read("Present_Position", n, normalize=False, num_retry=2))
        bus.write("Goal_Position", n, pos, normalize=False, num_retry=2)
        bus.write("Torque_Enable", n, 1, normalize=False, num_retry=2)
        time.sleep(0.3)
        # ±40tickの小さい往復を2回
        for delta in [40, -40, 40, -40, 0]:
            bus.write("Goal_Position", n, pos + delta, normalize=False, num_retry=2)
            time.sleep(0.35)
        time.sleep(0.3)
        ok = bus_alive()
        print(f"  {n}: 動作テスト → バス {'OK' if ok else '❌死亡'}")
        if not ok:
            killer = n
            break
    except Exception as e:
        print(f"  {n}: エラー {str(e)[:70]} ← ❌ここが犯人候補")
        killer = n
        break

print("\n結果:", f"犯人 = {killer} 付近の配線/コネクタ(動くと切れる)" if killer else "単関節の小動作では再現せず → 複数関節同時 or 大きい動きが条件")
bus.disconnect(disable_torque=False)
