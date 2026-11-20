# SeekR 2.0.1

**Published:** 2026-11-20  
**Platform:** Windows 10 and Windows 11  
**License:** MIT

SeekR 2.0.1 replaces the former daily meme widget with a daily cat photo displayed directly inside the launcher.

## Daily cat widget

- Fetches a cat photo from TheCatAPI on a background worker so network activity does not block search or launcher interaction.
- Downloads and renders the actual image inside the widget; it does not display a post URL or open a browser.
- Validates the returned image host and content type, rejects oversized image downloads above 4 MB, and lets Qt validate the image data before display.
- Caches the photo locally for the current calendar day and restores it when SeekR starts again.
- Keeps the last successful photo visible during network outages and retries failed requests in the background.
- Preserves existing users' daily-widget enabled state, refresh interval, and right-rail ordering when migrating from the former meme widget settings.

## Validation

The v2.0.1 release is published only after the GitHub Actions pipeline completes its Ubuntu and Windows test matrix, packaged UI verification, portable/onedir builds, installer compilation, and fresh install/launch/uninstall smoke checks. See the Actions run linked from the release for the actual results.

Physical Windows 10/11 desktop checks (mixed DPI, multi-monitor, sleep/resume, real 1.x upgrade, long-duration stability and accessibility review) remain separate from automated CI and must not be treated as passed unless performed on real hardware.

Windows binaries are unsigned unless a code-signing certificate is configured.
