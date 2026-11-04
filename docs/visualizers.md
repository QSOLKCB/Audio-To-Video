# Visual styles and their sources

Version 0.2 adds **Quantum Galaxy**, **GLUBALL Knot** and **Oscilloscope** to the
original waveform bars. Version 0.3 adds **ETQ Graph Walk**, using the exact finite
graph from VIZ ([model and receiver details](etq.md)). Choose the style in GTK or with `--style`. The optional
single-line title applies to still images and every visualizer.

| Style / CLI value | Motion and audio response |
| --- | --- |
| Waveform bars / `bars` | 80 time bins, peak of either stereo channel; visible baseline in silence. |
| Oscilloscope / `scope` | Separate cyan and violet stereo traces. Silence retains both rails. |
| Quantum Galaxy / `qutrit-galaxy` | Three spiral arms, indexed dust and travelling state packets. Three audio-band energies set their populations and brightness; level changes packet size. |
| GLUBALL Knot / `gluball-knot` | Nine luminous filaments grouped into three state ribbons on a (2,3) torus knot. Audio controls thickness and brightness; phase packets travel around the knot. |
| ETQ Graph Walk / `etq-graph-walk` | Three luminous walkers follow real edges of the 303-state lifted graph. Audio changes trail brightness and packet size; model geometry stays fixed. |

The three populations are nonnegative integer weights summing to 1,000,000.
They come from squared energies of two simple first-order low passes and their
residuals, computed separately per stereo channel. This keeps opposite-phase
stereo audible to the visuals. Filters restart each 1,600-sample frame window;
these controls are not calibrated frequency measurements. Silence gives equal
populations. The legend displays the weights as percentages (rounding can make
the displayed percentages sum to 99.9% or 100.1%).

The qutrit-inspired bridge is new artwork: three basis labels `|0>`, `|1>`, `|2>`,
normalized weights, and deterministic cyclic phases. It does not simulate quantum
measurement, quantum hardware, a quantum state trajectory, gravity or QCD. Phase
is a function of frame index at 30 fps, so the galaxy and knot keep moving during
silence. There is no wall clock, mutable random generator, GPU or camera control.

## Previous QSOLKCB work used as design references

- [GALAXY RETRO-MATH](https://github.com/QSOLKCB/GALAXY/blob/f219bb427b3a9b0c93900169d903f48f410ae67a/docs/RETRO-MATH.md): wrapping
  binary-angle turns, fixed-point projection and indexed, bounded particle work.
  This renderer has its own committed 257-entry quarter-wave Q14 table and a
  fixed 32-bit index mixer. It does not import GALAXY's CORDIC, particle engine,
  physics solver or identity/receipt contract.
- [GLUBALL core](https://github.com/QSOLKCB/GLUBALL/blob/d25da2a1ade877e2fe048fd4dabf019728cb25e7/gluball-core.js)
  and [sampling notes](https://github.com/QSOLKCB/GLUBALL/blob/d25da2a1ade877e2fe048fd4dabf019728cb25e7/docs/SAMPLING.md): the (2,3)
  torus-knot geometry and finite indexed sampling approach. We implement the
  mathematical centreline `((R+r cos 3t) cos 2t, (R+r cos 3t) sin 2t, r sin 3t)`
  independently, with decorative travelling filaments and a fixed projection.
  This is not GLUBALL's frozen geometry buffer or its topology/colour contract.

The Galaxy and GLUBALL styles import no donor implementation files. The separate
[ETQ module](etq.md) ports VIZ's finite construction with MPL-2.0 notices. All source
identities are fixed; no donor repository is needed at runtime.

## Text and export checks

Titles are literal text, up to 120 characters. DejaVu Sans is installed by the
system dependency helper. Text is centred, measured and reduced to fit; an overly
wide title produces an error instead of clipping. Glyph coverage follows that font;
emoji and complex-script shaping are not guaranteed. Newlines/control characters
are rejected. Blank text disables the title. No shell, markup or FFmpeg filter
expression interprets the title.

The title is drawn once at the actual output resolution in a reserved top strip.
Still images fit below it without cropping. Visualizer geometry begins below it.
The GTK visualization is an illustrative style preview, not live audio playback.

Every final MP4 frame is decoded at native size into RGB before thumbnail sampling.
Sampling YUV420 first can choose different luma/chroma locations and falsely turn
thin coloured lines grey. The verifier checks geometry below the title and above
the static population legend, then checks the title independently. A visible title
or legend cannot satisfy the visualization-presence test. Deliberately blank,
wrong-style, frozen and missing-title exports are regression-tested.

These are lossy-codec tolerance checks at 160x90, not full-resolution equality.
Subpixel motion and changes below the tolerance are not certified. Reproducibility
requires the same decoded PCM, style, frame index, title, font, Pillow and codec
builds. Byte identity across platforms or library versions is not promised.


## Oscilloscope additions (1.1)

| Style / CLI name | What it displays |
| --- | --- |
| Triggered oscilloscope / `trigger-scope` | Two channel traces on a graticule, aligned to the stronger channel's first rising zero crossing. Both traces share the trigger, preserving stereo phase. The visible sweep spans 800 samples (16.7 ms). |
| Stereo vectorscope / `vectorscope` | Mid/side projection: horizontal L−R, vertical L+R. In-phase mono is vertical; opposite-phase stereo is horizontal. Silence is a visible point. |
| Radial oscilloscope / `radial-scope` | Two concentric channel traces, one 1,600-pair audio window per circle. Both channel signals remain separate. |

These are sample-domain displays, not calibrated measurement instruments or FFT
spectra. Triggering stays inside each frame's own 1,600 stereo pairs; silence/DC
falls back to offset zero. Partial windows are zero-padded. No preceding frame,
wall clock or random state is required. A cached immutable grid and radial-angle
table bound setup work; bright traces remain visible after codec thumbnail sampling.

All three use the same full-frame decode and sample-derived verification as the
existing styles. Tests include real 720p/1080p exports, repeatability, silence,
opposite-phase stereo, shared trigger alignment, partial frames and rejection of
blank, frozen or wrong-style encodes. Verification retains the existing documented
lossy-codec tolerance; it is not a claim that every one-pixel change is detected.
