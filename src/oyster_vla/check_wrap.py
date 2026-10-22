"""トルクOFFのまま全関節の生位置を読み、継ぎ目(4095↔0の飛び)が可動範囲内にあるか自動検出する。
関節名を知らなくてOK。アームを手で持って、全部の部分をあちこち大きく動かすだけ。
モーターにトルクをかけないのでスラムは絶対起きない。
usage: python oyster_vla/check_wrap.py
"""
import time

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = "/dev/cu.usbmodem5B7B0090111"
D = MotorNormMode.DEGREES
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
JP = {"shoulder_pan": "1土台旋回", "shoulder_lift": "2肩上下", "elbow_flex": "3肘",
      "wrist_flex": "4手首曲げ", "wrist_roll": "5手首回転", "gripper": "6指"}
motors = {n: Motor(i + 1, "sts3215", D if n != "gripper" else MotorNormMode.RANGE_0_100) for i, n in enumerate(NAMES)}

bus = FeetechMotorsBus(port=PORT, motors=motors)
bus.connect(handshake=False)
for n in NAMES:
    try:
        bus.write("Torque_Enable", n, 0, normalize=False, num_retry=2)
    except Exception:
        pass

SECONDS = 45
print(f"全トルクOFF。これから{SECONDS}秒間、アームの色んな所を手で持って")
print("大きくガチャガチャ動かしてください(全部の関節を端から端まで)。\n")

prev = {}
jumped = set()
moved = set()
mins = {}
maxs = {}
t0 = time.time()
last = 0
while time.time() - t0 < SECONDS:
    try:
        vals = bus.sync_read("Present_Position", normalize=False, num_retry=2)
    except Exception:
        continue
    for n in NAMES:
        if n not in vals:
            continue
        v = vals[n]
        mins[n] = min(mins.get(n, v), v)
        maxs[n] = max(maxs.get(n, v), v)
        if n in prev:
            d = abs(v - prev[n])
            if d > 3:
                moved.add(n)
            if d > 1500:  # 継ぎ目跨ぎ
                if n not in jumped:
                    print(f"  ⚠️ {JP[n]}: 継ぎ目ジャンプ {prev[n]}→{v}")
                jumped.add(n)
        prev[n] = v
    now = time.time() - t0
    if now - last > 2.0:
        active = [JP[n] for n in NAMES if n in moved]
        print(f"  [{now:4.0f}s] 動かせた関節: {' '.join(active) if active else '(まだ無し)'}")
        last = now
    time.sleep(0.04)

print("\n--- 結果 ---")
# wrist_roll(5)は全周回転が正常なので継ぎ目跨ぎOK。他は問題
bad = sorted(j for j in jumped if j != "wrist_roll")
notmoved = [JP[n] for n in NAMES if n not in moved]
if notmoved:
    print(f"※ 動かせてない関節: {' '.join(notmoved)} (動かせてない関節は判定不能)")
if bad:
    print(f"❌ 継ぎ目が範囲内: {[JP[n] for n in bad]} → キャリブやり直し必須")
else:
    print("✅ (動かした関節では)継ぎ目ジャンプなし → このまま進めてOK")
bus.disconnect(disable_torque=False)
