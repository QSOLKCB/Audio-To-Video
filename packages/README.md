# Linux preview package

[Download Audio-To-Video-0.2.0-preview-linux.tar.gz](Audio-To-Video-0.2.0-preview-linux.tar.gz?raw=true)

```sh
sha256sum -c Audio-To-Video-0.2.0-preview-linux.tar.gz.sha256
tar -xzf Audio-To-Video-0.2.0-preview-linux.tar.gz
cd Audio-To-Video-0.2.0-preview
./audio2video
```

If dependencies are missing on Ubuntu 24.04+, run `./install-deps.sh` once.
The archive contains source code, executable launchers and checksums; it uses your
system's Python, Pillow, DejaVu Sans, GTK and FFmpeg. It does not bundle system libraries.

Choose **Visualizer**, then **Quantum Galaxy**, **GLUBALL Knot**, **Oscilloscope**
or **Waveform bars**. Enter an optional **Name – Track** title above the output
settings. Titles also work with still images. All processing stays local.

Source commit: `427a3424fb3143de656fbb970d3e8449d513d576`.

Archive SHA-256:
`466cd001076539dc466352e3ed805296068eadd81545b6481cee0e460fbd50f1`.

The local and CI archives match byte for byte.

[Source CI](https://github.com/QSOLKCB/Audio-To-Video/actions/runs/41553046483)
covers 35 automated tests, package roundtrip checks, and native GTK tests with real
exports in both modes and cancellation on close. The package includes the raw
[OPT benchmark observations](../docs/optimization-benchmark.json), scalar parity
checks and [pinned GALAXY/GLUBALL references](../docs/visualizers.md).

A separate extracted-package check rendered the synthetic four-second GLUBALL
sample at 1080p with a title while IPv4, IPv6 and Unix socket creation were denied
by an inherited Linux seccomp filter. All 120 decoded video frames passed verification.
This is an offline CLI test; it does not claim that every desktop environment,
hour-long project or external video player has been tested.

The source identity above is fixed. Later documentation/package commits contain
this archive without changing the application inside it. The previous 0.1.0 archive
is retained for reproducibility; 0.2.0 is the current preview.
