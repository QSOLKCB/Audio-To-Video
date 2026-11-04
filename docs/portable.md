# Portable desktops and Homebrew

The source app now runs on Windows, macOS and Linux. Native builds are produced by
`.github/workflows/portable.yml` for Windows x64, macOS Apple Silicon and macOS Intel.
Use the artifact whose architecture matches your computer. The workflow builds and
tests artifacts; it does **not** publish a release or move a tag.

## Windows

Extract the native ZIP, then double-click **AudioToVideo.exe**. The executable
contains Python, Tcl/Tk, Pillow, FFmpeg, FFprobe and the DejaVu title font. No separate
Python, GTK or FFmpeg installation is required. It unpacks its runtime into a
local temporary directory at launch; this is a self-contained executable, not a
statically linked binary. Keep the accompanying licence and build-provenance files.

From a terminal the same EXE supports the CLI:

```powershell
.\AudioToVideo.exe doctor
.\AudioToVideo.exe render song.wav video.mp4 --visualizer --style vectorscope --resolution 720p
```

## macOS

Extract the ZIP for your architecture and open **AudioToVideo.app**. This is an app
bundle, not an EXE. Its CLI is `AudioToVideo.app/Contents/MacOS/AudioToVideo`. The
bundle contains the media tools and their collected libraries, Python, Tk and Pillow.
Current builds target macOS 15 or newer, with separate Intel and Apple Silicon artifacts.

The CI builds are unsigned on Windows and ad-hoc signed on macOS; they are not
Developer ID notarized. OS download warnings can therefore appear. Public signed
installers require the owner's signing credentials and a separate release step.
Do not disable Gatekeeper or system-wide security settings to run a preview.

## Homebrew (source install)

After this change is merged, the repository can itself be used as a custom tap:

```sh
brew tap --custom-remote qsolkcb/audio-to-video https://github.com/QSOLKCB/Audio-To-Video.git
brew install --HEAD qsolkcb/audio-to-video/audio2video
audio2video
audio2video doctor
```

This is a HEAD formula, not a Homebrew/core listing or a versioned bottle. Homebrew
installs FFmpeg, Python 3.14, Tk and Pillow. The app then runs entirely locally and
does not install packages or make network calls. `brew upgrade --fetch-HEAD audio2video`
updates the source install. The macOS CI job installs and tests the actual formula
against an archive of the PR commit, including a real MP4 export and GUI launch.

## From source

- **Ubuntu 24.04+:** `./install-deps.sh`, then `./audio2video` for GTK.
- **Windows/macOS:** install Python with Tcl/Tk and FFmpeg (including FFprobe), then
  `uv run --with 'pillow>=10' python -m a2v` from the checkout. A Python distribution
  without Tcl/Tk needs that OS dependency installed first.
- **Portable Tk desktop on any OS:** `python -m a2v gui --backend tk`.
- **Headless CLI:** `python -m a2v render ...` never imports a desktop toolkit.

The same styles, title rendering, output checks, no-overwrite rule and cancellation
apply to both desktops. Tk shortcuts: Ctrl+O to choose audio, Ctrl+Enter to export,
Escape to cancel; macOS also accepts Command+O/Command+Enter. Both desktops show
elapsed export time and suggest an unused output filename. File operations use
local paths; network protocols remain disabled in FFmpeg.

Save to a local filesystem that supports hard links (NTFS, APFS, ext4, etc.).
FAT/exFAT cannot provide the app's atomic no-overwrite publication guarantee; save
locally and copy the finished file if needed. All temporary media remain in the
output folder and are removed on handled cancellation or failure.

## Build your own self-contained app

Build on the target OS and architecture. PyInstaller is **not a cross-compiler**:
https://pyinstaller.org/en/stable/usage.html

```sh
uv run --no-project --python 3.12.10 --with pillow==10.4.0 --with pyinstaller==6.16.0 \
  python scripts/build_portable.py --ffmpeg-dir /path/to/native/bin --notices /path/to/media-licences
python scripts/smoke_portable.py dist/Audio-To-Video-1.1.0-PLATFORM-ARCH --gui
```

The build script never downloads tools. Supply matching native FFmpeg and FFprobe
with libx264 and AAC, plus their licence notices and source/build provenance. Windows
CI checks a pinned Gyan FFmpeg 8.0.1 archive SHA-256; macOS records the exact installed
Homebrew builds and licence files. PyInstaller collects dependent dylibs on macOS.
The smoke check rejects non-system absolute library links and runs every style with
an empty PATH, so the build machine's FFmpeg installation cannot mask a missing tool.

Each archive contains `BUILD.json`, `SHA256SUMS`, application/third-party licences and
an external ZIP checksum. The receipt records the commit, dirty-worktree flag, Python,
Pillow, PyInstaller and media-tool versions/hashes. Native bundle byte reproducibility
across OS images or toolchain versions is not claimed. Same-toolchain render
repeatability and the existing source-package reproducibility checks remain tested.
