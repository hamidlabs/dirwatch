# Changelog

All notable changes to dirwatch are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-06-25

First public release.

### Added
- Watch user-defined folders and prompt on each new file that settles, with a
  centered, floating macOS-style card: Keep, Move, Snooze, Delete (Trash), Ignore.
- Existing files are baselined when a folder is first added, so only genuinely
  new arrivals prompt.
- Independent snooze schedules (1 hour / evening / tomorrow / next week); snoozed
  files are excluded from new-file prompts and resurface on their own time.
- Startup recovery: snoozes that came due while the machine was off are surfaced;
  files deleted while snoozed are dropped quietly (never crash).
- Batch "Review" window for backlogs, with per-file and bulk super-actions
  (Keep / Snooze / Move / Ignore / Delete all).
- Compositor auto-detection (niri / sway / hyprland / GNOME / KDE) with
  self-configured floating rules where needed.
- Professional settings window (folders, behavior, floating, about), launch at
  login, and an app/tray icon.
- SQLite persistence with retention pruning of old records.
- Linux AppImage packaging, `make install`, and headless smoke tests.

[0.1.0]: https://github.com/hamidlabs/dirwatch/releases/tag/v0.1.0
