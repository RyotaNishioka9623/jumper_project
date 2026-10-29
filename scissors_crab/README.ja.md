# Scissors Crab ✂️🦀 — チョキしか出せないカニ

[English](README.md) | **日本語**

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
| `scissors_crab/tools/make_eyes.py` | 目の表情を描き、タイムラインに沿って連番画像と実機用の動画にする |
| `scissors_crab/blender/import_motion.py` | 記録した動きと表情をリグに読み込み、Blenderで描画する |
| `scripts/play.py --qpos-out` | （公式スクリプトに追加）再生中の全状態を毎ステップ記録する（`rl/mjrl/viewer/qpos_log.py`） |
| `scissors_crab/assets/eyes/` | 各表情の静止画（リグの初期表示用） |
| `tasks/jumper/common/janken.py` | じゃんけんタスクの共通設定。報酬などの数値はクリップから計算する |
| `tasks/jumper/common/janken_jump.py` | ジャンプの区間だけ評価を変える仕組み（`janken_win_jump` 用） |
| `tasks/jumper/janken_*/` | 結果ごとのタスク（`janken_lose`、`janken_win`、`janken_win_hop`、`janken_win_jump`、`janken_draw`） |
| `scissors_crab/motions/` | 振り付けの `.blend`、そこから書き出したキーフレーム表、目の表情のタイムライン（`.eyes.json`） |
| `scissors_crab/motions/make_janken_*.py` | 結果ごとのたたき台を `.blend` に生成する。前半は `janken_common.py` で共有（以後は `.blend` を直接編集する） |
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

