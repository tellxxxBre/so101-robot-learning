"""どのモーターのトルクONがバスを殺すかを1個ずつ特定する。
モーターを1つずつトルクON→全員に返事があるか確認→NG が出た所が犯人(その配線/コネクタ/電源区間が弱い)。
腕は動かさない(現在位置を保持させるだけ)。終了時は全モータートルクOFFにしない(落下防止のため保持)。
usage: python oyster_vla/find_torque_killer.py
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
print("connected (handshake=False)\n")

def bus_alive():
    try:
        vals = bus.sync_read("Present_Position", normalize=False, num_retry=2)
        return len(vals) == 6
    except Exception:
        return False

print("ベースライン(全トルクOFF状態)での読み取り:", "OK" if bus_alive() else "NG ← トルク以前に読めない")

killer = None
for n in NAMES:
    try:
        # 現在位置を目標にしてから保持トルクON(動かない)
        pos = bus.read("Present_Position", n, normalize=False, num_retry=2)
        bus.write("Goal_Position", n, int(pos), normalize=False, num_retry=2)
        bus.write("Torque_Enable", n, 1, normalize=False, num_retry=2)
        time.sleep(0.6)
        ok = bus_alive()
        print(f"  {n}: トルクON → バス {'OK' if ok else '❌死亡'}")
        if not ok:
            killer = n
            break
    except Exception as e:
        print(f"  {n}: エラー {str(e)[:70]} ← ここが怪しい")
        killer = n
        break

print("\n結果:", f"犯人candidate = {killer} (この関節の配線/コネクタ/電源区間を点検)" if killer else "全モータートルクONでもバス生存 → この方法では再現せず(複合負荷か動作時のみ)")
bus.disconnect(disable_torque=False)
