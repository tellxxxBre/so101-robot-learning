#!/bin/bash
# セッションA(パイロット): 牡蠣→箱、まず10本。パイプライン疎通確認用。新規データセット作成。
# 疎通OKなら後で resume で本数を足せる(この10本は捨てない)。
# 実行: bash oyster_vla/record_A.sh  （自分のターミナルで。キー操作が要るため）
cd /Users/terunobuakiyama/practice/so101-blog
.venv/bin/lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B7B0090111 \
  --robot.id=my_follower \
  --robot.cameras="{overhead: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --robot.disable_torque_on_disconnect=false \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5B7B0094901 \
  --teleop.id=my_leader \
  --dataset.repo_id=local/so101_oyster_vla_20260920 \
  --dataset.single_task="pick up the white oyster plush and put it in the box" \
  --dataset.num_episodes=10 \
  --dataset.fps=30 \
  --dataset.episode_time_s=45 \
  --dataset.reset_time_s=15 \
  --dataset.push_to_hub=false
