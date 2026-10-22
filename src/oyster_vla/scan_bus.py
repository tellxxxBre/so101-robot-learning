"""モーターバスをスキャンして、検出できるモーターIDを表示する。
腕は一切動かさない(pingのみ)。
usage: python oyster_vla/scan_bus.py [follower|leader]  (省略時=follower)
"""
import sys

from lerobot.motors.feetech import FeetechMotorsBus

FOLLOWER = "/dev/cu.usbmodem5B7B0090111"
LEADER = "/dev/cu.usbmodem5B7B0094901"
which = sys.argv[1] if len(sys.argv) > 1 else "follower"
PORT = LEADER if which == "leader" else FOLLOWER
print(f"スキャン対象: {which} ({PORT})")
EXPECTED = {1: "shoulder_pan", 2: "shoulder_lift", 3: "elbow_flex",
            4: "wrist_flex", 5: "wrist_roll", 6: "gripper"}

res = FeetechMotorsBus.scan_port(PORT)
print("scan結果 (baudrate: 見つかったID):", res)
found = set()
for ids in res.values():
    found.update(ids)
print("\n検出:", sorted(found))
missing = [i for i in EXPECTED if i not in found]
if missing:
    for m in missing:
        print(f"  ❌ 欠落: ID {m} ({EXPECTED[m]})")
else:
    print("  ✅ 全6モーター検出OK")
