# WAPFLIX diagnostic installation package

Extract into the repository root, then run one command at a time:

    python3 wapflix-diagnostic-patch/apply.py --check
    python3 wapflix-diagnostic-patch/apply.py --apply
    python3 tools/diagnose.py --help
    python3 -m unittest discover -s tests -v

Requires Python 3.10+. FFmpeg/ffprobe are required for the real conversion tests.
No pip packages. Installer defaults to check-only. It validates all five file
hashes before writing, refuses different existing files and symlink targets,
and accepts identical files on repeat application. Stop on any error. An OS
write failure may leave a subset of new files, so inspect git status if it fails.

Only the five manifest-listed files are installed. Existing player, navigation,
themes, Pages workflow and build scripts are not modified. Nothing is committed
or pushed. Do not stage this package folder or the archive. After reviewing,
stage only the five intended files explicitly if you want to commit them.

Open docs/BENCHMARKING.md for the updated yt-dlp download and benchmark commands.
Media and reports stay outside the repository. This is an offline diagnostic,
not a progressive player or Docker backend. The preview is a single frame.

Verification: 15 tests passed in an isolated fixture environment, including
three real FFmpeg integration tests. The final archive was reopened and its
payload hashes verified, installed into another fixture checkout and tested.
Installer dry-run, repeat application and conflict refusal were also checked.
Your full repository test suite, N5105, media HDD and live Pages remain untested.
