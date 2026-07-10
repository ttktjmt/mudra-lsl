# ADR-0006: リポジトリのライセンスを Apache-2.0 にする

- ステータス: 承認済み (2026-07-10)
- 関連: ADR-0007

## コンテキスト

`mudra-lsl` 自身の OSS ライセンスを決める必要がある。これは Wearable Devices の
RawData ライセンス条項や third-party project としての位置づけ（README で TODO として
保留、著者判断で書かない）とは **別物** である。

## 決定

**Apache License 2.0** を採用する。

- リポジトリ直下に Apache-2.0 全文の `LICENSE` を置く（canonical テキストを取得）。
- `pyproject.toml` の `[project]` に SPDX 形式で `license = "Apache-2.0"` を設定し、
  対応する Trove 分類子も付す（hatchling が両者併記を受理することを実地確認済み）。
- 依存の `mne-lsl`（BSD-3-Clause）、`bleak`（MIT 系）はいずれも Apache-2.0 プロジェクトが
  依存する上で互換であり、特別な NOTICE 対応は不要。

## 結果

- `mudraka` のライセンス（Apache-2.0）と完全一致し、mudra* ファミリ内でクロスライセンスの
  摩擦が生じない。
- RawData ライセンス／third-party 位置づけの文言は本 ADR の対象外であり、README では
  プレースホルダのまま保留する（人間が Wearable Devices と確認する）。
