#!/bin/bash
# v2パイロット: 2カメラ(俯瞰+手首)で牡蠣→箱を3本だけ録る。検証用。
# OKなら resume で本番(各40本)へ拡張していく。
# 実行: bash oyster_vla/record_v2_pilot.sh
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
  --dataset.repo_id=local/test_overhead_only \
  --dataset.single_task="pick up the white oyster plush and put it in the box" \
  --dataset.num_episodes=1 \
  --dataset.fps=30 \
  --dataset.episode_time_s=45 \
  --dataset.reset_time_s=15 \
  --dataset.push_to_hub=false
