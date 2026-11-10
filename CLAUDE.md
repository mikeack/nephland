# Nephland

An interactive map and calendar of Mike's D&D world, **Nephland**, published for his players at
**https://nephland.mikeack.com** (GitHub Pages, served from `docs/` on `main`).

Click a town on the world map and its town map loads. Pins show tooltips and link to
more detail. Players only see what Mike has revealed. Mike unlocks places as the story
progresses.

## The one rule that matters

**This repo is PUBLIC. Anything committed here is world-readable.**

- Hidden locations, hidden maps and DM notes live ONLY in `dm/` (git-ignored, never committed).
- `docs/` is the published player site. It is **generated** by `python3 nephland.py build`.
  Never edit anything in `docs/` by hand.
- Before every commit or push, run `python3 nephland.py check`. If it fails, stop and
  fix it. Do not publish. (The git pre-commit hook enforces this; install it once per
  clone with `python3 nephland.py hooks`.)
- Never commit `dm/` or `dm-preview/`. Never paste DM-only text into `viewer/`, `sample/`,
  this file, commit messages, or anything else that is committed.
- Do not use `--force` on `build` unless Mike explicitly says so.

## Layout

| Path | What it is | Committed? |
|---|---|---|
| `dm/maps.json`, `dm/locations.json`, `dm/calendar.json`, `dm/maps/` | Mike's real data and map images, including hidden things | **No** (private) |
| `sample/` | Placeholder data and SVG maps so the project runs on a fresh clone | Yes |
| `viewer/index.html` | The whole viewer: one self-contained page, no dependencies, no CDN | Yes |
| `viewer/editor.js` | Pin editor, injected only by `nephland.py edit` (localhost). Never copied to `docs/` | Yes |
| `viewer/studio.html` | Map studio at `/studio` on `nephland.py edit`. Never copied to `docs/` | Yes |
| `dm/mapdocs/<id>/` | Studio layers: one grayscale PNG per layer plus `map.json` | **No** (private) |
| `nephland.py` | Build, leak check, reveal/hide, local server. Python 3 stdlib only | Yes |
| `docs/` | Generated player site, published by GitHub Pages | Yes (generated) |
| `dm-preview/` | Generated DM view with hidden items shown dashed | No |
| `source-material/` | Mike's raw notes and exports for reference | No |

`nephland.py` reads `dm/` if it exists, otherwise `sample/`. A fresh clone without `dm/`
builds the sample map. `build` refuses to overwrite a `docs/` that was built from `dm/`
with sample data.

## Commands

```
python3 nephland.py serve --dm      # DM preview at http://localhost:8000 (everything visible)
python3 nephland.py serve           # exactly what players will see
python3 nephland.py edit            # pin editor at http://localhost:8800 (add/move/edit/hide/delete pins)
python3 nephland.py list            # every map and location with its revealed status
python3 nephland.py reveal <id>...  # reveal a location, map and/or calendar event, rebuild, leak-check
python3 nephland.py hide <id>...    # undo a reveal
python3 nephland.py date [+N|-N|set Y M [D]]  # in-world date, rebuilds + checks
python3 nephland.py build           # rebuild docs/ (player site)
python3 nephland.py check           # verify docs/ contains nothing hidden
```

Mike publishes content with the **Publish** button in the pin editor. It commits only `docs/`, with
the fixed message "Update player site" so hidden names never reach public history, then pushes.
Publish also copies `dm/` to the `DM Backups` folder in Mike's iCloud Nephland folder (10 newest kept).
To publish by hand: `git add docs && git commit -m "Update player site" && git push`.
GitHub Pages updates in about a minute.

## Data format

`maps.json`
```json
{ "title": "Nephland", "root": "world",
  "maps": [ { "id": "world", "title": "The Three Realms", "image": "world.png", "parent": null, "revealed": true },
            { "id": "err",   "title": "Err",              "image": "err.png",   "parent": "world", "revealed": true } ] }
```

`locations.json` is an array of:
```json
{ "id": "err", "name": "Err", "map": "world", "x": 50, "y": 52, "type": "town",
  "opens": "err", "revealed": true, "description": "What players see in the tooltip.",
  "note_url": "optional link for a Read more button", "dm_notes": "DM-only, never published" }
```

- `x`, `y` are percentages (0–100) of the map image, from the top-left.
- `opens` is the id of a map to load when the pin is clicked. Optional.
  In the pin editor, changing a pin's visibility also changes the map it opens.
- `type`: `town`, `landmark`, `dungeon`, `tavern`, `shop` (anything else gets the default pin).
- Ids are lowercase with hyphens, and unique across maps and locations.
- A map is visible to players only if it **and all its ancestors** are `revealed`.
  Locations on a hidden map are never published, even if marked revealed.
