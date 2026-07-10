# ADR-0005: StreamPublisher 抽象と 1 デバイス 1 プロセス構成

- ステータス: 承認済み (2026-07-10)
- 関連: ロードマップ（README）、ADR-0004

## コンテキスト

ロードマップでは Phase 2 に IMU、Phase 3 に離散イベント（ジェスチャ／圧力／ナビ）の
Markers ストリームを予定している。v1 を単一スクリプトにハードコードすると Phase 2 で
書き直しになり、逆に汎用 N シグナルのプラグインレジストリを先取りすると存在しない信号の
ために過剰設計になる。

## 決定

最小限の `StreamPublisher` シームを設ける（`publishers/base.py`）。

```python
class StreamPublisher(Protocol):
    def lsl_info(self) -> StreamInfo: ...
    def poll_and_push(self) -> None: ...
    def close(self) -> None: ...
```

- `app.py` が BLE 接続と単一の `mudraka.Stream` を所有し、0xfff4 通知ごとに
  `stream.feed(data, recv_time)` を呼び、タイマ（既定 20ms）で各パブリッシャの
  `poll_and_push()` を叩く。v1 のパブリッシャリストは `EmgPublisher` 1 つだが、
  ループ形状は複数を前提にしている。
- `EmgPublisher` は自身の読み取りカーソル、LSL アウトレット、スクラッチバッファを所有する。
- **1 プロセス 1 デバイス**。両手 EMG が必要なら `mudra-lsl` を 2 プロセス起動し、
  各自の `source_id` でアウトレットを区別する（`muse-lsl` と同じモデル）。

## 結果

- Phase 2/3 は「パブリッシャクラスを 1 つ追加、`app` のリストに 1 行追加」で済む（加算的）。
- プロセス内マルチデバイスや汎用レジストリは作らない（非目標）。
- 再接続時もアウトレットとパブリッシャは維持し、BLE 断の間はサンプルにギャップが出る
  だけ（ログに記録）でコンシューマ接続は保たれる。
