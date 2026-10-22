#!/bin/bash
# v2本番 タスクB: 牡蠣→お辞儀。同じデータセットに追記(30本)。
# distractor(青ティッシュも机に置く)+配置シャッフルを毎回やること。
# n=保存, r=録り直し。リセット中はキー触らない。
# 実行: bash oyster_vla/record_v2_B_oyster_bow.sh
cd /Users/terunobuakiyama/practice/so101-blog
.venv/bin/lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B7B0090111 \
  --robot.id=my_follower \
  --robot.cameras="{overhead: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG}}" \
  --robot.disable_torque_on_disconnect=false \
  --teleop.type=so101_leader \
  --teleop.port=/dev/cu.usbmodem5B7B0094901 \
  --teleop.id=my_leader \
  --dataset.repo_id=local/so101_oyster_v2_2cam \
  --dataset.root=/Users/terunobuakiyama/.cache/huggingface/lerobot/local/so101_oyster_v2_2cam_20260923_003020 \
  --dataset.single_task="pick up the white oyster plush and make it bow" \
  --dataset.num_episodes=29 \
  --dataset.fps=30 \
  --dataset.episode_time_s=45 \
  --dataset.reset_time_s=15 \
  --dataset.push_to_hub=false \
  --dataset.rgb_encoder.vcodec=h264_videotoolbox \
  --resume=true