Colabでは [scissors_crab/colab/scissors_crab_colab.ipynb](colab/scissors_crab_colab.ipynb) を使います。公式ノートブックのコピーで、このリポジトリとじゃんけんタスクが初期値になっています。
[Colabで開く](https://colab.research.google.com/github/RyotaNishioka9623/jumper_project/blob/main/scissors_crab/colab/scissors_crab_colab.ipynb)

## 動画にする（表情つき）

学習した動きはシミュレーターで記録し、Blenderで目の表情をつけて描画します。

```bash
# 1. 学習した方策の動きを記録する（胴体と全関節の状態 qpos を毎ステップ保存）
.venv/bin/python scripts/play.py --task jumper.janken_lose --headless --num_envs 1 \
    --steps 290 --qpos-out scissors_crab/renders/janken_lose/rollout.npz

# 2. 目の表情をタイムラインに沿って作る（黒地に水色、実機ディスプレイと同じ132×132の動画も出力）
.venv/bin/python scissors_crab/tools/make_eyes.py scissors_crab/motions/janken_lose.eyes.json \
    --duration 5.8 --out scissors_crab/renders/janken_lose/eyes

# 3. Blenderに読み込んで描画する
blender scissors_crab/blender/jumper_rig.blend --background \
    --python scissors_crab/blender/import_motion.py -- \
    scissors_crab/renders/janken_lose/rollout.npz \
    --eyes scissors_crab/renders/janken_lose/eyes \
    --save scissors_crab/renders/janken_lose/scene.blend \
    --render scissors_crab/renders/janken_lose/janken_lose.mp4
```

`import_motion.py` には、タスクのクリップ（`media/*.npz`）も渡せます。学習前のお手本をBlenderで確認するときに使います。
`--twin 0.8` を付けると、鏡写しの2台目が0.8m先に向かい合って同じ動きをします（あいこの場面）。

表情の種類は `neutral`、`blink`、`serious`、`sad`、`surprised`、`happy`、`shy`、`sparkle` です。
`make_eyes.py --sheet sheet.png` で一覧を確認できます。タイムラインは `{"fps": 30, "keys": [[秒, "表情"], ...]}` 形式で、`neutral` の間は自動でまばたきします。

## 本番の動画を作る

背景・人・照明つきのカットを 1920×1080 で描画し、テロップと効果音を載せて1本にします。
背景（`home_set.blend`）と人（`human_female.blend`）、効果音・フォントは `renders/` と `external/` にあり、Git には入れていません。

```bash
L=scissors_crab/renders/janken_lose/1fb58d6
W=scissors_crab/renders/janken_win_jump/a1f8d50
D=scissors_crab/renders/janken_draw/97f28f8
H=scissors_crab/renders/sets/human_female.blend
OUT=scissors_crab/renders/final
B=/Applications/Blender.app/Contents/MacOS/Blender

# 1. 負け：人の肩越し（描画フレーム1〜230）
$B --background --factory-startup scissors_crab/renders/sets/home_set.blend \
    --python scissors_crab/blender/stage.py -- $L/rollout.npz --eyes $L/eyes --human $H \
    --throw rock --frames 1 230 --render $OUT/lose_ots.mp4 --size 1920 1080

# 2. 負け：泣き顔のアップ（200〜338）
$B --background --factory-startup scissors_crab/renders/sets/home_set.blend \
    --python scissors_crab/blender/stage.py -- $L/rollout.npz --eyes $L/eyes --human $H \
    --throw rock --camera 0.55 -0.24 0.22 --look-at 0.03 0.0 0.085 --lens 45 \
    --frames 200 338 --render $OUT/lose_close.mp4 --size 1920 1080

# 3. 勝ち（win_jump）から締めまでの1カット（70〜480）
$B --background --factory-startup scissors_crab/renders/sets/home_set.blend \
    --python scissors_crab/blender/ending.py -- --win $W/rollout.npz --win-eyes $W/eyes \
    --draw $D/rollout.npz --draw-eyes $D/eyes --human $H \
    --frames 70 480 --render $OUT/win_ending.mp4 --size 1920 1080

# 3b. 同じカットの302以降を、2秒延ばして描く（題名を読ませるため。302〜540）
$B --background --factory-startup scissors_crab/renders/sets/home_set.blend \
    --python scissors_crab/blender/ending.py -- --win $W/rollout.npz --win-eyes $W/eyes \
    --draw $D/rollout.npz --draw-eyes $D/eyes --human $H --length 540 \
    --frames 302 540 --render $OUT/win_ending_rest.mp4 --size 1920 1080

# サムネイル：「ぽん！」直後（124）、拳の後ろからカニの顔を見る1枚
$B --background --factory-startup scissors_crab/renders/sets/home_set.blend \
    --python scissors_crab/blender/stage.py -- $L/rollout.npz --eyes $L/eyes --human $H \
    --throw rock --camera 0.66 -0.44 0.26 --look-at 0.14 -0.07 0.27 --lens 26 \
    --frames 124 124 --render $OUT/thumbnail.mp4 --size 1920 1080
ffmpeg -i $OUT/thumbnail.mp4 -frames:v 1 $OUT/thumbnail.png

# 4. 編集リストを作り（テロップと効果音の時刻は描画フレームから計算）、1本にする
.venv/bin/python scissors_crab/edit/make_scissors_crab.py
.venv/bin/python scissors_crab/tools/edit.py scissors_crab/edit/scissors_crab.json \
    --out $OUT/scissors_crab.mp4
```

テロップや効果音のタイミングを変えるときは `edit/make_scissors_crab.py` を直して 4. だけやり直します（描画のやり直しは不要）。

## カメラでじゃんけん（MediaPipe、Mac）

Mac のカメラで人の手（グー・チョキ・パー）を MediaPipe で読み取り、学習済みの3つの方策（負け・勝ち・あいこ）がその場でシミュレーションのカニを動かします。カニはチョキしか出せないので、人がグーなら負け、パーなら勝ち、チョキか手が見えないときはあいこで、「あいこでしょ」の「しょ」ごとにもう一度出せます。

```bash
# 初回だけ：MediaPipe（.venv に）と、Google 公式のジェスチャー認識モデル（8.4MB、Git 管理外）
.venv/bin/python -m pip install mediapipe==1.1.1
mkdir -p scissors_crab/external/models
curl -L -o scissors_crab/external/models/gesture_recognizer.task \
    https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

# 遊ぶ（スペースで開始、r / p / s で手を指定、q で終了）
.venv/bin/python scissors_crab/interactive/janken_cam.py

# 画面ごと録画する（デモ動画用）
.venv/bin/python scissors_crab/interactive/janken_cam.py --record scissors_crab/renders/live/demo.mp4

# 録画を X 用（H.264）にし、待ち時間を切ってタイトルを付けた投稿用動画にする
ffmpeg -i scissors_crab/renders/live/demo.mp4 -c:v libx264 -pix_fmt yuv420p -crf 20 \
    -movflags +faststart scissors_crab/renders/live/demo_x.mp4
.venv/bin/python scissors_crab/edit/make_live_demo.py
.venv/bin/python scissors_crab/tools/edit.py scissors_crab/edit/live_demo.json \
    --out scissors_crab/renders/live/live_demo.mp4

# カメラなしで確認する（台本どおりに手を出す）
.venv/bin/python scissors_crab/interactive/janken_cam.py --no-camera --headless \
    --script "start@0.5,rock@1.5" --seconds 10 --record check.mp4
```

- 初めてカメラを使うとき、macOS がターミナルアプリにカメラの許可を求めます（システム設定 → プライバシーとセキュリティ → カメラ）。
- **判定のタイミング**：「ぽん」（「しょ」）の瞬間はまだ手を出している途中のことが多いので、その**0.2〜0.5秒後**の手の多数決で判定し、0.5秒後に結果を出します。その間カニはチョキで構えて待ちます。`--read-from 0.3 --decide-at 0.6` のように秒数を変えられます。
- カニの目は，Blender の動画と同じく**顔パネルの丸い画面2つに表示**します（位置は `blender/build_rig.py` と同じ）．ハサミで顔を隠すと目も隠れます．
- 方策・目の連番は `renders/` の学習結果（負け `janken_lose/1fb58d6`、勝ち `janken_win_jump/a1f8d50`、あいこ `janken_draw/97f28f8`）を使います。
- 「ぽん」と「しょ」の瞬間に、動いている環境の物理状態（関節・胴体の位置と速度、直前の指令）を、結果に応じた方策の環境へ引き継ぎます。3つのクリップは前半が同じなので、カニは今の姿勢のまま続けて反応します（録画の再生ではありません）。

## 注意

- 動画はシミュレーションの映像です。実機での動作は検証していません。
- 変換時の胴体姿勢は、常に床に接地している前提で計算します。空中に跳ぶ動きは、Blender でルート（`jumper_root`）を持ち上げた量（`lift`）を足して表現します。
