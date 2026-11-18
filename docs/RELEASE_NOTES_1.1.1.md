# SeekR 1.1.1

## Fixed

- Keep each launcher widget permanently parented to its side rail. Refreshing
  widget settings no longer reparents cards, which could make Qt hide them.
- Add a GUI regression test that opens the launcher and checks that all enabled
  cards and both rails are visible with non-empty geometry.
- Add packaged-application verification to the Windows release workflow. CI
  launches the portable executable and the installed executable in UI-check
  mode and verifies all four enabled widgets render.

## Verification

The v1.1.1 release workflow passed on Windows Latest, Windows Server 2022 and
Ubuntu. The Windows job built the portable executable and Inno Setup installer,
verified widget visibility in both packaged forms, performed install/startup/
uninstall smoke tests, and uploaded SHA-256 checksums.

Automated UI checks do not replace a manual check on a user's Windows desktop.
See [the Windows manual test checklist](WINDOWS_MANUAL_TEST.md).
