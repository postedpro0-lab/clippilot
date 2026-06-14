# 🎬 ClipPilot

Watches a YouTube channel. When it posts a new video, ClipPilot **downloads it,
finds the best ~30-second moments, cuts them into 9:16 vertical clips with
burned-in captions, and auto-posts them to YouTube Shorts, Instagram Reels, and
TikTok** — running 24/7 in the cloud for **$0/month**.

```
new upload → download → transcribe (local Whisper) → pick best moments
          → cut 9:16 + captions → auto-post to YT / IG / TikTok
```

Everything runs on **GitHub Actions' free tier** (use a *public* repo for
unlimited minutes), so your Mac doesn't need to be on.

---

## What's actually free vs. what needs a one-time setup

| Step | Cost | Setup effort |
|------|------|--------------|
| Watch channel for uploads | Free, no API key | none |
| Download video (`yt-dlp`) | Free | none |
| Transcribe (`faster-whisper`, local) | Free | none |
| Cut clips + captions (`ffmpeg`) | Free | none |
| Run 24/7 (GitHub Actions) | Free | push to a public repo |
| **Post to YouTube Shorts** | Free | ~10 min (Google OAuth) |
| **Post to Instagram Reels** | Free | ~15 min (IG Business acct + Meta app) |
| **Post to TikTok** | Free | **app approval, a few days** ⚠️ |
| **Post to Snapchat** | Free | **Public Profile + app approval** ⚠️ |

> ⚠️ **TikTok honesty check:** TikTok's only allowed auto-posting path is their
> Content Posting API, which requires you to register a developer app and get the
> `video.publish` scope **approved** (free, but takes days). There is no safe
> shortcut — unofficial auto-posters get accounts banned. So TikTok ships
> **off** (`post_to.tiktok: false`). Flip it on once you're approved. YouTube +
> Instagram work immediately.
>
> ⚠️ **Snapchat is the same story, but stricter:** there's no free instant
> organic-posting API. The free path needs a **Public Profile** plus an app
> approved for content publishing (Snapchat Business/Marketing API) — gated even
> harder than TikTok. The only turnkey alternative is a paid aggregator
> (Ayrshare/Late, ~$25–50/mo), which breaks the $0 rule. So Snapchat also ships
> **off** (`post_to.snapchat: false`), fully coded and ready to flip on once
> you're approved.

---

## Quick start

### 1. Pick the channel
Edit `config.yaml` → set `channel:` to the handle/URL you want (e.g. `@MrBeast`).
Then:
```bash
pip install -r requirements.txt
python scripts/resolve_channel.py     # fills in channel_id automatically
```

### 2. Get your posting credentials

**YouTube (do this first — it's the easiest):**
```bash
python scripts/get_youtube_token.py
```
Follow the printed steps (create a free Google Cloud project, enable *YouTube
Data API v3*, make a *Desktop* OAuth client). It prints 3 values:
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

**Instagram:**
1. Convert your IG account to a **Business or Creator** account and link it to a
   Facebook Page.
2. Create a free app at <https://developers.facebook.com/> → add
   *Instagram Graph API*.
3. Generate a **long-lived access token** with `instagram_content_publish`
   permission, and grab your numeric **IG user id**.
   → `IG_ACCESS_TOKEN`, `IG_USER_ID`.

**TikTok (optional, later):** register an app at
<https://developers.tiktok.com/>, request `video.publish`, and once approved put
the token in `TIKTOK_ACCESS_TOKEN` and set `post_to.tiktok: true`.

**Snapchat (optional, later):** set up a **Snapchat Public Profile**, then apply
for content-publishing access via <https://business.snapchat.com/> / the
Snapchat Marketing API. Once approved, put `SNAPCHAT_ACCESS_TOKEN` +
`SNAPCHAT_PROFILE_ID` in your secrets and set `post_to.snapchat: true`. Choose
`snapchat_target: "SPOTLIGHT"` or `"STORY"` in `config.yaml`. Confirm the exact
content endpoint/scope in `src/posters/snapchat.py` against the docs for the
access tier you're granted — the rest of the flow is already wired.

### 3a. Run it on your Mac (to test)
```bash
cp .env.example .env      # paste your credentials in
python run.py
```
First run just records existing videos as "seen" and makes nothing (so it
doesn't clip the whole back catalog). The next time the channel posts, you get
clips.
*To test on the current latest video instead, set `process_backlog: true`.*

### 3b. Run it in the cloud 24/7 (the real deal)
1. Create a **public** GitHub repo and push this folder to it.
2. Repo → **Settings → Secrets and variables → Actions** → add each value from
   your `.env` as a secret (same names). `GITHUB_TOKEN` is provided
   automatically — don't add it.
3. That's it. `.github/workflows/clip.yml` runs every 3 hours. Trigger it once
   manually from the **Actions** tab to confirm.

### Downloading the clips (cloud mode)
Cloud runs happen on a temporary GitHub server, so clips aren't saved to your
Mac automatically. Instead, every run **attaches its clips as a downloadable
zip** to the run itself:

1. Repo → **Actions** tab → click the run you want.
2. Scroll to **Artifacts** at the bottom → download **`clips-<number>`**.
3. Unzip — clips are organized into `work/<channel>/` folders inside.

Artifacts auto-delete after **14 days** (keeps your free storage tiny). Runs
that produced no new clips simply won't have an artifact.

---

## Tuning

All in `config.yaml`:
- `clip_seconds`, `max_clips_per_video` — how many/how long.
- `whisper_model` — `base` is the sweet spot; `small`/`medium` = better captions,
  slower.
- `post_to` — toggle platforms.
- `caption_template`, `extra_hashtags` — what gets written under each post.
- `post_spacing_seconds` — gap between posts so platforms don't flag spam.

## How the "smart" clip picker works
No paid AI. It transcribes locally, slides a 30s window over the speech, and
scores each window by talking density, hook words (questions, "you", numbers,
curiosity triggers), and whether it ends on a clean sentence. Top non-overlapping
windows win. Tweak the weights in `src/moments.py`.

## Notes / limits
- YouTube free quota ≈ 6 uploads/day. `max_clips_per_video: 5` keeps you safe.
- IG/TikTok pull video from a public URL, so clips are published as assets on a
  GitHub **Release** named `clips` in your repo (public repo = public URL).
- Fully automatic means it posts whatever the heuristic picks. Watch the first
  few runs; raise `whisper_model` or lower `max_clips_per_video` if quality
  varies.

## Costs
**$0/month.** Public-repo Actions minutes are unlimited; all libraries and APIs
used are free tiers. No servers, no subscriptions.
