# Scissors Crab ✂️🦀 — チョキしか出せないカニ

*Everyone jokes that crabs can only throw scissors. So we trained a real 22-DoF crab robot to play rock-paper-scissors.*

[Jumper](https://github.com/KingKongRobotics/jumper) の [Crab Robot Open-source Challenge](https://beunlimited.me/en/events/crab-robot-challenge-2026) に向けた制作です。
じゃんけんでチョキしか出せない照れ屋のカニとして、Jumperに次のリアクションを覚えさせます。

- グーに負けたら、しゅんとする
- パーに勝ったら、喜んだあと照れて顔を隠す

振り付けはBlenderのキーフレームで作り、公式ツールキットの模倣強化学習で学習させます。

このリポジトリは [KingKongRobotics/jumper](https://github.com/KingKongRobotics/jumper) の履歴を引き継いでいます（Apache-2.0）。追加した部分は以下の通りです。

| パス | 内容 |
|---|---|
| `scissors_crab/blender/build_rig.py` | 学習用モデル `assets/jumper/jumper.xml` から、アニメーション用のリグをBlenderに生成する |
| `scissors_crab/blender/export_keyframes.py` | リグに付けた関節アニメーションを、キーフレーム表（`.keyframes.json`）として書き出す |
| `scissors_crab/tools/keyframes_to_npz.py` | キーフレーム表を学習用のクリップ（`.npz`）に変換する |
| `scissors_crab/tools/preview_clip.py` | 学習前に、クリップをMuJoCoで再生して動画にする |
| `tasks/jumper/common/janken.py` | じゃんけんタスクの共通設定。報酬などの数値はクリップから計算する |
| `tasks/jumper/janken_*/` | 結果ごとのタスク（`janken_lose` など） |
| `scissors_crab/motions/` | 振り付けの `.blend` と、そこから書き出したキーフレーム表 |
| `scissors_crab/docs/` | 評価基準の整理と制作計画 |

## 振り付けから学習までの流れ

前提：Python 3.10〜3.13 で `pip install -e .` 済みの `.venv`（公式の [PROJECT_GUIDE](../docs/PROJECT_GUIDE.md) を参照）と、Blender 4.2 以降。

```bash
# 1. リグを生成する（初回とモデルの更新時のみ）
blender --background --python scissors_crab/blender/build_rig.py
```

2\. `scissors_crab/blender/jumper_rig.blend` を開き、`scissors_crab/motions/<名前>.blend` として別名で保存する。
各関節（`RF_J1` など）を、それぞれの回転軸まわりに回してキーフレームを付ける。

- 1フレーム目は立ち姿勢（HOME）
- 関節の可動範囲は、学習用モデルと同じ値に制限してある
- 胴体は固定されたまま。実際の胴体の位置と傾きは、変換時に足の接地から計算される

```bash
# 3. キーフレーム表を書き出す
blender scissors_crab/motions/janken_lose.blend --background \
    --python scissors_crab/blender/export_keyframes.py

# 4. 学習用クリップに変換する（HOMEからの入りと戻りを付け、胴体の姿勢を計算する）
.venv/bin/python scissors_crab/tools/keyframes_to_npz.py \
    scissors_crab/motions/janken_lose.keyframes.json --task janken_lose

# 5. 学習前に動きを確認する
.venv/bin/python scissors_crab/tools/preview_clip.py \
    tasks/jumper/janken_lose/media/janken_lose.npz --out preview.mp4

# 6. 学習する（MacのCPUは動作確認用。本番はColabのGPUで回す）
.venv/bin/python scripts/train.py --task jumper.janken_lose \
    --backend native --device cpu --num_envs 64 --max-iterations 5
```

Colabでは、公式の [Colabノートブック](../docs/COLAB.md) で次のように設定します。

- `REPOSITORY_URL`：このリポジトリ
- `TASK`：`jumper.janken_lose` など

## 注意

- 動画はシミュレーションの映像です。実機での動作は検証していません。
- 変換時の胴体姿勢は、常に床に接地している前提で計算します。空中に跳ぶ動きは表現できません。
