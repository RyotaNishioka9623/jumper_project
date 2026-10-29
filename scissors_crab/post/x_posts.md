# X の投稿文（下書き）

無料プランは1投稿280字まで（全角は2字、URL は一律23字で数える）。数え直しは
`python scissors_crab/tools/x_length.py scissors_crab/post/x_posts.md`。

- **本投稿（英語）を正式な応募**にする。動画・ハッシュタグ・メンションはここに付ける。
- 作り方と「面白い失敗」は、本投稿への**返信のスレッド**で続ける（応募要項に「アイデア、試行錯誤、面白い失敗の共有も入賞のチャンスを広げる」とある）。
- 日本語は、本投稿の**引用ポスト**にする。
- **前提（チョキしか出せない）は投稿文でも言わない**。動画の最後の答え合わせを先に明かさないため。

## 投稿の前に確認すること

1. **メンション先は `@KingKongRobo`**（https://x.com/KingKongRobo、2026-10-15 確認）。表示名が応募要項の「@KingKong Robotics」と一致し、プロフィールのリンクが kingkong.tech、Jumper のオープンソース化と大会の案内を必須ハッシュタグ付きで投稿している。公式の投稿は `#KingKong #BeUnlimited` も付けている（応募には不要。付けても267字で収まる）。
2. **サムネイル**：パソコン版の投稿画面で、動画にサムネイルを設定する項目があるか確かめる。あれば `renders/final/thumbnail.png` を使う。
3. 動画は `renders/final/scissors_crab.mp4`（22.4秒、1920×1080）。

## 1. 本投稿（英語、動画を付ける）

```text
Can a crab robot win at rock-paper-scissors? 🦀

Our Jumper learned every move in simulation with the open-source toolkit: the throw, the slump, the happy jump, the shy hide.

Watch to the end.

@KingKongRobo #Jumper #CrabRobot #OpenSourceRobot
```

## 2. 返信1：作り方

```text
How it was made 🛠️
1. Keyframed each reaction on the 22-joint rig in Blender
2. Trained a policy to imitate it in MuJoCo with the Jumper toolkit (RL on a Colab GPU)
3. Rendered the simulated motion in Blender, with eye animations

Code: https://github.com/RyotaNishioka9623/jumper_project
```

## 3. 返信2：最初は跳べなかった話（ジャンプ）

```text
At first, the victory jump never left the floor. Just very enthusiastic squats 😅

The reward only scored the pose, and penalties charged for every watt of a push-off. Lifting those for the jump and rewarding height and foot contact got it airborne. For 0.06 s.
```

## 4. 返信3：注記とクレジット

```text
All of this is simulation (MuJoCo), not the real robot yet.

Scene: KingKong Robotics jumper-design (home map)
Human: Blender Studio Human Base Meshes (CC0)
Sound effects: 効果音ラボ
```

## 5. 日本語（本投稿の引用ポスト）

```text
カニのロボットにじゃんけんをさせてみました🦀

負けて泣いて、勝ってはしゃいで照れて…ぜひ最後まで。

オープンソースのJumperで、動きはすべてシミュレーションの強化学習です。作り方はスレッドに。
```

## 返信2の補足（必要なら別の返信に使う）

- 学習の評価は「姿勢がお手本に近いか」だけで、空中に出ても点が増えなかった。ダンス用の電力とトルクの減点は、思い切り踏み切るほど損をする設定だった（公式ジャンプのお手本で計算すると、踏み切りの0.2秒間に1ステップ平均4.7点の減点、加点は最大6.5点）。
- ジャンプの区間だけ減点を外し、公式の `jumper.jump` と同じ3項目（胴体の高さ、上下速度、足の接地状態）で加点したところ、胴体が130mm→157mmまで上がり、2回とも約6mm・0.06秒だけ空中に出た（お手本は33.6mm）。

---

# カメラ版（本投稿とは別の投稿）

動画は `renders/live/live_demo.mp4`（24.1秒、1280×720、H.264。`edit/make_live_demo.py` → `tools/edit.py` で作る）。本投稿（上の1.）を**引用**して投稿し、ハッシュタグとメンションを付ける（審査の「Useful（技能）」に当たる、もう1本の応募）。この動画は画面に「カニ：チョキ」と出るので、本投稿より後に出す。

## 6. カメラ版（英語、動画を付け、本投稿を引用）

```text
Now you can actually play it 🦀✂️

A webcam reads your hand with MediaPipe, and the trained Jumper policies react live in simulation: the crab loses, wins, or calls a draw and goes again.

@KingKongRobo #Jumper #CrabRobot #OpenSourceRobot
```

## 7. カメラ版の日本語（6.の引用ポスト）

```text
カメラでカニとじゃんけんできるようにしました🦀

MediaPipeで手を読み取り、学習済みのカニがシミュレーションの中でその場で反応します。あいこなら「あいこでしょ」が続きます。
```

## 8. カメラ版への返信：コード（6.への返信）

本投稿のスレッドのリンクまでたどらない人のために、カメラ版のスクリプトへ直接つなぐ。

```text
Code: https://github.com/RyotaNishioka9623/jumper_project/blob/main/scissors_crab/interactive/janken_cam.py

Runs on a Mac CPU. MediaPipe reads your hand 0.2–0.5 s after "shoot", and the crab's state is handed mid-motion to the policy for that outcome. Simulation only, not the real robot yet.
```

## 9. 実機のカメラでやりたいこと（8.への返信、文だけ）

シミュレーションで描いたカニの目線の映像（`renders/pov/`）は**付けない**（2026-10-29、ユーザーの判断）。実機のカメラは対角162°の超広角で、普通のレンズとして描いた映像は実機の見え方と違うため。実機で確かめたことではなく、これからやりたいこととして書く。

```text
Next I'd love to try this with the real Jumper's own front camera instead of my webcam, so the crab reads your hand and judges the game with its own eyes 👀
```

## 10. 9.の日本語（7.への返信、文だけ）

```text
次は、Macのカメラではなく、Jumper実機の前面カメラで手を読んでみたいです。カニが自分の目で勝負を判定できるように👀
```
