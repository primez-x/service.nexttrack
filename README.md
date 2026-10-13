# Next Track

Next Track shows a countdown overlay for the next music track. The service monitors Kodi's audio player and supports Kodi playlist data or provider data.

The add-on manifest imports Kodi's `xbmc.python` API at version `3.0.0`.

## Install

1. Install the [Primez repository ZIP](https://primez-x.github.io/kodi.addons/repository.primez.addons/repository.primez.addons-1.0.0.zip) in Kodi.
2. Open **Add-ons → Install from repository → Primez Kodi Add-ons → Services**.
3. Install **Next Track** and open the add-on settings from Kodi's Services list.

See the [Primez repository site](https://primez-x.github.io/kodi.addons/) and the [central repository guide](https://github.com/primez-x/kodi.addons/blob/main/README.md) for repository setup.

## Playback and provider support

Next Track monitors Kodi audio playback. Kodi's music playlist supplies the next item when a track is queued. Repeat-one playback has no next item. The service ignores external players and optical-disc sources.

Providers can send Kodi's `Other.nexttrack_data` notification with `current_track` and `next_track` data. Optional fields include `notification_time`, `notification_offset`, `play_url`, and `play_info`. Support depends on each provider's implementation; the service does not make every music add-on compatible.

Kodi owns the existing playlist and advances to the next item. Next Track does not enqueue a duplicate for that path. If provider data supplies `play_url` and Kodi has no next playlist item, Next Track queues the URL. If playback does not advance, the service removes only that queue entry. When a provider supplies `play_info` without a URL, Next Track sends the play action back to that provider.

## Settings and workflow

- **Notification duration:** The setting controls the countdown window. The default is 15 seconds before track end, and the range is 5 to 60 seconds. Provider timing fields can override the window.
- **Log level:** Choose None, Info, or Debug.
- **Test widget:** Open the settings action **Show a Next Track test widget...** to preview the overlay.

The overlay displays track details and progress. If Kodi opens the music OSD, the overlay yields focus and continues as a toast.

## Source layout

- `resources/lib/service_entry.py` starts the service; `script_entry.py` starts script actions.
- `resources/lib/monitor.py`, `playbackmanager.py`, `playitem.py`, and `api.py` monitor playback, choose the next item, and manage provider or Kodi queue actions.
- `resources/lib/nexttrack.py` implements the overlay.
- `resources/settings.xml` defines settings.
- `resources/skins/default/1080i/` contains overlay layouts.
- `tests/` contains Python unit tests.

## Tests and maintenance

The configured publish test is:

```sh
python3 -m unittest discover -s tests
```

The tracked branch is `main`. A configured source webhook forwards tracked-branch pushes to the central publish workflow. If the webhook is absent or rejected, use the manual workflow described in the central guide. Enable local publish checks with `git config core.hooksPath .githooks`.

README-only edits do not need an add-on version bump. Changes to shipped behavior need a new `addon.xml` version and a matching first line in `<news>`. Follow the central [versioning rules](https://github.com/primez-x/kodi.addons/blob/main/VERSIONING.md).

Next Track started as a music-focused fork of [im85288's Up Next](https://github.com/im85288/service.upnext). The Primez fork is maintained in [primez-x/service.nexttrack](https://github.com/primez-x/service.nexttrack) and is licensed under [GPL-2.0-only](LICENSE).

The shared `utils.py` and `statichelper.py` modules are maintained in [`kodi.addons/tools/service_common/`](https://github.com/primez-x/kodi.addons/tree/main/tools/service_common/). From the central repository root, run `python3 tools/sync_service_common.py --check` to compare the copies. Run `python3 tools/sync_service_common.py` to copy changed masters to both source trees.
