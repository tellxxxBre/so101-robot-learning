# 環境構築ログ（2026-08-02）

## 環境
- macOS 26.1（Apple Silicon / arm64）
- conda 26.1.1（/opt/anaconda3）
- ffmpeg 8.1（Homebrew導入済み）

## 手順（実際に実行したコマンド）

### 1. Conda環境の作成
```bash
conda create -y -n lerobot python=3.10
conda activate lerobot
```

### 2. LeRobotのインストール（Feetechサーボ対応込み）
```bash
pip install 'lerobot[feetech]'
```
- SO-101のサーボはFEETECH STS3215なので `[feetech]` エクストラが必須
- 所要約2分。torch 2.10.0 / torchvision 0.25.0 / feetech-servo-sdk 1.0.0 など一式が入る

### 3. 動作確認
```bash
python -c "import lerobot; print(lerobot.__version__)"
# => 0.4.4（2026-08-02時点のPyPI最新）
ls $(dirname $(which python)) | grep lerobot
# => lerobot-find-port, lerobot-setup-motors, lerobot-calibrate,
#    lerobot-teleoperate, lerobot-record, lerobot-train など16コマンド
```

## ハマりどころ
1. **別プロジェクトのvenvが環境を乗っ取る**: 他のPythonプロジェクトのvenvが有効なシェルから作業すると、`conda activate`しても`python`がvenv側（3.13）を指したままになることがある。`which python`で`/opt/anaconda3/envs/lerobot/bin/python`を指しているか必ず確認。おかしければ先に`deactivate`する
2. バージョン表記の混乱: LeRobotはGitHubのドキュメントとPyPIのバージョン番号が揃っていないことがある。pipで入る最新は0.4.4（2026-08-02時点）

## 次の工程
- サーボID設定（`lerobot-setup-motors`）: 組み立て**前**にやる。ドライバーボード+USB+電源+サーボだけでできる（ネジ止め不要）
- リーダー用サーボはトルク違い（19kg×1 / 16kg×2 / 14.4kg×3）で取付位置が決まっているため、ID設定時にマスキングテープでラベリングする