- The root map can carry an optional `"globe": {"lat": 12, "lon": 0, "height": 70, "trim": 3.3}`. It places
  the map on the planet in the Globe view: `lat`/`lon` are where the map's centre sits, `height` is how many
  degrees tall the image is, and `trim` is the percentage of the image width cut from each edge (it removes the
  studio's border frame). Those four values are the defaults, so leave it out unless you want to change one.
- Images go in `dm/maps/`. PNG, JPG, WebP or SVG. Keep each under about 3 MB (the site is
  served to phones). Use descriptive filenames.

Finding coordinates: run `python3 nephland.py serve --dm`, then **Shift+click** a spot on the map.
It copies `"x": 42.3, "y": 61.8` to the clipboard.

## Calendar (`calendar.json`)

Mike's in-world calendar: 13 months of 24 days (6-day weeks), special days, an `era` label
(PW, Post Wilhelm), and a `today` date. Shown at `#calendar`, `#calendar/<year>`, `#calendar/<year>/<month-or-special-id>[/<day>]`.

- `months`: id, name, season, days, description. `special_days`: id, name, description.
- `year`: the ordered list of months and special days. A special day can split a month with
  `{"month":"ubrin","to":12}`, special, `{"month":"ubrin","from":13}`. Splits must fall on a week boundary (multiple of 6).
- `events`: id, title, description, `month`+`day` or `special`, optional `year` (omit = repeats every year),
  optional `location` (a location id, adds a "Show on the map" link), `revealed` (default hidden), `dm_notes`.
- `today`: `{"year":35,"month":"linfey","day":14}` or `{"year":35,"special":"new-cycle"}`; `show_today:false` hides it from players.
- Months and special days are always public. Hidden events and `dm_notes` never reach `docs/`; `check` scans for them.
- Pins can be linked to directly with `#<mapId>@<locationId>`.

## Globe view

`#globe` (the **Globe** tab) wraps the root map onto a planet as a second way to look at it. It reads the same
`map-data.json` and map image as the flat map, so it shows exactly the pins players can already see and nothing
else: revealing, hiding or repainting changes both views on the next build. It is plain WebGL inside
`viewer/index.html` (no library), and the tab hides itself on a device without WebGL. Only the real map image is
drawn. Everything off the map is open sea, so never add invented coastlines for lands that have no map yet.

## Map studio

`http://localhost:8800/studio` paints maps as layers. It redraws the whole map as original SVG
from the layers in a fixed order, so roads stay under trees and buildings. All art in the SVG is
generated by `studio.html`. Don't add third-party map assets to it.

Bridges are stamps, not paint: `map.json` keeps them as `bridges: [{x,y,a,len,w}]` (mask units, angle in
degrees) so they stay editable. They draw above roads and under buildings, trees and mountains.

A JSON export from Watabou's Medieval Fantasy City Generator imports without tracing: buildings and water go
into `vectors.json`, and roads, walls, fields and trees go into the editable layers.

Importing a town image traces each building, the water and roads at full size into `vectors.json`, and other colors into layers.
The result still copies the source map's layout, so check the source's terms before publishing.

## Adding a town (the usual task)

1. Put the town map image in `dm/maps/`.
2. Add it to `dm/maps.json` with `parent` set to the map it belongs to.
3. Add a location on the parent map with `"opens"` set to the new map id.
4. Add the town's own pins on the new map.
5. Preview with `serve --dm`, set `revealed` when players should see it, then
   `build`, `check`, commit and push.

## Hosting

- GitHub Pages: Settings → Pages → Deploy from branch → `main` / `/docs`.
- Custom domain `nephland.mikeack.com` (the `docs/CNAME` file is written by `build`).
- DNS: a `CNAME` record, name `nephland`, pointing to `<github-username>.github.io`.
- Enforce HTTPS once the certificate is issued.

## Conventions

- Keep the viewer a single dependency-free HTML file. No frameworks, no CDN, no
  analytics, and no external fonts (players' privacy, and it keeps working offline).
- All text from data is inserted with `textContent`, never `innerHTML`.
- Test viewer changes on a phone-sized viewport as well as desktop. Tapping a pin on touch
  shows a card first. On a mouse, clicking a town opens its map directly.
- Mike's source notes (a Notion export converted to markdown) are the reference for
  names and descriptions. They contain DM secrets, so keep them out of the repo.
- Real data goes in `dm/` (start with `cp -R sample dm`). Never edit `docs/` by hand.
- Style: plain, short commit messages (e.g. "Reveal Hommlet").
