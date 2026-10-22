"""新品サーボ(工場出荷ID=1)にID=2を書き込む。
前提: バス上に新サーボ1個だけを接続していること(他のモーターは全部切り離す)。
usage: python oyster_vla/set_servo_id2.py
"""
import time

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = "/dev/cu.usbmodem5B7B0090111"

# まずスキャンして現状確認
res = FeetechMotorsBus.scan_port(PORT)
found = set()
for ids in res.values():
    found.update(ids)
print("検出ID:", sorted(found))

if found == {1}:
    pass  # 期待通り: 新品(ID1)が1個だけ
elif found == {2}:
    raise SystemExit("✅ すでにID=2です。書き込み不要。次の工程へ")
elif len(found) == 0:
    raise SystemExit("❌ 何も見つかりません。配線と電源を確認してください")
else:
    raise SystemExit(f"❌ 想定外のID構成 {sorted(found)}。新サーボ1個だけを接続した状態にしてください(他のモーターが繋がってる疑い)")

# ID1のモーターとして接続し、IDを2に書き換え
bus = FeetechMotorsBus(port=PORT, motors={"new_servo": Motor(1, "sts3215", MotorNormMode.DEGREES)})
bus.connect(handshake=False)
try:
    bus.write("Torque_Enable", "new_servo", 0, normalize=False, num_retry=3)
    time.sleep(0.2)
    # Feetech: IDレジスタはEEPROM。Lockを解除して書き込み
    try:
        bus.write("Lock", "new_servo", 0, normalize=False, num_retry=3)
        time.sleep(0.2)
    except Exception:
        pass  # Lockレジスタが無い/不要な場合
    bus.write("ID", "new_servo", 2, normalize=False, num_retry=3)
    time.sleep(0.3)
finally:
    bus.disconnect(disable_torque=False)

# 確認スキャン
res2 = FeetechMotorsBus.scan_port(PORT)
found2 = set()
for ids in res2.values():
    found2.update(ids)
print("書き込み後の検出ID:", sorted(found2))
print("✅ ID=2 書き込み成功！次: 電源を切って機械交換へ" if found2 == {2} else "❌ 失敗。出力を報告してください")
