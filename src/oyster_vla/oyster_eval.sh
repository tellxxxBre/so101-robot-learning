#!/bin/bash
# 言語切り替えテスト: 学習済みSmolVLAが"指示に従って"動くか。ポリシーが腕を動かす(テレオペ不要)。
# usage: bash oyster_vla/oyster_eval.sh box|bow|snack
# 同じシーン(牡蠣＋赤袋を机に置く)で、引数を変えて3回試し、行動が変わるか見る。
cd /Users/terunobuakiyama/practice/so101-blog
case "$1" in
  box)   TASK="pick up the white oyster plush and put it in the box"; ID=box;;
  bow)   TASK="pick up the white oyster plush and make it bow"; ID=bow;;
  snack) TASK="pick up the red snack bag and put it in the box"; ID=snack;;
  *) echo "usage: bash oyster_vla/oyster_eval.sh box|bow|snack"; exit 1;;
esac
echo "指示: $TASK"
.venv/bin/lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/cu.usbmodem5B7B0090111 \
  --robot.id=my_follower \
  --robot.cameras="{overhead: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --robot.disable_torque_on_disconnect=false \
  --policy.path=outputs/oyster_smolvla/050000/pretrained_model \
  --policy.device=mps \
  --dataset.repo_id=local/oyster_eval_$ID \
  --dataset.single_task="$TASK" \
  --dataset.num_episodes=2 \
  --dataset.fps=30 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=10 \
  --dataset.push_to_hub=false
