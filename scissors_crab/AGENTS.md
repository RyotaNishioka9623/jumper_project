# AGENTS.md — Scissors Crab（チョキしか出せないカニ）

このフォークで進めている制作プロジェクトの記録です。作業を始める前に必ず読み、決定事項や進捗が変わったら更新してください。
リポジトリ全体の作業ルール（公式）は、ルートの [`CLAUDE.md`](../CLAUDE.md) と [`AGENTS.md`](../AGENTS.md) にあります。

最終更新：2026-10-15

---

## 1. 目的と大会の要件

- **目的**：KingKong Technology の [Crab Robot Open-source Challenge 2026](https://beunlimited.me/en/events/crab-robot-challenge-2026) に応募し、Jumper 実機（100台配布）の獲得を目指す。応募は X への動画投稿で行う。
- **締切**：Round 1 は **2026-10-30**。選考は3〜4回あり、早く応募するほど有利。期間は 2026-09-30〜11-30。
- **投稿要件（海外枠）**：15秒より長い動画を X に投稿する。
  - ハッシュタグ：`#Jumper #CrabRobot #OpenSourceRobot`
  - メンション：`@KingKong Robotics`。**X 上の正確なハンドル名は未確認なので、投稿前に必ず確認する。**
- **審査**：視聴者の反応60%＋専門家審査40%。評価軸は外観（Beautiful）・動き（Playful）・技能（Useful）の3つ。どれか1つが突出すれば十分で、複数で優れると加点される。制作過程や失敗の共有も評価対象。
- **規約**：
  - 作品はオリジナルであること
  - 音楽の権利は自分で処理する（このプロジェクトでは楽曲を使わない）
  - 応募作品は KingKong に商用利用を含む利用許諾を与えることになる
  - Apache-2.0 を遵守する
- 詳細な分析は [docs/01_evaluation_criteria_and_plan.md](docs/01_evaluation_criteria_and_plan.md) を参照。

## 2. コンセプト（決定事項）

- **「チョキしか出せないカニ」**：ハサミなのでじゃんけんでチョキしか出せない、照れ屋のカニ。
  - 英語のフック：*"Everyone jokes that crabs can only throw scissors. So we trained a real 22-DoF crab robot to play rock-paper-scissors."*
- **路線**：本物の22自由度モデルで実装する。
  - Blender で振り付け（お手本）を作り、公式ツールキットの模倣強化学習で、物理シミュレーション上で再現させる。
  - 同じネタの 2D GIF を X の @jumpercrabsol が投稿しているが、**これは公式ではなく暗号資産トークンの宣伝アカウント**。メンションも引用もしない。
- **結果別のアニメーション3本**（いずれも共通の前半から始まる）：
  - 共通の前半（`janken_common.opening()`、112フレーム @30fps）：V字の素振り（キラキラ目、チョキチョキ2回）→ 握りこぶしで「じゃん・けん」→「ぽん！」でチョキ。**勝敗は「ぽん！」で決まるので、各結果は直後に反応する。**
  - **負け** `jumper.janken_lose`：ビクッ → 真顔（点の目、まばたきなし）で V のまま固まる → ゆっくり頭（体の前側）だけ下がる（約17°）→ ハサミが落ちて泣く（涙が流れる、ひっくひっく）。笑顔は出さない。
  - **勝ち** `jumper.janken_win`：ピョン → 両ハサミ V でバンザイ → 2回ジャンプ（0.2秒・49mm、放物線）→ 両手チョキチョキ（1回0.5秒）→ 我に返る → **両ハサミで顔を覆って照れる** → 右ハサミをずらしてチラ見 → また隠れる → ハサミを先に下ろしてから立ち姿勢へ戻り、にっこり。
  - **あいこ** `jumper.janken_draw`：同族のカニ同士。開閉なしの V で固まり、ビクッも驚きもない真顔のにらみ合いで「あいこでしょ」を繰り返す（1周36フレーム、チョキで始まりチョキで終わるので、何周でもループできる）。
- **目の表情**：公式の顔アニメーションと同じスタイル（黒地に水色、132×132／ディスプレイ）。表情は neutral, blink, serious, sad, cry, blank, surprised, happy, shy, sparkle の10種類。タイムラインは `scissors_crab/motions/janken_*.eyes.json`。

## 3. 動画の構成（決定事項・案）

- **背景**：公式 jumper-design の `home.map`（リビング）。出典を明記する（「scene: KingKong Robotics jumper-design」）。マップ作り自体は評価軸ではないので、公式素材で問題ない。
- **人**：Blender Studio の Human Base Meshes（CC0）の**女性**。淡い黄色のトップス、明るいデニム、白い靴下、ポニーテール。中腰で膝に手をついて覗き込み、「じゃん・けん」でこぶしを振り、「ぽん！」でかがんで手を出す（負けの回はグー、勝ちの回はパー）。
- **カメラ**：**人の左肩越しの低い位置から**撮る。カニの顔を正面に映し、人の顔は映さない（リアルな顔に表情がないと不気味になるため）。
- **照明**：午後の窓からの暖かい光＋補助光。色の変換は Standard（AgX にするとカニの赤が薄くなる）。
- **構成案（約40秒）**：
  1. つかみ：素振り。テロップ「チョキしか出せないカニ」
  2. じゃんけん → 負け → 泣く（顔のアップを挟む）
  3. 「もう一回！」→ 勝ち → ジャンプ → 照れ
  4. **照れているカニから、カメラが部屋の中を移動し、奥であいこを繰り返す2体へ**（1カットで描画）→ 何周か見せてフェードアウト（ちゃんちゃん♪）
  5. 締め：「Trained with the Jumper open-source toolkit」
- **テロップ**：フォントは M PLUS Rounded 1c（OFL）。言語（日本語のみ／英語併記）は未決定。
- **効果音**：効果音ラボ（商用可、クレジット不要、**ファイルの再配布は禁止**＝リポジトリに入れない）。使う15個と場面の対応は §6 を参照。
- **X 投稿**：英語の投稿を正式な応募にし（ハッシュタグとメンションを付ける）、日本語の投稿はその引用ポストにする。
- **サムネイル**：グーの手にチョキで挑む場面。
- **動画完成後（時間があれば）**：MediaPipe Hands で人の手のグー・チョキ・パーを判定し、カニが自動で反応するインタラクティブ版（技能の軸）。

## 4. パイプライン（コマンドは [README.md](README.md) にも記載）

```
Blender で振り付け（jumper_rig.blend にキーフレーム）
  → export_keyframes.py → motions/<名前>.keyframes.json
  → tools/keyframes_to_npz.py → tasks/jumper/janken_<結果>/media/janken_<結果>.npz
  → （確認）tools/preview_clip.py または blender/import_motion.py
  → Colab で学習（colab/scissors_crab_colab.ipynb）→ ダウンロードフォルダにバックアップ
  → scripts/play.py --checkpoint … --qpos-out rollout.npz（Mac で動きを記録）
  → tools/make_eyes.py（目の表情の連番画像）
  → blender/stage.py（背景＋カニ＋人＋照明）で描画
  → 編集（テロップ・効果音）→ 投稿
```

| ファイル | 役割 |
|---|---|
| `blender/build_rig.py` | 学習用 MJCF からリグを生成（FK 誤差0.0001mm）。顔パネルの目、`jumper_root["rest_z"]` |
| `blender/export_keyframes.py` | 関節角度（＋ジャンプの `lift`）を 100Hz で書き出す |
| `tools/keyframes_to_npz.py` | HOME への入り・戻り、静止接地ソルバで胴体姿勢を計算、`lift` の加算、急な傾き（150°/s超）を0.3秒かけて滑らかにする |
| `motions/janken_common.py` | 共通のポーズと前半、`mirror()`、`hop()`、`set_down()` |
| `motions/make_janken_{lose,win,draw}.py` | たたき台の生成（以後は `.blend` を直接編集してもよい） |
| `tasks/jumper/common/janken.py` | 環境設定の数値をクリップから計算 |
| `scripts/play.py --qpos-out` | （公式に追加）再生中の全状態を記録（`rl/mjrl/viewer/qpos_log.py`） |
| `tools/make_eyes.py` | 目の表情の描画、タイムラインから連番画像と 132px の実機用動画 |
| `blender/import_motion.py` | 動き＋目をリグに載せて描画（`--twin` で鏡写しの2台目、`--frames` で区間指定） |
| `blender/import_scene.py` | `.map` を背景として読み込む |
| `blender/build_human.py` / `pose_human.py` | 人の素体に骨格・服・目・髪を付ける／ポーズ（中腰、しゃがみ、グー・パー、2関節 IK） |
| `blender/stage.py` | 場面の組み立てと描画（人のじゃんけんはカニの前半に同期） |
| `colab/scissors_crab_colab.ipynb` | Colab 用ノートブック（公式のコピーで、初期値だけ変更） |

**Colab での学習手順**：ランタイムを接続解除して削除 → ノートブックを開き直す → GPU を選ぶ → `TASK` と `ITERATIONS` を設定 → すべてのセルを実行。`Pinned source commit:` が最新のコミットであることを確認する。
`ITERATIONS` は lose・draw が1500、win（ジャンプあり）が2500。

## 5. 現在の状況（2026-10-15）

| タスク | クリップを最後に変えたコミット | 学習 | 状態 |
|---|---|---|---|
| janken_lose | `c0e0b09`〜`1fb58d6` | 済（`1fb58d6`、1500回、収束） | 重み・記録・目は `renders/janken_lose/1fb58d6/`。関節の誤差は平均2.2° |
| janken_win | `007b26a`（ジャンプと終わり方の修正） | 未（ユーザーが Colab で実施中） | 学習結果待ち |
| janken_draw | `1fb58d6`（ビクッを削除） | 未（ユーザーが Colab で実施中） | 学習結果待ち |

- 学習結果はユーザーのダウンロードフォルダに届く（例：`~/Downloads/Jumper_lose/jumper-jumper-janken_lose-*/run/model_1499.pt`）。
- **効果音15個はユーザーが手動でダウンロードする**（サーバーが直リンクを拒否するため。回避はしない）。保存先は `scissors_crab/external/se/`。
- 次の作業：
  1. win・draw の描画
  2. 勝ち → カメラ移動 → あいこ2体のループ＆フェードの1カット
  3. 編集の仕組み（テロップ・効果音・カット割り）
  4. サムネイル
  5. 投稿文（日英）
  6. 公式 X アカウントのハンドル名の確認

## 6. 外部素材（`scissors_crab/external/`、Git の管理対象外）

| 素材 | 入手元 | ライセンス／注意 |
|---|---|---|
| `maps/home.map` | KingKongRobotics/jumper-design `library/maps/home.map` | シーン単体のライセンス表記なし。主催者の素材。出典を明記する |
| `human-base-meshes/…v1.4.1/human_base_meshes_bundle.blend` | blender.org の Asset Bundles（mirror.blender.org の zip、49MB） | CC0 |
| `fonts/mplus-rounded-1c/*.ttf` | google/fonts `ofl/mplusrounded1c`（Bold・ExtraBold・Black） | OFL |
| `se/*.mp3` | 効果音ラボ（ユーザーが手動で取得） | 商用可、クレジット不要、再配布禁止 |

効果音の場面対応：

- 前半：scissors1（素振り）、kira1（キラキラ）、pa1（じゃん・けん）、jean1（ぽん）
- 負け：shock2（ビクッ）、cute-sad1（うなだれる）、teardrop1（泣く）、tin1（締め）
- 勝ち：jump-anime1（ジャンプ）、cute-pose1（バンザイ）、surprise1（我に返る）、heart2（照れる）、blink1（チラ見）
- あいこ：sceneswitch2（カメラ移動）、chan-chan1（締め）

生成物は `scissors_crab/renders/`（Git の管理対象外）に置く。リグは `blender/build_rig.py`、人は `build_human.py`、背景は `import_scene.py` で再生成できる。

## 7. 作業上の約束事と注意点

- **コミットと push は許可済み**。コミットメッセージの末尾には `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` を付ける。リポジトリは public。
- **公式テストの既知の失敗**：`tests/test_posture.py::test_the_mirror_of_a_posture_is_the_posture_of_the_mirror` は上流側の数値誤差で失敗する。それ以外の全テストが通ることを確認する。
- **ruff**：上流のファイルには元から警告がある。自分で追加したファイルは警告ゼロに保つ。
- **シミュレーションの結果を、実機で検証したとは書かない。**
- **関節の符号**：
  - 腕（LF/RF）は J1 の符号が左右で同じで、J0・J2・J3・J4 は左右で反転する。脚は全関節が反転する。
  - グリッパー：RF_J4 は 0 で閉、1.5 で開（1.6 が機械的な上限）。
- **接地ソルバの限界**：胴体の姿勢は「静止して床に接地している」前提で計算する。
  - ハサミが床に着く・離れるときは傾きが一瞬で変わるので、ハサミを先に下ろす（`set_down`）。急な傾きは変換時に自動で滑らかにする。
  - ジャンプは `lift`（Blender でルートを持ち上げる）で表現する。
- **Blender 5.2**：`/Applications/Blender.app/Contents/MacOS/Blender`。
  - オブジェクトを結合（join）すると材質の番号がずれるので、材質はデータブロックで指定する。
  - 骨に親子付けしたオブジェクトはずれることがあったので、目やポニーテールはメッシュに結合し、頭の骨に重み1で固定している。
- **シェル**：zsh は変数をスペースで分割しない。複数の引数を変数で渡すときは `${=VAR}` を使う。また、`bash -c` 経由のスクリプトは安全確認で止まることがある。
- **ダウンロード**：新しいファイルを取得する前に、ユーザーの許可（ファイル名・入手元・サイズ）を得る。
