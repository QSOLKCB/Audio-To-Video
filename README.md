# Audio to Video

**Audio in. Video out. All on your computer.**

A small native desktop application for making MP4 videos from music or spoken audio.
Two modes:

- **Still image:** one PNG or JPEG, fitted without cropping, stretching, or movement.
- **Visualizer:** eight deterministic styles: waveform bars, stereo oscilloscope,
  **Quantum Galaxy**, **GLUBALL Knot**, **ETQ Graph Walk**, **Triggered oscilloscope**,
  **Stereo vectorscope** and **Radial oscilloscope**.

Add an optional **Name – Track** title at the top in either mode.
[Visual styles and GALAXY/GLUBALL references](docs/visualizers.md) ·
[OPT optimizations and measured results](docs/optimization.md) ·
[ETQ Graph Walk and VIZ provenance](docs/etq.md).

MP3, M4A and WAV in. H.264 video + AAC audio in an MP4 out. Choose 1080p or 720p,
both 16:9 at 30 fps. The whole audio file is used; video ends on the next complete
frame, at most 1/30 second later. No account, uploads, advertising, model downloads,
cloud service, browser runtime, Node, or container is required.

[Windows/macOS bundles and Homebrew](docs/portable.md) · [Earlier Linux previews](packages/README.md) · [GTK screenshot](docs/gtk-preview.png)

![ETQ Graph Walk captured from a verified MP4 export](docs/etq-preview.png)

[Quantum Galaxy and GLUBALL Knot preview](docs/visualizer-preview.png)

## Run on Ubuntu 24.04 or newer

From a checkout:

```sh
./install-deps.sh
./audio2video
```

Or extract the Linux package, enter its directory, and run `./audio2video`.
The dependency helper is a **one-time, explicit** system package installation.
The application itself does not install anything or make network requests.
It uses `/usr/bin/python3` so Ubuntu's GTK bindings work even with a virtualenv active.

1. Choose your MP3, M4A, or WAV.
2. Choose **Still image** and a PNG/JPEG, or select **Visualizer** and its style.
3. Optionally enter your title, check the destination and click **Create MP4**.
4. When validation finishes, click **Open video** to use your normal video player.

Existing files are never overwritten. Cancellation, a failed encode, or failed
verification cleans up the temporary files. Closing the window cancels active work
and waits for FFmpeg to stop. Both desktops show elapsed export time. Full error text is available under **Details**.

