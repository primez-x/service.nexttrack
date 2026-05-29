# Repository Guidelines

## Project Structure & Module Organization
This repository is a Kodi service add-on named `service.nexttrack`. `addon.xml` is the manifest and declares two entry points: `resources/lib/service_entry.py` for the background service and `resources/lib/script_entry.py` for script/test actions. Runtime Python modules live in `resources/lib/`, including playback, player, API, state, and utility code. Kodi skin XML files are in `resources/skins/default/1080i/`; add-on images and skin media are under `resources/media/` and `resources/skins/default/media/`. Settings are defined in `resources/settings.xml`, with English strings in `resources/language/resource.language.en_gb/strings.po`.

## Build, Test, and Development Commands
- `python -m compileall resources/lib` checks Python syntax without needing Kodi modules at runtime.
- From the parent directory, `Compress-Archive -Path '.\service.nexttrack' -DestinationPath '.\service.nexttrack.zip' -Force` creates an installable add-on zip for Kodi testing.
- In Kodi, install or update the add-on, enable it under Services, and use the settings action `Show a Next Track test widget...` to run `RunScript(service.nexttrack,test_window)`.

## Coding Style & Naming Conventions
Use Python 3-compatible code with the existing UTF-8/GPL header and `from __future__ import absolute_import, division, unicode_literals` in runtime modules. Use 4-space indentation, `snake_case` for functions and variables, `PascalCase` for classes, and descriptive module names. Keep Kodi-specific calls isolated behind helpers where practical, especially in `utils.py` and `api.py`. Match the existing XML indentation style when editing skin or settings files.

## Testing Guidelines
There is no committed automated test suite yet. For Python changes, run `python -m compileall resources/lib` before submitting. For behavior changes, perform a manual Kodi smoke test with playlist-based audio playback and the test widget action. If adding tests, place them under `tests/`, name files `test_*.py`, and mock Kodi modules such as `xbmc`, `xbmcgui`, and `xbmcaddon`.

## Commit & Pull Request Guidelines
Recent commits use short, imperative summaries such as `Improve NextTrack skin hook compatibility`, `Fix Next Track popup...`, and `Refactor...`. Keep the first line focused on the user-visible or architectural change. Pull requests should describe the scenario tested in Kodi, list any changed settings or skin properties, link relevant issues, and include screenshots or short clips for UI overlay changes.

For Primez repository publishing, any commit pushed to the tracked `main` branch must bump the root `addon.xml` version in the same commit. Kodi auto-update consumes the generated repository version, not the Git SHA, and the central `kodi.addons` publish guard rejects webhook publishes whose source version does not increase.

## Security & Configuration Tips
Do not commit local Kodi profile data, logs, cache files, or generated zip packages. Avoid hard-coded local paths; use Kodi add-on paths and settings APIs instead.
