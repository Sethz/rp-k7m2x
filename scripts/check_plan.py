"""Vergleicht den veröffentlichten Tagesplan (Taoticket) mit plan.json und schreibt plan_check.json.
Bei Abweichungen wird plan_diff.md erzeugt (daraus macht die Action ein GitHub-Issue)."""
import json, re, html, urllib.request, datetime as dt

URL = "https://www.taoticket.com/en_AU/co/costa-cruises/croc/3/SVND8A03"
plan = json.load(open("plan.json"))
known = sorted({p["port"] for p in plan} | {"Navigation"}, key=len, reverse=True)
DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
MON = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August",
                                   "September","October","November","December"], 1)}
T = r"(\d{1,2}:\d{2}\s*[AP]M|not found)"

def h24(s):
    if not s or s.startswith("not"): return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP])M", s)
    h = int(m.group(1)) % 12 + (12 if m.group(3) == "P" else 0)
    return f"{h:02d}:{m.group(2)}"

status = {"checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "source": URL}
try:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Reiseplan-Check)"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)))
    found = {}
    for m in re.finditer(rf"({DAYS}),? (\d{{1,2}}) ({'|'.join(MON)}) (\d{{4}})", text):
        rest = text[m.end():m.end() + 120]
        times = re.match(rf"\s*(?:{T})?\s*(?:-\s*(?:{T})?)?\s*", rest)
        a, b = times.group(1), times.group(2)
        rest = rest[times.end():]
        name = next((k for k in known if rest.startswith(k)), None)
        if name is None:
            if not (a or b):   # kein Zeitstempel -> kein Eintrag im Tagesplan (z. B. Navigationsleiste)
                continue
            name = "NEU: " + " ".join(rest.split()[:3])
        if name == "Navigation": continue
        d = dt.date(int(m.group(4)), MON[m.group(3)], int(m.group(2))).isoformat()
        if d in found and not found[d]["port"].startswith("NEU"): continue
        found[d] = {"date": d, "port": name, "arr": h24(a), "dep": h24(b)}
    status["parsed_ports"] = len(found)
    if len(found) < 40:
        status["result"] = "Quelle nicht lesbar (zu wenige Häfen erkannt) – nichts geändert"
    else:
        mine = {p["date"]: p for p in plan}
        diffs = []
        for d in sorted(set(mine) | set(found)):
            a, b = mine.get(d), found.get(d)
            fmt = lambda x: f'{x["port"]} {x["arr"] or "–"}–{x["dep"] or "–"}' if x else "Seetag / kein Hafen"
            if not a or not b or a["port"] != b["port"] or a["arr"] != b["arr"] or a["dep"] != b["dep"]:
                diffs.append(f"| {d} | {fmt(a)} | {fmt(b)} |")
        status["result"] = "unverändert" if not diffs else f"{len(diffs)} Abweichung(en)"
        status["diffs"] = diffs
        if diffs:
            open("plan_diff.md", "w").write(
                "Die Automatik hat Abweichungen zwischen dem Reiseplan in der App und dem veröffentlichten Plan gefunden.\n\n"
                "| Datum | In der App | Veröffentlicht |\n|---|---|---|\n" + "\n".join(diffs) +
                f"\n\nQuelle: {URL}\n\nBitte prüfen und Claude Bescheid geben, dann wird die App angepasst.")
except Exception as e:
    status["result"] = f"Fehler beim Abruf: {e}"
json.dump(status, open("plan_check.json", "w"), ensure_ascii=False, indent=1)
print(status)
