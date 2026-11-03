# Linux preview package

[Download Audio-To-Video-0.3.0-preview-linux.tar.gz](Audio-To-Video-0.3.0-preview-linux.tar.gz?raw=true)

```sh
sha256sum -c Audio-To-Video-0.3.0-preview-linux.tar.gz.sha256
tar -xzf Audio-To-Video-0.3.0-preview-linux.tar.gz
cd Audio-To-Video-0.3.0-preview
./audio2video
```

If dependencies are missing on Ubuntu 24.04+, run `./install-deps.sh` once.
The archive contains source code, executable launchers and checksums; it uses your
system's Python, Pillow, DejaVu Sans, GTK and FFmpeg. It does not bundle system libraries.

Choose **Visualizer → ETQ Graph Walk** for the new VIZ-derived graph animation.
Quantum Galaxy, GLUBALL Knot, Oscilloscope and Waveform bars remain available.
Enter an optional **Name – Track** title above the output settings. Titles also
work with still images. All processing stays local.

Source commit: `2300b92c161c1a85663736e5da4c989b81957111`.

Archive SHA-256:
`850bc84982393d7ed19115a21cdd12c79e0dfa327bdaada728a0726542e2effd`.

[Source CI](https://github.com/QSOLKCB/Audio-To-Video/actions/runs/41559116732)
covers 44 automated tests, package roundtrip checks, and native GTK tests selecting
ETQ Graph Walk with real exports and cancellation on close. The downloaded CI
archive and this archive match byte for byte. The package includes
the [ETQ construction, traversal and licence details](../docs/etq.md). The finite
model matches the pinned VIZ donor's roots and edge arrays exactly.

A separate extracted-package check exported a four-second ETQ sample at 1080p with
a title while IPv4, IPv6 and Unix socket creation were denied by an inherited Linux
seccomp filter. All 120 decoded frames passed both the general visualizer check and
the additional moving-packet check. This is an offline CLI test, not a claim that
every desktop environment, hour-long project or external video player was tested.

The source identity above is fixed. Later documentation/package commits contain
this archive without changing the application inside it. Older archives remain for
reproducibility; 0.3.0 is the current preview.
