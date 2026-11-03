#!/bin/sh
set -eu
# Explicit, user-run setup only. The application never installs or downloads.
if ! command -v apt-get >/dev/null 2>&1; then
    echo 'Install Python 3.10+, Pillow, DejaVu Sans, FFmpeg with libx264/AAC, PyGObject, GTK 4.10+ and libadwaita 1.4+.' >&2
    exit 1
fi
if [ "$(id -u)" = 0 ]; then
    apt-get update
    apt-get install -y python3 python3-pil fonts-dejavu-core python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 ffmpeg
else
    sudo apt-get update
    sudo apt-get install -y python3 python3-pil fonts-dejavu-core python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 ffmpeg
fi
