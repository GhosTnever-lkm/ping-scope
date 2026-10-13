# Changelog

## 0.2.3 - 2026-10-13

- Correct the application window's displayed version to match the release metadata.

## 0.2.2 - 2026-10-11

- Complete the standard MIT license text, restoring the full warranty and liability disclaimer.

## 0.2.1 — 2026-10-10

- Updated GitHub Actions to the current Node 24-compatible major versions.
- Kept standalone Windows x64 and source archives reproducible with SHA-256 checksums.

## 0.2.0 — 2026-10-10

- Added a standalone one-file Windows x64 build that runs without a separate Python installation.
- Added reproducible, version-pinned PyInstaller packaging to the release workflow, with SHA-256 checksums for both app and source archives.
- Suppressed the child console window when the packaged app runs Windows ping.
- Added regression coverage for captured ping output and no-console launch.

## 0.1.0 — 2026-10-10

- First public source release of PingScope.
- Live ICMP sampling, latency/jitter/loss metrics, adaptive chart and CSV export.
- Offline local UI; no dependency installation or administrator privileges required.
- Windows Python launcher fallback and documented ICMP measurement limits.