The UI follows the simple native-desktop approach in
[M4A2TXT](https://github.com/QSOLKCB/M4A2TXT/pull/1); this is an independent implementation
and does not require M4A2TXT, Whisper, CUDA, or a GPU.

## CLI

The CLI uses the same renderer and export checks as the GUI:

```sh
./audio2video doctor
./audio2video render "song.m4a" "song.mp4" --image "cover.png"
./audio2video render "song.mp3" "galaxy.mp4" --visualizer --style qutrit-galaxy --title "Name – Track"
./audio2video render "talk.wav" "talk.mp4" --visualizer --style etq-graph-walk --resolution 720p
./audio2video render "stereo.wav" "scope.mp4" --visualizer --style trigger-scope --resolution 720p
./audio2video render "stereo.wav" "phase.mp4" --visualizer --style vectorscope
```

Relative input/output paths are relative to your current directory, including when
the launcher is invoked from elsewhere. Ctrl+C cancels the CLI. Paths are passed as
arguments to local processes, never through a shell. Inputs are restricted to local
regular files and their documented demuxers; FFmpeg network protocols are disabled.

## The visualizer must survive the export

Success requires more than FFmpeg returning zero. Before publishing the final file,
the application:

- Requires exactly one H.264/yuv420p video stream and one AAC audio stream, with
  the expected dimensions, frame rate and audio duration.
- Decodes **every video frame**, checks its count, and, in visualizer mode, compares
  it with a thumbnail calculated from the matching audio-sample window, style and frame index.
- Rejects missing/blank visualizer frames and material mismatches such as a frozen
  visualizer over changing audio. Titles get a separate presence/content check. Lossy-codec tolerances are documented in the code.
- Decodes the audio stream to check for decoding failures.
- Publishes the MP4 only after those checks pass.

Still-image exports may legitimately be dark or black, so they get stream, duration,
frame-count and decode checks without a waveform-presence check. The visualizer's
verification is a pixel-tolerance check, not a mathematical proof of codec correctness.
It cannot certify how every third-party player or video-hosting service behaves.

## Determinism and local resources

The audio is decoded once to 48 kHz stereo signed 16-bit PCM. Each video frame uses
exactly 1,600 stereo sample pairs. Eighty time bins take the peak magnitude from
either channel; opposite-phase stereo therefore cannot cancel the waveform.
Bars are **time-domain waveform bins, not frequency-spectrum bins**. The new
[styles](docs/visualizers.md) use fixed angles and bounded indexed particles; Pillow
draws the raster and glow. Quantum Galaxy and GLUBALL Knot map three broad audio
bands into normalized artistic state weights. No wall-clock timing,
randomness, graphics driver, or display capture influences the output.

Identical decoded PCM, style, frame index, title, font and Pillow build produce
identical source frames. Identical inputs and settings
are tested for identical decoded frames and MP4 bytes on the same FFmpeg/libx264
build. Byte-identical MP4s across codec versions, CPU architectures or distributions
are **not** promised. Record `ffmpeg -version` when comparing exports.

Rendering uses the CPU with one codec thread for repeatability. Memory is bounded
by a few video frames; decoded audio is streamed to a temporary file in the destination
folder (about **660 MiB per hour**, plus the output MP4). Full export verification adds
a decode pass. Use 720p for faster jobs. Temporary files are removed on handled errors
and cancellation; a power loss or forced kill may leave an `.audio2video-*` folder that
can be removed when no export is running.

The destination must be an existing local folder on a filesystem supporting hard links
(for example NTFS, APFS, ext4 or Btrfs). Atomic, no-overwrite publication uses a hard link; FAT/exFAT
destinations are not supported. Save locally, then copy the completed MP4 if needed.

## Develop, verify, package

Core runtime: Python 3.10+, Pillow 10+, the bundled DejaVu Sans font, and FFmpeg/FFprobe with libx264 and AAC.
Linux desktop: PyGObject, GTK 4.10+, libadwaita 1.4+. Portable desktop: standard-library Tcl/Tk.
The native CI builds include the runtime and media dependencies; Homebrew installs them explicitly.
See [builds, installation, shortcuts and platform limits](docs/portable.md).

```sh
/usr/bin/python3 -m unittest discover -s tests -v
# Native GUI tests (install xvfb, xauth, dbus-x11 and imagemagick):
GSK_RENDERER=cairo GTK_A11Y=none xvfb-run -a -s '-screen 0 1280x1000x24' \
  dbus-run-session -- /usr/bin/python3 tests/gtk_smoke.py --screenshots /tmp/a2v-layouts
# Package the committed tree, with source identity and file checksums:
/usr/bin/python3 scripts/package.py --ref HEAD
/usr/bin/python3 tests/package_roundtrip.py
```

CI runs real MP3/M4A/WAV encodes, PNG/JPEG exports, silence and opposite-phase stereo,
partial final frames, corruption and cancellation cases, repeatability checks, deliberate
blank/frozen/wrong-style/missing-title/audio-only MP4 rejection, native GTK interaction and a packaged CLI export.

This repository is a fresh local implementation. The former reference README remains
available only in Git history. The bundled DejaVu font includes its licence in `LICENSES/DejaVu.txt`.
The existing Apache-2.0 project licence is retained;
`a2v/etq.py` is an MPL-2.0 adaptation from VIZ, with its licence in `LICENSES/`.
