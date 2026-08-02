"""
Draws four stat SVGs from your own contribution data, in the same visual
language as the portrait:
  - assets/stats.svg       hero total + weekly bar sparkline
  - assets/streak.svg      current + longest streak
  - assets/languages.svg   top languages by bytes
  - assets/year.svg        the year at one character per day, portrait's ramp

Stdlib only (urllib) -- nothing to break in CI. Runs daily via
.github/workflows/refresh-stats.yml using the workflow's built-in
GITHUB_TOKEN (no personal access token needed).

Two determinism traps this avoids:
  1. The contribution window is pinned to whole UTC days (today-364d
     00:00:00Z -> today 23:59:59Z). Left floating, two runs minutes apart
     can bucket a day into different weeks and shift the sparkline.
  2. Repositories are filtered to privacy: PUBLIC, so language percentages
     don't depend on who/what token ran the script.

Required env vars: GITHUB_TOKEN, GH_LOGIN.
Optional: STATS_FONT_PATH (subset woff2 to embed, same as the portrait).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from svgutils import RAMP, FONT_FAMILY, font_face_css, escape_svg_text

API_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, isFork: false,
                 ownerAffiliations: OWNER) {
      nodes {
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch(login: str, token: str) -> dict:
    now = datetime.now(timezone.utc)
    to = now.replace(hour=23, minute=59, second=59, microsecond=0)
    frm = (to - timedelta(days=364)).replace(hour=0, minute=0, second=0)
    data = gql(QUERY, {
        "login": login,
        "from": frm.isoformat().replace("+00:00", "Z"),
        "to": to.isoformat().replace("+00:00", "Z"),
    }, token)
    return data["user"]


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    longest = run = 0
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    current = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current += 1
        else:
            break
    return current, longest


def weekly_totals(weeks: list[dict]) -> list[int]:
    return [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]


def top_languages(repos: list[dict], n: int = 5) -> list[tuple[str, int, str]]:
    totals: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b8b8b"
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(name, size, colors[name]) for name, size in ranked]


def svg_wrap(width: int, height: int, body: str, font_path: str | None,
             font_size: float = 13) -> str:
    font_css = font_face_css(font_path)
    family = f"'{FONT_FAMILY}', monospace" if font_css else "monospace"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
  viewBox="0 0 {width} {height}">
  <style>{font_css} text {{ font-family: {family}; font-size: {font_size}px; fill: #c9d1d9; }}</style>
  <rect x="0" y="0" width="{width}" height="{height}" fill="#0d1117" rx="6" />
  {body}
</svg>"""


def hero_svg(total: int, weekly: list[int], font_path) -> str:
    w, h = 480, 140
    bars = weekly[-26:] or [0]
    maxv = max(bars) or 1
    bw = (w - 20) / len(bars)
    base_y = h - 20
    body = [f'<text x="10" y="28" font-size="20" font-weight="bold">{total} contributions, last year</text>']
    for i, v in enumerate(bars):
        bh = (v / maxv) * 60
        x = 10 + i * bw
        body.append(f'<rect x="{x:.1f}" y="{base_y - bh:.1f}" width="{bw*0.7:.1f}" height="{bh:.1f}" fill="#3fb950" />')
    return svg_wrap(w, h, "\n".join(body), font_path)


def streak_svg(current: int, longest: int, font_path) -> str:
    w, h = 480, 90
    body = f"""
    <text x="10" y="35">current streak: {current} days</text>
    <text x="10" y="65">longest streak: {longest} days</text>
    """
    return svg_wrap(w, h, body, font_path)


def languages_svg(langs: list[tuple[str, int, str]], font_path) -> str:
    w, h = 480, 30 + 26 * max(len(langs), 1)
    total = sum(size for _, size, _ in langs) or 1
    body = []
    for i, (name, size, color) in enumerate(langs):
        y = 30 + i * 26
        pct = size / total * 100
        bar_w = pct * 2.5
        body.append(f'<text x="10" y="{y}">{escape_svg_text(name)}</text>')
        body.append(f'<rect x="140" y="{y-12}" width="{bar_w:.1f}" height="12" fill="{color}" rx="2" />')
        body.append(f'<text x="{150+bar_w:.1f}" y="{y}">{pct:.1f}%</text>')
    return svg_wrap(w, h, "\n".join(body), font_path)


def year_ramp_svg(weeks: list[dict], font_path) -> str:
    counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    if not counts:
        return svg_wrap(480, 60, "", font_path)
    maxv = max(counts) or 1
    levels = len(RAMP)
    chars = []
    for c in counts:
        idx = int(round((c / maxv) * (levels - 1))) if c else 0
        chars.append(RAMP[idx])
    text = escape_svg_text("".join(chars))
    body = f'<text x="10" y="35" xml:space="preserve">{text}</text>'
    return svg_wrap(480, 60, body, font_path)


def write_if_changed(path: str, content: str) -> bool:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ["GH_LOGIN"]
    font_path = os.environ.get("STATS_FONT_PATH")

    user = fetch(login, token)
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    weekly = weekly_totals(cal["weeks"])
    current, longest = compute_streaks(days)
    langs = top_languages(user["repositories"]["nodes"])

    changed = False
    changed |= write_if_changed("assets/stats.svg", hero_svg(cal["totalContributions"], weekly, font_path))
    changed |= write_if_changed("assets/streak.svg", streak_svg(current, longest, font_path))
    changed |= write_if_changed("assets/languages.svg", languages_svg(langs, font_path))
    changed |= write_if_changed("assets/year.svg", year_ramp_svg(cal["weeks"], font_path))

    print("changed:", changed)


if __name__ == "__main__":
    main()
