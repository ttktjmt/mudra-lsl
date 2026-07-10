# Examples

Runnable LSL consumers for the `MudraEMG` outlet. Start the bridge first:

```bash
mudra-lsl stream -v
```

Then, in another terminal:

| Script | What it does | Needs |
|--------|--------------|-------|
| [`print_stream.py`](print_stream.py) | Resolve the outlet and print incoming chunks. A quick "is it flowing?" check. | core deps only |
| [`read_and_export_mne.py`](read_and_export_mne.py) | Record a few seconds into an MNE `Raw` and save a `.fif`. | `examples` extra (`uv sync --extra examples`) |

```bash
uv run python examples/print_stream.py
uv run python examples/read_and_export_mne.py --duration 10 --output emg_raw.fif
```

> The amplitude scale is provisional (see the main README and the stream's
> `scale_note`). The MNE export converts µV → V for unit-correctness, but treat
> the values as relative until calibrated.
