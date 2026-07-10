# ADR-0007: パッケージングは uv + hatchling、フラットレイアウト

- ステータス: 承認済み (2026-07-10)
- 関連: ADR-0006

## コンテキスト

パッケージングのツールとレイアウトを決める。mudraka は `uv` を採用し `uv.lock` を
同梱している。`mudra-lsl` もファミリのツール慣行に合わせたい。

## 決定

- ビルドバックエンドは **hatchling**、依存・仮想環境管理は **uv**。`uv.lock` を
  コミットする（mudraka に合わせる）。
- パッケージレイアウトは **フラット**（リポジトリ直下 `mudra_lsl/`）。ブートストラップ
  §5 の構成図に一致。
- 公開向け **README はリポジトリ直下**（GitHub / PyPI が期待する標準位置）。§5 の図では
  `docs/README.md` と記されていたが、ルート README を正とする（軽微な判断、
  §0.5 の「decide and proceed」範囲）。ADR は `docs/adr/`。
- CLI エントリポイント `mudra-lsl = "mudra_lsl.cli:main"`、ライブラリ API
  `from mudra_lsl import stream` の両方を提供する（`muse-lsl` と同様の二面性）。
- 依存ピン:
  - `mudraka>=0.3,<0.4`（公開最新 0.3.1 を確認。Phase 2 の IMU 対応など将来の破壊的
    変更が黙って挙動を変えないよう上限を切る）。
  - `mne-lsl>=1.6,<2`、`bleak>=0.22`、`numpy>=1.24`。
- Lint は `ruff`、テストは `pytest`。`device` マーカーで実機統合テストを既定スキップ。

## 結果

- ファミリ内でツールが揃い、`uv sync` / `uv run pytest` で再現可能。
- PyPI パッケージ名 `mudra-lsl` は 2026-07-10 時点で未使用を確認（JSON API が 404、
  `pip index` も distribution なし）。ただし公開直前に再確認する（§0.5 category 4）。
