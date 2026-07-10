"""Zero-configuration live-data tools: weather and news.

Both use free public endpoints (Open-Meteo, Google News RSS) that need no
API key, so they work in any deployment out of the box.
"""
from __future__ import annotations

import re

import httpx

from .base import ToolParam, tool

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog", 51: "light drizzle", 53: "drizzle",
    55: "dense drizzle", 61: "slight rain", 63: "rain", 65: "heavy rain",
    71: "slight snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "violent rain showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


@tool(
    "weather",
    "Get the current weather and a short forecast for a place (city name).",
    [ToolParam("location", "string", "City or place name, e.g. 'Dubai' or 'Paris, France'")],
    timeout=25,
)
async def weather(location: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1},
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return f"Couldn't find a place called '{location}'."
        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        label = ", ".join(filter(None, [place.get("name"), place.get("country")]))

        fc = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto", "forecast_days": 3,
            },
        )
        fc.raise_for_status()
        data = fc.json()

    cur = data.get("current", {})
    code = cur.get("weather_code", 0)
    lines = [
        f"Weather in {label}:",
        f"  Now: {cur.get('temperature_2m')}°C ({WEATHER_CODES.get(code, 'unknown')}), "
        f"feels like {cur.get('apparent_temperature')}°C, "
        f"humidity {cur.get('relative_humidity_2m')}%, wind {cur.get('wind_speed_10m')} km/h.",
    ]
    daily = data.get("daily", {})
    days = daily.get("time", [])
    for i, day in enumerate(days[:3]):
        dcode = daily["weather_code"][i]
        lines.append(
            f"  {day}: {daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
            f"{WEATHER_CODES.get(dcode, 'unknown')}."
        )
    return "\n".join(lines)


@tool(
    "news",
    "Get recent news headlines. Optionally about a topic; otherwise top headlines.",
    [
        ToolParam("topic", "string", "Topic to search, or empty for top headlines", required=False),
        ToolParam("count", "integer", "How many headlines (1-10)", required=False),
    ],
    timeout=25,
)
async def news(topic: str = "", count: int = 6) -> str:
    count = max(1, min(int(count), 10))
    if topic.strip():
        url = "https://news.google.com/rss/search"
        params = {"q": topic, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    else:
        url = "https://news.google.com/rss"
        params = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": "Mozilla/5.0 (JARVIS)"})
        resp.raise_for_status()

    items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)[:count]
    if not items:
        return "No headlines found."
    out = []
    for i, item in enumerate(items, 1):
        title = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        link = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        t = re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip() if title else "(untitled)"
        out.append(f"{i}. {t}\n   {link.group(1).strip() if link else ''}")
    header = f"Top headlines about '{topic}':" if topic.strip() else "Top headlines:"
    return header + "\n" + "\n".join(out)
