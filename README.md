# Nephland Interactive Map

An interactive, player-facing map of the world of Nephland. A world map with clickable
towns that open town maps, pins with tooltips, and a DM-controlled "reveal" system.

Live site: https://nephland.mikeack.com

## Run it locally

```
python3 nephland.py serve --dm    # your view, with hidden places shown dashed
python3 nephland.py serve         # the player view
```

Open http://localhost:8000. Needs only Python 3.

## Reveal something to your players

```
python3 nephland.py list
python3 nephland.py reveal hommlet
git add -A && git commit -m "Reveal Hommlet" && git push
```

## First-time setup

1. Install the safety hook once: `python3 nephland.py hooks`
2. Create a **public** GitHub repo named `nephland-map` and push this folder to it.
3. Repo → Settings → Pages → Source: *Deploy from a branch* → `main` and `/docs`.
4. Same page → Custom domain: `nephland.mikeack.com`.
5. At your domain registrar's DNS settings add a record:
   - Type `CNAME`, Name/Host `nephland`, Value `<your-github-username>.github.io`
6. When GitHub shows the DNS check as passed, tick **Enforce HTTPS**.

Your real maps and hidden places go in a private `dm/` folder (see `CLAUDE.md`).
Until you create it, the site shows the placeholder sample map.
