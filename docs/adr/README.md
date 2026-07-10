# アーキテクチャ決定記録 (ADR)

`mudra-lsl` の設計上の重要な決定を記録します。フォーマットは Michael Nygard 形式
（ステータス / コンテキスト / 決定 / 結果）に準拠し、言語は日本語です
（mudraka / mudra-viewer の慣習に合わせています）。公開向けドキュメントである
README は英語です。

| ADR | タイトル | ステータス |
|-----|---------|-----------|
| [0001](0001-lsl-binding-mne-lsl.md) | LSL バインディングに mne-lsl を採用する | 承認済み |
| [0002](0002-source-id-device-serial.md) | LSL の source_id にデバイスのシリアル番号を使う | 承認済み |
| [0003](0003-timestamps-push-chunk-autostamp.md) | タイムスタンプは push_chunk の自動付与に委ねる | 承認済み |
| [0004](0004-value-representation-uv-float32.md) | 値表現は µV / float32、スケールは暫定として明示する | 承認済み |
| [0005](0005-architecture-stream-publisher.md) | StreamPublisher 抽象と 1 デバイス 1 プロセス構成 | 承認済み |
| [0006](0006-license-apache-2.0.md) | リポジトリのライセンスを Apache-2.0 にする | 承認済み |
| [0007](0007-packaging-uv-hatchling.md) | パッケージングは uv + hatchling、フラットレイアウト | 承認済み |
