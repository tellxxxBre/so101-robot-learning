"""m5(wrist_roll)の過負荷ラッチをソフトで解除する。
アームは落とさない(disconnect時 disable_torque=False)。腕も動かさない(トルク再有効化のみ)。
usage: python oyster_vla/clear_m5_overload.py
"""
import time

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = "/dev/cu.usbmodem5B7B0090111"
D = MotorNormMode.DEGREES
motors = {
    "shoulder_pan": Motor(1, "sts3215", D),
    "shoulder_lift": Motor(2, "sts3215", D),
    "elbow_flex": Motor(3, "sts3215", D),
    "wrist_flex": Motor(4, "sts3215", D),
    "wrist_roll": Motor(5, "sts3215", D),
    "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
}
bus = FeetechMotorsBus(port=PORT, motors=motors)
bus.connect(handshake=False)
print("connected (handshake=False)")
ok = False
for attempt in range(4):
    try:
        # Torque_Enable 0->1 トグルでラッチ解除(m5のみ触る=他関節のトルク状態は保持)
        bus.write("Torque_Enable", "wrist_roll", 0, normalize=False, num_retry=3)
        time.sleep(0.5)
        bus.write("Torque_Enable", "wrist_roll", 1, normalize=False, num_retry=3)
        time.sleep(0.5)
    except Exception as e:
        print(f"  attempt{attempt} toggle err: {str(e)[:80]}")
    r = bus.ping("wrist_roll", num_retry=3, raise_on_error=False)
    print(f"  attempt{attempt}: m5 ping = {r}")
    if r is not None:
        ok = True
        break
    time.sleep(0.5)
bus.disconnect(disable_torque=False)  # ★アーム保持(落とさない)
print("RESULT:", "m5復帰OK" if ok else "m5まだ応答せず→電源再投入が必要かも")
