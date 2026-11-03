#!/usr/bin/env python3
"""Nephland map tool. Python 3 standard library only.

Commands:
  build            Build the PLAYER site into docs/ (this is what gets published)
  preview          Build the DM preview into dm-preview/ (never published)
  check            Verify docs/ contains nothing that is hidden or DM-only
  list             List all maps and locations with their revealed status
  reveal <id>...   Reveal a location and/or map by id, then rebuild + check
  hide <id>...     Hide a location and/or map by id, then rebuild + check
  serve [--dm]     Build and serve locally at http://localhost:8000
  hooks            Install the git pre-commit safety hook (run once per clone)

Data source: dm/ if it exists (private, git-ignored), otherwise sample/.
"""
import json, re, shutil, subprocess, sys, http.server, socketserver, functools
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dm" if (ROOT / "dm").exists() else ROOT / "sample"
PLAYER_OUT = ROOT / "docs"
DM_OUT = ROOT / "dm-preview"
DOMAIN = "nephland.mikeack.com"
TEXT_EXT = {".json", ".html", ".svg", ".js", ".css", ".txt", ".md", ""}


def load():
    maps = json.loads((SRC / "maps.json").read_text(encoding="utf-8"))
    locs = json.loads((SRC / "locations.json").read_text(encoding="utf-8"))
    return maps, locs


def save(maps, locs):
    dump = lambda o: json.dumps(o, indent=2, ensure_ascii=False) + "\n"
    (SRC / "maps.json").write_text(dump(maps), encoding="utf-8")
    (SRC / "locations.json").write_text(dump(locs), encoding="utf-8")


def revealed_map_ids(maps):
    """A map is visible only if it and every ancestor are revealed."""
    by = {m["id"]: m for m in maps["maps"]}
    ok = set()
    for m in maps["maps"]:
        cur, good = m, True
        while cur:
            if not cur.get("revealed", False):
                good = False
                break
            cur = by.get(cur.get("parent"))
        if good:
            ok.add(m["id"])
    return ok


def build(dm):
    maps, locs = load()
    out = DM_OUT if dm else PLAYER_OUT
    prev = out / "data" / "map-data.json"
    if not dm and SRC.name == "sample" and prev.exists() and "--force" not in sys.argv:
        try:
            if json.loads(prev.read_text(encoding="utf-8")).get("source") == "dm":
                sys.exit("Refusing to overwrite a docs/ built from your private dm/ data with the sample data.\n"
                         "The dm/ folder is missing on this machine. Restore it, or pass --force if you really mean it.")
        except ValueError:
            pass
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    ok = {m["id"] for m in maps["maps"]} if dm else revealed_map_ids(maps)
    if maps["root"] not in ok:
        sys.exit("The root map must be revealed.")
    out_maps, out_locs = [], []
    for m in maps["maps"]:
        if m["id"] not in ok:
            continue
        item = {k: m[k] for k in ("id", "title", "image", "parent") if k in m}
        if dm:
            item["revealed"] = m.get("revealed", False)
        out_maps.append(item)
    for l in locs:
        vis = l.get("revealed", False)
        if l["map"] not in ok or (not dm and not vis):
            continue
        item = {k: l[k] for k in ("id", "map", "name", "x", "y", "type", "description", "note_url") if k in l}
        opens = l.get("opens")
        if opens and opens in ok:
            item["opens"] = opens
        if dm:
            item["revealed"] = vis
            if l.get("dm_notes"):
                item["dm_notes"] = l["dm_notes"]
            if opens and opens not in ok:
                item["opens"] = opens
        out_locs.append(item)
    data = {"title": maps.get("title", "Nephland"), "root": maps["root"],
            "mode": "dm" if dm else "player", "source": SRC.name, "maps": out_maps, "locations": out_locs}
    (out / "data" / "map-data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "viewer" / "index.html", out / "index.html")
    (out / "maps").mkdir()
    for m in out_maps:
        src = SRC / "maps" / m["image"]
        if not src.exists():
            sys.exit(f"Missing map image: {src}")
        shutil.copy(src, out / "maps" / m["image"])
    if not dm:
        (out / "CNAME").write_text(DOMAIN + "\n")
        (out / ".nojekyll").write_text("")
    print(f"Built {'DM preview' if dm else 'PLAYER site'} -> {out.relative_to(ROOT)}  "
          f"({len(out_maps)} maps, {len(out_locs)} locations; source: {SRC.name}/)")


def check():
    maps, locs = load()
    ok = revealed_map_ids(maps)
    shown = lambda l: l.get("revealed", False) and l["map"] in ok
    visible_words = set()
    for l in locs:
        if shown(l):
            visible_words |= {l["name"].lower(), l["id"].lower()}
    for m in maps["maps"]:
        if m["id"] in ok:
            visible_words |= {m["title"].lower(), m["id"].lower(), m["image"].lower()}
    forbidden = set()
    for l in locs:
        if not shown(l):
            forbidden |= {l["name"].lower(), l["id"].lower()}
        if l.get("dm_notes"):
            forbidden.add(l["dm_notes"].lower())
    for m in maps["maps"]:
        if m["id"] not in ok:
            forbidden |= {m["title"].lower(), m["id"].lower(), m["image"].lower()}
    forbidden = {f for f in forbidden if f and f not in visible_words}
    if not PLAYER_OUT.exists():
        sys.exit("docs/ does not exist. Run build first.")
    def hit(term, text):
        return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None
    problems = []
    for p in PLAYER_OUT.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(PLAYER_OUT)).lower()
        for f in forbidden:
            if hit(f, rel):
                problems.append(f"filename {rel!r} contains hidden term {f!r}")
        if p.suffix.lower() in TEXT_EXT:
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            for f in forbidden:
                if hit(f, text):
                    problems.append(f"{rel}: contains hidden term {f!r}")
    if problems:
        print("CHECK FAILED - do not publish:")
        for pr in problems:
            print("  -", pr)
        sys.exit(1)
    print(f"Check passed: docs/ contains none of {len(forbidden)} hidden/DM-only terms.")


