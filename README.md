# Nephland

An interactive, player-facing map and calendar for the world of Nephland. A world map with clickable
towns that open town maps, pins with tooltips, the in-world calendar with its holidays, and a
DM-controlled "reveal" system.

Live site: https://nephland.mikeack.com

## Run it locally

```
python3 nephland.py serve --dm    # your view, with hidden places shown dashed
python3 nephland.py serve         # the player view
```

Open http://localhost:8000. Needs only Python 3.

## Add, move and edit pins

```
python3 nephland.py edit          # pin editor at http://localhost:8800
```

Click **+ Add pin**, then click the map, fill in the form and save. Click any pin and choose
**Edit pin** to change its text, tick *Visible to players*, move it or delete it. Each save writes
`dm/locations.json` (the previous version is kept in `dm/locations.backup.json`), rebuilds the
player site and runs the leak check. Then commit and push to publish. The editor only answers on
this computer and is never part of the published site.

## Paint maps

With `python3 nephland.py edit` running, open http://localhost:8800/studio. Pick a map, or click
**New map** and choose a world or town map, then paint with the brushes on the left. Land, rivers,
roads, forests, mountains and hills are separate layers, and town maps have streets, buildings,
fields, trees and walls. Roads and streets always draw under trees and buildings.

To convert an existing town map, drag an image onto the studio or click **Import town map**. The
studio samples its main colors and guesses what each one is. Correct any guess in the panel and the
map updates. Then touch up with the brushes and save.

**Save** keeps your layers in `dm/mapdocs/` and writes `dm/maps/<id>.svg`. **Use on site** also
points the site at that map. New maps start hidden, so reveal them when players should see them.

## Reveal something to your players

```
python3 nephland.py list
python3 nephland.py reveal hommlet
git add -A && git commit -m "Reveal Hommlet" && git push
```

## Move the in-world date forward

```
python3 nephland.py date              # show today's in-world date
python3 nephland.py date +1           # advance one day (-1 goes back)
python3 nephland.py date set 35 linfey 14
python3 nephland.py date set 35 new-cycle    # a special day
```
Then commit and push. Hide the date from players with `"show_today": false` in `calendar.json`.

## First-time setup

1. Install the safety hook once: `python3 nephland.py hooks`
2. Create a **public** GitHub repo named `nephland` and push this folder to it.
3. Repo → Settings → Pages → Source: *Deploy from a branch* → `main` and `/docs`.
4. Same page → Custom domain: `nephland.mikeack.com`.
5. At your domain registrar's DNS settings add a record:
   - Type `CNAME`, Name/Host `nephland`, Value `<your-github-username>.github.io`
6. When GitHub shows the DNS check as passed, tick **Enforce HTTPS**.

Your real maps, calendar and hidden things go in a private `dm/` folder: `cp -R sample dm`, then edit (see `CLAUDE.md`).
Until you create it, the site shows the placeholder sample map.
