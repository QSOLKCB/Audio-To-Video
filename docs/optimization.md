# OPT adaptation: exact reuse and native pixel comparisons

Source: [QSOLKCB/OPT at 7556dd3](https://github.com/QSOLKCB/OPT/tree/7556dd36acd53ed3ed538fd03b1db44e5c1ec869).
Patterns used: `OPT-INV-001` (equivalent reuse) and `OPT-PY-001` (immutable
intermediates, precomputed lookups and vectorized classifications). No donor code,
benchmark constants, approximation policies or worker counts are copied.

## Contract declared before measurement

- X: precompute fixed knot basis values; replace Python pixel loops with exact
  Pillow operations; retain one immutable title-reference entry.
- F: identical source RGB24 bytes and identical verification accept/reject decisions
  for the same inputs; same every-frame checks, cancellation and publication behavior.
- f/d: minimize median full export time, including rendering, encoding and verification.
- C: no frame skipping, lower-resolution reference rendering, looser codec tolerance,
  stateful randomness, new GPU/runtime dependency or retained per-track frame cache.
- B: one candidate batch, three alternating baseline/optimized pairs per quantum
  style on a fixed two-second 720p fixture; at most 15 minutes of measurement.
- S: stop after that batch; discard on parity failure. Report raw timings and
  variability, and make no speedup claim where separation is within observed noise.

Categorical local search; noisy timing objective; deterministic exact semantics;
black-box measurements; sequential trials. These are host-specific observations,
not a calibrated universal CI timing threshold or a statistical detector claim.

The pre-optimization renderer's raw-frame digests are kept in
`tests/visual-golden.json`. The scalar verification oracle stays in tests. The
benchmark also compares baseline/optimized source frames, checker outcomes and
complete MP4 bytes before reporting timings. All ordinary failure tests remain.

The finite lookup tables are independent of audio and track length. The title
reference has one entry because a desktop export has one active title/resolution;
changing either reconstructs it. No rendered-frame history is cached. The verifier
still independently renders the expected style from the matching PCM window.

See the recorded benchmark JSON for environment, implementation hashes and raw
observations. Repeat measurements on the intended machine before extrapolating.

## Measured result

Three alternating pairs on this Linux/AMD EPYC host (Python 3.12.3, Pillow 10.2.0,
FFmpeg 6.1.1), including cold caches and complete exports:

| Style | Baseline median | Optimized median | Time reduction |
| --- | ---: | ---: | ---: |
| Quantum Galaxy | 3.886 s | 3.012 s | 22.5% |
| GLUBALL Knot | 6.054 s | 4.233 s | 30.1% |

All six MP4s per style were byte-identical. This is a 2.017-second synthetic stereo
fixture at 720p, not a promise about full albums or other machines. The raw
[observations](optimization-benchmark.json) record source-file hashes and each run.
The baseline and optimized paths receive the same viewport correction found in visual QA; this functional correction is not credited as an optimization. A second paired run after that correction replaces the initial characterization, with unchanged optimization choices.

To reproduce from a Git checkout (not the standalone package):

```sh
mkdir -p /tmp/a2v-reference
git show 50d6fae530b1273dff0b9fac68b13b58092969ce:a2v/visualizer.py > /tmp/a2v-reference/visualizer.py
git show 50d6fae530b1273dff0b9fac68b13b58092969ce:a2v/title.py > /tmp/a2v-reference/title.py
/usr/bin/python3 scripts/benchmark_visuals.py --reference /tmp/a2v-reference --output /tmp/a2v-benchmark.json
```

The baseline rendering source, including its Python reference checker, remains in
that commit. The script applies the same explicit knot viewport correction before
comparison and records the effective source hash. Golden frames cover silence, antiphase and a full-range ramp, all four
styles, and four frame indices including random access far into a track. The native
checker is compared with a frozen scalar oracle at coverage/difference boundaries.
The source-frame fixture is pinned to the tested Pillow 10.2.0 rasterizer.


## Portable/scopes update (1.1.0)

Compared with release source commit `255794c166f70b535c3a1a8f8a6609882e9b8f17`,
this update draws bars through Pillow's native rectangle rasterizer, unrolls the
three-band energy accumulation without changing integer rounding, caches immutable
galaxy dust geometry, and hoists invariant galaxy colours and knot phases. The
Windows pipe implementation uses bounded worker queues; Linux/macOS keep direct
cancellable pipe I/O so portability does not impose per-frame thread handoffs there.

[Raw timings, environment, source hashes and output hashes](portable-benchmark.json).
Three alternating baseline/candidate pairs ran in isolated subprocesses on the
same interpreter/Pillow/FFmpeg. Each style used a 2.017-second changing stereo
fixture (61 frames), 720p and a title. The source-frame timing includes hashing;
that pass also primes small geometry caches before the complete export timing.

| Existing style | Source render time reduction | Complete export: baseline → candidate | Export time reduction |
| --- | ---: | ---: | ---: |
| Waveform bars | 43.1% | 1.842 s → 1.833 s | 0.5% |
| Stereo oscilloscope | 0.6% | 2.847 s → 2.847 s | approximately unchanged |
| Quantum Galaxy | 8.4% | 3.410 s → 3.040 s | 10.9% |
| GLUBALL Knot | 10.5% | 4.926 s → 4.310 s | 12.5% |
| ETQ Graph Walk | −4.5% | 2.762 s → 2.743 s | 0.7% |

These are medians from this machine and short fixture, not universal speed claims.
Scope and ETQ total export changes are effectively flat; ETQ's isolated raster
measurement was slower in this sample. Faster bar rasterization does not imply an
equivalent total export gain because encoding and verification still dominate.

For **every existing style**, all six outputs had identical source-frame hashes
and byte-identical MP4 hashes. Golden-frame, scalar bar/energy oracles, cancellation,
codec-corruption and full-export checks remain required. No verification frames
are skipped and no source reference is reused from an untrusted encoded result.

To reproduce against an unmodified checkout of that commit:

```sh
/usr/bin/python3 scripts/benchmark_portable.py --reference /path/to/baseline --output /tmp/a2v-benchmark.json
```
