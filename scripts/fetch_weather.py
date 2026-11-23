"""Holt die Open-Meteo-Vorhersage (16 Tage) für kommende Häfen sowie Wien/Lienz und schreibt weather.json."""
import json, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

API = "https://api.open-meteo.com/v1/forecast"
HOME = {"Wien": (48.21, 16.37, None), "Lienz · Zettersfeld": (46.855, 12.79, 1800)}

def get(lat, lon, elev=None):
    url = (f"{API}?latitude={lat:.2f}&longitude={lon:.2f}&daily=temperature_2m_max,temperature_2m_min,weather_code"
           f"&forecast_days=16&timezone=auto" + (f"&elevation={elev}" if elev else ""))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.load(r)["daily"]
            return {day: {"mx": round(mx), "mn": round(mn), "c": c}
                    for day, mx, mn, c in zip(d["time"], d["temperature_2m_max"], d["temperature_2m_min"], d["weather_code"])
                    if mx is not None}
        except Exception as e:
            print("Fehler", url, e); time.sleep(5)
    return {}

stops = json.load(open("stops.json"))
now = dt.datetime.now(dt.timezone.utc)
horizon = now + dt.timedelta(days=16)
ports = {}
for s in stops:
    tz = ZoneInfo(s["tz"])
    start = s["arr"] or s["dep"]; end = s["dep"] or s["arr"]
    t0 = dt.datetime.fromtimestamp(start / 1000, dt.timezone.utc)
    t1 = dt.datetime.fromtimestamp(end / 1000, dt.timezone.utc)
    if t1 < now - dt.timedelta(days=1) or t0 > horizon:
        continue
    days, d = set(), t0.astimezone(tz).date()
    while d <= t1.astimezone(tz).date():
        days.add(d.isoformat()); d += dt.timedelta(days=1)
    fc = get(s["lat"], s["lon"])
    for day in days:
        if day in fc:
            ports[f'{s["key"]}|{day}'] = fc[day]
home = {name: get(*v) for name, v in HOME.items()}

# --- Seetage: geschätzte Schiffsposition (gleiche Rechnung wie die Seite) ---
import math
def vec(la, lo):
    la, lo = math.radians(la), math.radians(lo)
    return (math.cos(la)*math.cos(lo), math.cos(la)*math.sin(lo), math.sin(la))
def ang(a, b):
    return math.acos(max(-1, min(1, sum(x*y for x, y in zip(a, b)))))
def slerp(a, b, f):
    w = ang(a, b)
    if w < 1e-9: return a
    s1, s2 = math.sin((1-f)*w)/math.sin(w), math.sin(f*w)/math.sin(w)
    return tuple(x*s1 + y*s2 for x, y in zip(a, b))
def latlon(p):
    return math.degrees(math.asin(p[2])), math.degrees(math.atan2(p[1], p[0]))
def position(t):
    for i in range(len(stops)-1):
        a, b = stops[i], stops[i+1]
        if a["dep"] and b["arr"] and a["dep"] <= t < b["arr"]:
            pts = [vec(a["lat"], a["lon"])] + [vec(*w) for w in a.get("wp", [])] + [vec(b["lat"], b["lon"])]
            tot = sum(ang(pts[k], pts[k+1]) for k in range(len(pts)-1))
            d = (t - a["dep"]) / (b["arr"] - a["dep"]) * tot
            for k in range(len(pts)-1):
                w = ang(pts[k], pts[k+1])
                if d <= w or k == len(pts)-2:
                    return latlon(slerp(pts[k], pts[k+1], min(1, d/w) if w else 0))
                d -= w
    return None
sea, coords = {}, []
day0 = now.date()
for k in range(16):
    d = day0 + dt.timedelta(days=k)
    t = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp()*1000)
    p = position(t)
    if p: coords.append((d.isoformat(), p))
if coords:
    url = (f"{API}?latitude={','.join(f'{p[0]:.2f}' for _, p in coords)}&longitude={','.join(f'{p[1]:.2f}' for _, p in coords)}"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code&forecast_days=16&timezone=GMT")
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            res = json.load(r)
        res = res if isinstance(res, list) else [res]
        for (day, p), loc in zip(coords, res):
            dd = loc["daily"]
            if day in dd["time"]:
                j = dd["time"].index(day)
                if dd["temperature_2m_max"][j] is not None:
                    sea[day] = {"mx": round(dd["temperature_2m_max"][j]), "mn": round(dd["temperature_2m_min"][j]),
                                "c": dd["weather_code"][j], "lat": round(p[0], 1), "lon": round(p[1], 1)}
    except Exception as e:
        print("Seewetter-Fehler", e)
json.dump({"generated": int(now.timestamp() * 1000), "ports": ports, "home": home, "sea": sea},
          open("weather.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(ports), "Hafentage,", len(sea), "Seetage mit Vorhersage")
