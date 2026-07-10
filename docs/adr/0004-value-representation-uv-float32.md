# ADR-0004: 値表現は µV / float32、スケールは暫定として明示する

- ステータス: 承認済み (2026-07-10)
- 関連: ADR-0001

## コンテキスト

サンプル値の表現形式として、`int32`（生カウント）と `float32`（µV 換算）が
mudraka から取得できる（`latest_into` / `latest_uv_into`、`pull_into` / `pull_uv_into`）。
コミュニティの慣行（`muse-lsl`、`OpenBCI_LSL`、MNE-LSL のモック）は
`unit=microvolts` / `format=float32`。

一方で mudraka のスケール値は暫定・未検証である。実地確認では
`Config().profile.scale == [0.035, 0.035, 0.035]`（チャンネルごとのリスト）であり、
mudraka 自身のドキュメントが「PROVISIONAL/UNVERIFIED、ベンダー校正ではない」と
明記している。

## 決定

- `pull_uv_into` を用い **float32 / µV** で公開する。チャンネルメタデータは
  `type=emg`、`unit=microvolts`。
- ただしスケールが暫定であることを **ストリームメタデータと README の両方で明示** する。
  `desc` に `scale_note` を追加し、`0.035 uV/count` が暫定・未校正であり
  「絶対物理量ではなく相対振幅として扱う」ことを記す。
- スケールは単一スカラではなく **チャンネルごとのリスト** である点に対応する。値が全
  チャンネル一様な場合は単一値で表記し、非一様ならリストを記す。
- mudraka の `latest_uv_into` はチャンネルメジャー `(n_channels, n_samples)` を埋めるが、
  `push_chunk` はサンプルメジャー `(n_samples, n_channels)` を要求する。**転置してから
  push する**（本バージョンの mne-lsl は逆形状で `ValueError` を送出するが、値の取り違え
  という静かなバグを避けるため転置は必須）。

## 結果

- LSL コンシューマ側は追加の単位変換なしに µV として扱える。
- スケールが未校正であることが記録に残り、絶対値として誤用されにくい。
- 転置のコストは 1 チャンク分のメモリコピー（数 KB）で無視できる。