def list_all():
    maps, locs = load()
    ok = revealed_map_ids(maps)
    print("MAPS")
    for m in maps["maps"]:
        flag = "revealed" if m["id"] in ok else "HIDDEN"
        print(f"  {m['id']:<18} {flag:<9} {m['title']}  (parent: {m.get('parent')})")
    print("LOCATIONS")
    for l in locs:
        flag = "revealed" if l.get("revealed") else "HIDDEN"
        print(f"  {l['id']:<18} {flag:<9} {l['name']}  [map: {l['map']}]" + (f" -> opens {l['opens']}" if l.get("opens") else ""))


def set_revealed(ids, value):
    if not ids:
        sys.exit("Give at least one id (see: python3 nephland.py list)")
    maps, locs = load()
    hit = set()
    for l in locs:
        if l["id"] in ids:
            l["revealed"] = value
            hit.add(l["id"])
    for m in maps["maps"]:
        if m["id"] in ids:
            m["revealed"] = value
            hit.add(m["id"])
    missing = set(ids) - hit
    if missing:
        sys.exit(f"No location or map with id: {', '.join(sorted(missing))}")
    save(maps, locs)
    print(f"{'Revealed' if value else 'Hid'}: {', '.join(sorted(hit))}")
    build(False)
    check()
    print("Now commit and push to publish:  git add -A && git commit -m 'Update reveals' && git push")


def serve(dm):
    build(dm)
    d = DM_OUT if dm else PLAYER_OUT
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    with socketserver.TCPServer(("", 8000), handler) as httpd:
        print("Serving at http://localhost:8000  (Ctrl+C to stop)")
        httpd.serve_forever()


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "help"
    if cmd == "build": build(False)
    elif cmd == "preview": build(True)
    elif cmd == "check": check()
    elif cmd == "list": list_all()
    elif cmd == "reveal": set_revealed(a[1:], True)
    elif cmd == "hide": set_revealed(a[1:], False)
    elif cmd == "serve": serve("--dm" in a)
    elif cmd == "hooks":
        subprocess.check_call(["git", "config", "core.hooksPath", ".githooks"], cwd=ROOT)
        print("Pre-commit hook installed (.githooks/pre-commit).")
    else: print(__doc__)


if __name__ == "__main__":
    main()
