# ADR-0001: LSL バインディングに mne-lsl を採用する

- ステータス: 承認済み (2026-07-10)
- 関連: ADR-0003, ADR-0004

## コンテキスト

Python から LSL アウトレットを公開する主要な選択肢は 2 つある。

- `pylsl` — 公式バインディング。`muse-lsl` や `OpenBCI_LSL` が採用している実績あり。
- `mne-lsl`（`mne_lsl.lsl` モジュール）— `pylsl` の低レベルバインディングを置き換える
  後継。FCBG がメンテナンスし 2026 年まで継続リリース。BSD-3-Clause。Python ≥ 3.11 を要求。

`mudra-lsl` は EMG を将来的に MNE-Python ベースの解析（運動単位分解など）へ渡すことを
見据えている。単一アウトレットの EMG ブリッジとしては両者に機能差はない。

## 決定

`mne_lsl.lsl` を採用する。`StreamInfo` / `StreamOutlet` / `push_chunk` の低レベル API は
`pylsl` とほぼ同形であり、移行コストは低い。`requires-python = ">=3.11"` を
`pyproject.toml` に設定する（`mne-lsl` の要求に一致、許容範囲内であることは確認済み）。

インストール済みバージョン (`mne-lsl 1.13.2`) で以下を実地確認した。

- コンストラクタ: `StreamInfo(name, stype, n_channels, sfreq, dtype, source_id)`。
- `set_channel_names` / `set_channel_types` / `set_channel_units` が存在し往復する。
- `desc` は **プロパティ**（メソッド呼び出しではない）で `XMLElement` を返し、
  `append_child_value(name, value)` が使える。ブートストラップで懸念された
  「`desc` vs `desc()`」は本バージョンではプロパティ側で確定。
- `push_chunk(x, timestamp=None, pushThrough=True)`。`x` は `(n_samples, n_channels)`
  形状を要求し、逆形状は `ValueError` を送出する（ADR-0004 の転置の根拠）。

## 結果

- MNE-Python エコシステムへ自然に接続できる。
- Python 3.11 未満は非対応。現時点で許容。
- 依存に `mne`（`mne-lsl` 経由）と `scipy` などが入る。`mne` 本体は
  `examples` extra のみで必要とし、コア機能は `mne-lsl` だけで動く。
