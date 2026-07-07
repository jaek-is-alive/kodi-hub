# kodi-hub

Personal Kodi setup: **Jacob's Hub** (`plugin.video.jacobshub`) — one addon that fronts
Umbrella + The Loop with combined menus, one-tap search, debrid connect buttons, and
CocoScrapers auto-configuration — plus a personal repository addon so it auto-updates
from this GitHub repo.

## Layout

```
plugin.video.jacobshub/     the hub addon
  default.py                router (rarely needs touching)
  resources/menu.json       WHAT the menus show — edit freely
  resources/targets.json    upstream addon IDs/actions (verified 2026-07-06)
  resources/presets.json    one-tap settings presets (CocoScrapers wiring etc.)
repository.jacobshub/       repo addon → serves zips/ via GitHub Pages
tools/build_repo.py         zips addons + regenerates zips/addons.xml(.md5)
tools/vendor.py             downloads backend addons + deps into zips/ (see below)
tools/make_icon.py          regenerates icon.png/fanart.png (pure stdlib)
zips/                       generated artifacts (incl. vendored addons) — commit them
```

## First-time GitHub setup

1. Create a repo named `kodi-hub` on your **personal** GitHub (private works only if
   you make it public or use a token URL — Kodi fetches anonymously, so **public** is
   the simple path; there's nothing sensitive here).
2. The repo URLs in `repository.jacobshub/addon.xml` already point at jaek-is-alive/kodi-hub.
3. `python3 tools/build_repo.py && git add -A && git commit -m 'build' && git push`

## Installing on a Kodi box

Prereqs (installed normally from their own repos): Umbrella, CocoScrapers, The Loop.
The hub deep-links into them; it deliberately does **not** declare them as
dependencies so it installs cleanly anywhere and just greys out missing sections.

1. Download the repository zip to the device:
   `https://jaek-is-alive.github.io/kodi-hub/repository.jacobshub/repository.jacobshub-1.0.0.zip`
2. Add-ons → Install from zip file → pick the downloaded zip.
3. Add-ons → Install from repository → Jacob's Hub Repository → Video add-ons → Jacob's Hub.

Note: do **not** add the Pages URL as a Kodi "file source" — GitHub Pages serves
the landing page for a directory, not a browsable file list, so the zip won't show.
Just download the zip above. Auto-updates after install don't need a listing: Kodi
fetches `addons.xml` and each versioned zip by exact URL.

From then on, bumping the `version=` in `plugin.video.jacobshub/addon.xml` and
pushing = CI rebuilds `zips/`, redeploys Pages, and every box auto-updates.

## Backend add-ons (vendored) + the Setup button

This repo doesn't just launch Umbrella / CocoScrapers / The Loop — it **serves**
them. `tools/vendor.py` downloads those three plus their non-official
dependencies (ResolveURL, JetExtractors, LoopTV, etc.) into `zips/`, and
`build_repo.py` lists them all in `addons.xml`, so one repo provides everything.

Anything in the **official Kodi repo** (requests, inputstreamhelper, pyamf,
dailymotion, googledrive, python.twitch, ...) is deliberately NOT vendored —
Kodi resolves those automatically at install.

In the addon, **Tools & Setup → ⚙ Setup** installs the three backend add-ons in
one tap (from this repo + the official repo for the rest), then offers to wire
CocoScrapers into Umbrella and enable the recommended providers. Kodi may ask you
to confirm each install.

**Refreshing the vendored versions** (no auto-refresh is set up):

```
python3 tools/vendor.py       # re-download current upstream versions into zips/
python3 tools/build_repo.py   # rebuild addons.xml
git add -A && git commit -m 'refresh vendored addons' && git push
```

If `vendor.py` lists an addon under MISSING, it's almost always in the official
Kodi repo (fine — leave it). Only add a source for a genuinely non-official dep.

## Day-2 editing

- **Add/remove/reorder menu items:** edit `resources/menu.json`. Item forms:
  - `{"label": "...", "path": "plugin://..."}` — deep-link into another addon
  - `{"label": "...", "menu": "submenu_id"}` — open another menu.json section
  - `{"label": "...", "run": "auth.torbox"}` — fire a RunPlugin target from targets.json
  - `{"label": "...", "hub": "search", "params": {"kind": "movies"}}` — internal action
  - add `"requires": "plugin.video.umbrella"` to grey the item out when missing
- **Find new deep-link URLs:** in Kodi, favourite any list inside any addon, then read
  `userdata/favourites.xml` — it contains the exact `plugin://` URL.
- **Upstream renamed an action?** Fix it in `targets.json`; no code change.

## Tools menu (what the buttons do)

- **Connect AllDebrid / TorBox / Trakt / RD / PM** — triggers Umbrella's own device-code
  auth flows (`?action=ad_Authorize`, `tb_Authorize`, …).
- **Status** — shows installed addons + which debrid services have tokens in Umbrella.
- **Auto-configure CocoScrapers** — sets Umbrella's `provider.external.enabled/module/name`
  to point at `script.module.cocoscrapers` and a 60s scrape timeout.
- **Recommended providers** — enables the reliable CocoScrapers torrent providers.

## Verified upstream facts (2026-07-06)

- Umbrella 6.7.79: search is pre-fillable via `?action=movieSearchterm&name=<q>` /
  `tvSearchterm`; debrid tokens live in `alldebridtoken`/`torboxtoken`/etc.
- CocoScrapers 1.0.32: torrent providers only; toggles are `provider.<name>`.
- The Loop 8.0b (`plugin.video.the-loop`, loopaddon.uk): routing-style URLs;
  menus are remote JSON — `plugin://plugin.video.the-loop/get_list/<json-url>`;
  search route `/ls3arch3/search/<query>`. Note: loopaddon.uk redirects non-Kodi
  user agents, so test URLs from Kodi, not curl.
