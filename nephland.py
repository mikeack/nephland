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
  edit [--port N]  Open the pin editor at http://localhost:8800 (add, move, edit, delete pins)
  hooks            Install the git pre-commit safety hook (run once per clone)
  date             Show the in-world date players see on the site
  date +N | -N     Move the in-world date forward/back N days, rebuild, check
  date set <year> <month-or-holiday> [day]   e.g.  date set 35 linfey 14
                                              or   date set 35 new-cycle

Data source: dm/ if it exists (private, git-ignored), otherwise sample/.
"""
import json, re, shutil, subprocess, sys, unicodedata, http.server, socketserver, functools
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
    cal = load_calendar()
    n_events = 0
    if cal:
        validate_calendar(cal, locs)
        vis_locs = {l["id"] for l in out_locs}
        out_events = []
        for ev in cal.get("events", []):
            vis = ev.get("revealed", False)
            if not dm and not vis:
                continue
            item = {k: ev[k] for k in ("id", "title", "description", "month", "day", "special", "year", "location") if k in ev}
            if not dm and item.get("location") not in vis_locs:
                item.pop("location", None)
            if dm:
                item["revealed"] = vis
                if ev.get("dm_notes"):
                    item["dm_notes"] = ev["dm_notes"]
            out_events.append(item)
        cdata = {k: cal[k] for k in ("name", "era", "era_name", "weekdays", "months", "special_days", "year") if k in cal}
        cdata["events"] = out_events
        cdata["mode"] = "dm" if dm else "player"
        if cal.get("today") and (dm or cal.get("show_today", True)):
            cdata["today"] = cal["today"]
        (out / "data" / "calendar-data.json").write_text(json.dumps(cdata, indent=1, ensure_ascii=False), encoding="utf-8")
        n_events = len(out_events)
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
          f"({len(out_maps)} maps, {len(out_locs)} locations{', ' + str(n_events) + ' events' if cal else ''}; source: {SRC.name}/)")


# ---------------------------------------------------------------- calendar
def load_calendar():
    p = SRC / "calendar.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_calendar(cal):
    (SRC / "calendar.json").write_text(json.dumps(cal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def flat_days(cal):
    months = {m["id"]: m for m in cal["months"]}
    flat = []
    for seg in cal["year"]:
        if "special" in seg:
            flat.append(("s", seg["special"], 1))
        else:
            m = months[seg["month"]]
            flat.extend(("m", m["id"], d) for d in range(seg.get("from", 1), seg.get("to", m["days"]) + 1))
    return flat


def validate_calendar(cal, locs):
    errs = []
    months, specials = {}, {}
    for m in cal["months"]:
        if m["id"] in months:
            errs.append(f"duplicate month id {m['id']!r}")
        months[m["id"]] = m
    for sd in cal["special_days"]:
        if sd["id"] in specials or sd["id"] in months:
            errs.append(f"duplicate id {sd['id']!r}")
        specials[sd["id"]] = sd
    wl = len(cal["weekdays"])
    covered = {mid: [] for mid in months}
    used = []
    year = cal["year"]
    for k, seg in enumerate(year):
        if "special" in seg:
            used.append(seg["special"])
            if seg["special"] not in specials:
                errs.append(f"year[{k}]: unknown special day {seg['special']!r}")
        elif seg.get("month") in months:
            m = months[seg["month"]]
            lo, hi = seg.get("from", 1), seg.get("to", m["days"])
            covered[m["id"]].extend(range(lo, hi + 1))
            nxt = year[k + 1] if k + 1 < len(year) else None
            if nxt and "special" in nxt and hi < m["days"] and hi % wl:
                errs.append(f"month {m['id']!r} is split after day {hi}; splits must land on a week boundary (multiple of {wl})")
        else:
            errs.append(f"year[{k}]: unknown month {seg.get('month')!r}")
    for mid, days in covered.items():
        if sorted(days) != list(range(1, months[mid]["days"] + 1)):
            errs.append(f"month {mid!r}: each of its {months[mid]['days']} days must appear exactly once in 'year'")
    for sid in specials:
        if used.count(sid) != 1:
            errs.append(f"special day {sid!r} must appear exactly once in 'year'")
    loc_ids = {l["id"] for l in locs}
    seen = set()
    for ev in cal.get("events", []):
        eid = ev.get("id")
        if not eid or eid in seen:
            errs.append(f"event id missing or duplicated: {eid!r}")
        seen.add(eid)
        if not ev.get("title"):
            errs.append(f"event {eid!r} has no title")
        if "special" in ev:
            if ev["special"] not in specials:
                errs.append(f"event {eid!r}: unknown special day {ev['special']!r}")
        elif ev.get("month") in months:
            if not 1 <= ev.get("day", 0) <= months[ev["month"]]["days"]:
                errs.append(f"event {eid!r}: day out of range")
        else:
            errs.append(f"event {eid!r}: needs either 'special' or 'month' + 'day'")
        if ev.get("location") and ev["location"] not in loc_ids:
            errs.append(f"event {eid!r}: unknown location {ev['location']!r}")
    t = cal.get("today")
    if t:
        ok = isinstance(t.get("year"), int) and (t.get("special") in specials or
             (t.get("month") in months and 1 <= t.get("day", 0) <= months[t["month"]]["days"]))
        if not ok:
            errs.append("'today' is invalid (use: date set <year> <month-or-holiday> [day])")
    if errs:
        sys.exit("calendar.json problems:\n  - " + "\n  - ".join(errs))


def ordinal(n):
    s = ["th", "st", "nd", "rd"]
    v = n % 100
    return f"{n}{s[(v - 20) % 10] if (v - 20) % 10 < 4 and not 10 <= v < 20 else s[0]}"


def describe(cal, year, entry):
    kind, ident, day = entry
    if kind == "s":
        name = next(s["name"] for s in cal["special_days"] if s["id"] == ident)
        return f"{name}, {year} {cal['era']}"
    name = next(m["name"] for m in cal["months"] if m["id"] == ident)
    wd = cal["weekdays"][(day - 1) % len(cal["weekdays"])]
    return f"{wd}, the {ordinal(day)} of {name}, {year} {cal['era']}"


def cmd_date(args):
    cal = load_calendar()
    if not cal:
        sys.exit(f"No calendar.json in {SRC.name}/")
    validate_calendar(cal, load()[1])
    flat = flat_days(cal)
    n = len(flat)
    t = cal.get("today")
    if args and args[0] == "set":
        if len(args) < 3:
            sys.exit("Usage: date set <year> <month-or-holiday> [day]")
        year = int(args[1])
        key = norm(args[2])
        month = next((m for m in cal["months"] if key in (norm(m["id"]), norm(m["name"]))), None)
        special = next((s for s in cal["special_days"] if key in (norm(s["id"]), norm(s["name"]))), None)
        if month:
            if len(args) < 4:
                sys.exit(f"Which day of {month['name']}? (1-{month['days']})")
            day = int(args[3])
            if not 1 <= day <= month["days"]:
                sys.exit(f"{month['name']} has days 1-{month['days']}")
            cal["today"] = {"year": year, "month": month["id"], "day": day}
        elif special:
            cal["today"] = {"year": year, "special": special["id"]}
        else:
            names = ", ".join([m["id"] for m in cal["months"]] + [s["id"] for s in cal["special_days"]])
            sys.exit(f"Unknown month or holiday {args[2]!r}. Try one of: {names}")
    elif args and re.fullmatch(r"[+-]\d+", args[0]):
        if not t:
            sys.exit("No 'today' set yet. Use: date set <year> <month-or-holiday> [day]")
        entry = ("s", t["special"], 1) if "special" in t else ("m", t["month"], t["day"])
        i = flat.index(entry) + int(args[0])
        year = t["year"] + i // n
        kind, ident, day = flat[i % n]
        cal["today"] = {"year": year, "special": ident} if kind == "s" else {"year": year, "month": ident, "day": day}
    elif args:
        sys.exit("Usage: date | date +N | date -N | date set <year> <month-or-holiday> [day]")
    else:
        if not t:
            sys.exit("No 'today' set yet. Use: date set <year> <month-or-holiday> [day]")
        entry = ("s", t["special"], 1) if "special" in t else ("m", t["month"], t["day"])
        print("Today:", describe(cal, t["year"], entry), f"(day {flat.index(entry) + 1} of {n})")
        print("Players see this date" if cal.get("show_today", True) else "Hidden from players (show_today is false)")
        return
    t = cal["today"]
    entry = ("s", t["special"], 1) if "special" in t else ("m", t["month"], t["day"])
    save_calendar(cal)
    print("Today is now:", describe(cal, t["year"], entry))
    build(False)
    check()
    print("Now commit and push to publish:  git add -A && git commit -m 'Advance date' && git push")


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
    cal = load_calendar()
    if cal:
        for m in cal["months"]:
            visible_words |= {m["name"].lower(), m["id"].lower()}
        for sd in cal["special_days"]:
            visible_words |= {sd["name"].lower(), sd["id"].lower()}
        for ev in cal.get("events", []):
            terms = {ev.get("title", "").lower(), ev.get("id", "").lower()}
            if ev.get("revealed", False):
                visible_words |= terms
            else:
                forbidden |= terms
                if ev.get("dm_notes"):
                    forbidden.add(ev["dm_notes"].lower())
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
    cal = load_calendar()
    if cal:
        print("CALENDAR EVENTS")
        for ev in cal.get("events", []):
            flag = "revealed" if ev.get("revealed") else "HIDDEN"
            print(f"  {ev['id']:<26} {flag:<9} {ev['title']}")


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
    cal = load_calendar()
    if cal:
        changed = False
        for ev in cal.get("events", []):
            if ev.get("id") in ids:
                ev["revealed"] = value
                hit.add(ev["id"])
                changed = True
        if changed:
            save_calendar(cal)
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


# ---------------------------------------------------------------- editor
PIN_TYPES = ("town", "landmark", "dungeon", "tavern", "shop")
LOC_FIELDS = ("id", "name", "map", "x", "y", "type", "opens", "revealed", "description", "note_url", "dm_notes")


def validate_locations(locs, maps):
    """Return (clean list, errors). Only known fields are kept, in a stable order."""
    if not isinstance(locs, list):
        return None, ["expected a list of locations"]
    map_ids = {m["id"] for m in maps["maps"]}
    errs, clean, seen = [], [], set()
    for i, l in enumerate(locs):
        if not isinstance(l, dict):
            errs.append(f"item {i} is not an object")
            continue
        lid = str(l.get("id", "")).strip()
        label = lid or f"item {i}"
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", lid):
            errs.append(f"{label}: id must be lowercase letters, numbers and hyphens")
        elif lid in seen:
            errs.append(f"{label}: another location already uses this id")
        seen.add(lid)
        if not str(l.get("name", "")).strip():
            errs.append(f"{label}: name is required")
        if l.get("map") not in map_ids:
            errs.append(f"{label}: unknown map {l.get('map')!r}")
        for k in ("x", "y"):
            v = l.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 100:
                errs.append(f"{label}: {k} must be a number from 0 to 100")
        if l.get("opens") and l["opens"] not in map_ids:
            errs.append(f"{label}: opens unknown map {l['opens']!r}")
        url = l.get("note_url")
        if url and not re.match(r"https?://", str(url)):
            errs.append(f"{label}: note_url must start with http:// or https://")
        item = {}
        for k in LOC_FIELDS:
            v = l.get(k)
            if k in ("x", "y") and isinstance(v, (int, float)):
                item[k] = round(float(v), 2)
            elif k == "revealed":
                item[k] = bool(v)
            elif isinstance(v, str):
                v = v.strip()
                if v:
                    item[k] = v
            elif v is not None and k not in ("opens", "note_url", "dm_notes", "description", "type"):
                item[k] = v
        clean.append(item)
    return clean, errs


def edit(port):
    import contextlib, io, os
    build(True)
    editor_js = ROOT / "viewer" / "editor.js"
    allowed_hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}

    def rebuild():
        out = io.StringIO()
        ok = True
        with contextlib.redirect_stdout(out):
            try:
                build(True)
                build(False)
                check()
            except SystemExit as e:
                ok = False
                if e.code not in (None, 0, 1):
                    print(e.code)
        return ok, out.getvalue().strip()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DM_OUT), **kw)

        def log_message(self, fmt, *args):
            pass

        def send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def local_only(self):
            if self.headers.get("Host") not in allowed_hosts:
                self.send_error(403, "Editor only answers on localhost")
                return False
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1] not in allowed_hosts:
                self.send_error(403, "Cross-site request refused")
                return False
            return True

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self):
            if not self.local_only():
                return
            path = self.path.split("?", 1)[0]
            if path == "/api/locations":
                maps, locs = load()
                return self.send_json(200, {"locations": locs, "maps": maps["maps"], "types": PIN_TYPES, "source": SRC.name})
            if path == "/editor.js":
                body = editor_js.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in ("/", "/index.html"):
                html = (DM_OUT / "index.html").read_text(encoding="utf-8")
                body = html.replace("</body>", '<script src="editor.js"></script>\n</body>').encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()

        def do_POST(self):
            if not self.local_only():
                return
            if self.path != "/api/locations":
                return self.send_error(404)
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self.send_json(415, {"ok": False, "errors": ["Expected JSON"]})
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= 2_000_000:
                return self.send_json(413, {"ok": False, "errors": ["Request too large"]})
            try:
                incoming = json.loads(self.rfile.read(n).decode("utf-8"))
            except ValueError:
                return self.send_json(400, {"ok": False, "errors": ["Not valid JSON"]})
            maps, old = load()
            clean, errs = validate_locations(incoming.get("locations") if isinstance(incoming, dict) else None, maps)
            if errs:
                return self.send_json(400, {"ok": False, "errors": errs})
            target = SRC / "locations.json"
            if old != clean:
                shutil.copy(target, SRC / "locations.backup.json")
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, target)
            ok, log = rebuild()
            self.send_json(200, {"ok": True, "check_ok": ok, "log": log, "count": len(clean)})

    if SRC.name == "sample":
        print("Note: no dm/ folder, so you are editing sample/ data.")
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"Port {port} is busy. Try: python3 nephland.py edit --port {port + 1}")
    with httpd:
        print(f"Pin editor at http://localhost:{port}  (editing {SRC.name}/locations.json, Ctrl+C to stop)")
        print("Saving rebuilds docs/ and runs the leak check. Publish with: git add -A && git commit -m '...' && git push")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nEditor stopped.")


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
    elif cmd == "edit": edit(int(a[a.index("--port") + 1]) if "--port" in a else 8800)
    elif cmd == "date": cmd_date(a[1:])
    elif cmd == "hooks":
        subprocess.check_call(["git", "config", "core.hooksPath", ".githooks"], cwd=ROOT)
        print("Pre-commit hook installed (.githooks/pre-commit).")
    else: print(__doc__)


if __name__ == "__main__":
    main()
