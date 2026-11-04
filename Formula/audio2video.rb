class Audio2video < Formula
  desc "Local audio-to-MP4 renderer with deterministic visuals and checked exports"
  homepage "https://github.com/QSOLKCB/Audio-To-Video"
  head "https://github.com/QSOLKCB/Audio-To-Video.git", branch: "main"
  license all_of: ["Apache-2.0", "MPL-2.0"]

  depends_on "ffmpeg"
  depends_on "pillow"
  depends_on "python@3.14"
  depends_on "python-tk@3.14"

  def install
    libexec.install "a2v", "LICENSES", "LICENSE"
    (bin/"audio2video").write <<~SH
      #!/bin/sh
      export A2V_FFMPEG_DIR="#{Formula["ffmpeg"].opt_bin}"
      export A2V_GUI_BACKEND=tk
      exec "#{Formula["python@3.14"].opt_bin}/python3.14" "#{libexec}/a2v/launcher.py" "$@"
    SH
  end

  test do
    assert_match "FFmpeg and FFprobe found", shell_output("#{bin}/audio2video doctor")
    system Formula["ffmpeg"].opt_bin/"ffmpeg", "-v", "error", "-f", "lavfi", "-i",
           "sine=frequency=440:duration=0.1", "-c:a", "pcm_s16le", testpath/"tone.wav"
    system bin/"audio2video", "render", testpath/"tone.wav", testpath/"out.mp4",
           "--visualizer", "--style", "trigger-scope", "--resolution", "720p", "--title", "Brew check"
    assert_path_exists testpath/"out.mp4"
  end
end
