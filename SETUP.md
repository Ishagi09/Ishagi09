# Setup

## 0. Create the special repo
GitHub only shows this on your profile if the repo is named **exactly** your
username.

```bash
gh repo create Ishagi09 --public
cd Ishagi09
```

Copy every file from this bundle (`scripts/`, `.github/`, `assets/`,
`README.md`, `requirements.txt`) into that repo.

## 1. Install deps locally (only needed to build the portrait once)

```bash
pip install -r requirements.txt --break-system-packages
```

First run of `rembg` downloads a ~176MB background-removal model — once,
then cached.

## 2. Get a photo
No amount of tuning rescues a bad input — ASCII draws with shadow, not
detail (~13 brightness levels total).

- side light at ~45°, not flat-on lighting
- fill the frame: chin to just above the hair
- 1200px+ source
- plain background, don't wear black against a dark wall
- slight angle, not dead-on

Save it as `photo.jpg` in the repo root.

## 3. Get the font and subset it
Download `JetBrainsMono-Regular.ttf` from
https://github.com/JetBrains/JetBrainsMono/releases (SIL OFL 1.1), then:

```bash
chmod +x scripts/subset_font.sh
./scripts/subset_font.sh /path/to/JetBrainsMono-Regular.ttf
```

This writes `assets/fonts/jbmono-ramp.woff2` (~1.3KB — only the 13
characters the portrait ever draws, not the full font).

## 4. Generate the portrait

```bash
python scripts/generate_portrait.py photo.jpg assets/portrait.svg \
  --font assets/fonts/jbmono-ramp.woff2 --cols 90
```

Sanity-check it renders correctly before committing: paste the raw SVG
into GitHub's markdown rendering API (`POST /markdown`) and confirm it
comes back unchanged — that's the same sanitiser your README goes through.

If you're screenshotting to check the typing animation, don't use a
full-page screenshot — that restarts the SVG's SMIL animation. Use a tall
viewport and wait a couple seconds instead.

## 5. Push it

```bash
git add .
git commit -m "self-generating profile"
git push
```

No personal access token needed anywhere — the workflow uses the
built-in `GITHUB_TOKEN`.

## 6. Let the workflow run
It's scheduled daily and also runs on-demand: Actions tab → "refresh
stats" → Run workflow. First run writes `assets/stats.svg`,
`streak.svg`, `languages.svg`, `year.svg` and commits them.

## 7. If the README doesn't show up on your profile
A freshly created profile README is cached. Edit it once through the
GitHub web UI (even just adding a space and removing it) to force a
refresh.

---

**Notes**
- This bundle is an original implementation of the technique — background
  cutout → filtered/contrast-enhanced grayscale → darkening curve → ASCII
  ramp → per-row SMIL typing animation, with stats drawn separately via
  the GitHub GraphQL API and committed by a scheduled Action.
- `generate_stats.py` uses only the Python standard library (`urllib`) —
  nothing to break in CI.
- Re-running `generate_portrait.py` is a manual, occasional thing (new
  photo). The daily automation only touches the stats SVGs.
