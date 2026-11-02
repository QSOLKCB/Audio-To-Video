# Linux preview package

[Download Audio-To-Video-0.1.0-preview-linux.tar.gz](Audio-To-Video-0.1.0-preview-linux.tar.gz?raw=true)

```sh
sha256sum -c Audio-To-Video-0.1.0-preview-linux.tar.gz.sha256
tar -xzf Audio-To-Video-0.1.0-preview-linux.tar.gz
cd Audio-To-Video-0.1.0-preview
./audio2video
```

If dependencies are missing on Ubuntu 24.04+, run `./install-deps.sh` once.
The archive contains source code, executable launchers and checksums; it uses your
system's Python, GTK and FFmpeg. It does not bundle codecs or GTK libraries.

Source commit: `ee4ccb82c0f621b5ab9e59f86b15f0ddaf30e289`.

Archive SHA-256:
`d13a0449b9bf8e7620cce50d30eb69204e31b5e7a249a66d71bf2d9eb427f9f6`.

The local and [CI package](https://github.com/QSOLKCB/Audio-To-Video/actions/runs/41542790460)
match byte for byte. That run passed 21 automated tests, package roundtrip checks,
and native GTK tests with real exports in both modes and cancellation on close.

A further extracted-package check rendered a 12.017-second stereo signal at 1080p
with IPv4, IPv6 and Unix socket creation denied by an inherited Linux seccomp filter.
All 361 decoded video frames passed verification; AAC duration was 12.017 seconds
and video duration 12.033333 seconds. This is a synthetic-signal test, not a claim
that hour-long projects or every external player have been tested.

The source identity above is intentionally fixed. Later documentation/package commits
can contain this verified archive without changing the application inside it.
