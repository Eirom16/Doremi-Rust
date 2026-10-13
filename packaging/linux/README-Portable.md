# Doremi Linux x86_64 Portable

Extract and run — no Python, Rust or VLC installation required.

```bash
tar xzf Doremi-Linux-x86_64-Portable.tar.gz
cd Doremi-Linux-x86_64-Portable   # or the extracted directory name
./Doremi --smoke-test             # self-check: expect DOREMI_SMOKE_OK, exit 0
./doremi.sh                       # recommended launcher (bundle VLC env)
./Doremi                          # direct binary (also works)
```

## Notes

- No root required. Never run as root.
- User data (config, database, downloads, logs) lives in the standard XDG
  directories (`~/.config/doremi`, `~/.local/share/doremi`, `~/.cache/doremi`)
  and is preserved between runs. Nothing personal is written inside the bundle.
- `doremi.sh` prepends the bundled `vlc_libs/` to `LD_LIBRARY_PATH` and pins
  `PYTHON_VLC_LIB_PATH` / `VLC_PLUGIN_PATH` to the bundle without overwriting
  your values. It works from any working directory.
- Built on Ubuntu 22.04 x86_64 (glibc 2.35 baseline) for broad distro
  compatibility. See `MANIFEST.txt` for the exact build versions.
- Licenses: `LICENSE.txt` (Doremi, GPL-3.0) + `THIRD-PARTY-NOTICES.txt`.
  Public redistribution stays subject to the source-offer obligations listed
  there (VLC, Qt); internal test use is fine.
