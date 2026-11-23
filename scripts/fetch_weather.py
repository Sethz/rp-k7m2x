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
json.dump({"generated": int(now.timestamp() * 1000), "ports": ports, "home": home},
          open("weather.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(ports), "Hafentage mit Vorhersage")
