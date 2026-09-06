# Deploy checklist — real values, in order

Status as of **2026-09-06**. Everything that does not need your login is done.
What is left is three screens in a browser, about 20 minutes.

```
repo        github.com/ramongtzl/ramon-social-assets     PUBLIC   ✅ pushed
commit      f5eccb6  ·  201 files  ·  44 MB
workflows   .github/workflows/post.yml  (hourly, :05)    ✅ in repo
            .github/workflows/maintain.yml               ✅ in repo
schedule    60 posts · @ramonhouses only · 2026-09-01 → 2026-11-02
assets      186 image refs · 0 missing  (validated 2026-09-06)
GitHub Pages                                             ❌ NOT ON  ← blocker
repo secrets                                             ❌ NOT SET ← blocker
```

**Nothing can post until Pages is on.** The Instagram Graph API takes an image
*URL*, not an upload — with Pages off, every image 404s and every post fails.

**Next scheduled post: today, 2026-09-06 at 10:00 Pacific** (RE Single ES).
If steps 1–2 are done before then, that one goes out today. Three earlier slots
(Sep 1, Sep 2, Sep 5) have already passed unposted — the agent only posts what is
due in the current hour, it does not back-fill.

---

## Step 1 — Turn on GitHub Pages  (2 min)

<https://github.com/ramongtzl/ramon-social-assets/settings/pages>

**Source: Deploy from a branch → Branch: `main` → Folder: `/ (root)` → Save.**

Wait ~1 minute, then confirm this returns JSON rather than a 404:

```bash
curl -sI https://ramongtzl.github.io/ramon-social-assets/manifest.json
```

## Step 2 — Add the secrets  (10 min)

<https://github.com/ramongtzl/ramon-social-assets/settings/secrets/actions>

| Secret | Value | Required? |
|---|---|---|
| `ASSET_BASE_URL` | `https://ramongtzl.github.io/ramon-social-assets` | **yes** |
| `IG_TOKEN` | long-lived token — SETUP.md step 3 | **yes** |
| `IG_USER_HOUSES` | Instagram account id for @ramonhouses | **yes** |
| `IG_USER_GROWTH` | — | **not needed** (no growthwealth rows in this schedule) |
| `FB_PAGE_IDS` | both Page ids, comma-separated | optional, free |
| `LI_*` | LinkedIn — SETUP.md §8 | optional, later |
| `YT_*` | YouTube — SETUP.md §8 | optional, later |

Token scopes to grant in Graph API Explorer:
`instagram_basic`, `instagram_content_publish`, `pages_show_list`,
`pages_read_engagement`, `business_management`, **`pages_manage_posts`**.

That last one is what makes Facebook free — the agent derives Page tokens from
`IG_TOKEN` at run time, so no separate Facebook token is ever needed.

## Step 3 — Dry run, then live  (5 min)

<https://github.com/ramongtzl/ramon-social-assets/actions>

`post-to-social` → **Run workflow** → leave **dry run ticked** → Run.
The log prints every target it *would* hit. Check the URLs resolve and the
account ids look right, then run again with dry run **off** during an hour that
has something scheduled.

---

## After it is live

- **Facebook**: run `python auth/facebook_pages.py` with `IG_TOKEN` in the
  environment — it prints every Page id the token can post to. Put the two Ramon
  Houses ids in `FB_PAGE_IDS`. No review, no wait.
- **LinkedIn**: profile posting works immediately; the *company page* needs
  Community Management API review (days). SETUP.md §8.
- **YouTube**: uploads are locked to PRIVATE until Google verifies the app.
  Set the consent screen to **In production**, not Testing — in Testing the
  refresh token dies after 7 days.

## The one recurring job

`IG_TOKEN` and `LI_ACCESS_TOKEN` both expire about every 60 days, and when they
do **posting stops silently** — the run fails, the platform says nothing. Put a
calendar reminder at day 50. `health.json` and the Actions tab are where to look
if posts stop appearing.

## Book cards

Not in this bundle, by design. `build_web_assets.py` has `INCLUDE_BOOKS` off by
default since 2026-09-04 — the Round 2 / 2b quote cards belong to
@ramongtzl.growthwealth and are published separately. Re-verified 2026-09-06:
0 of 60 rows are book cards, 60 of 60 are @ramonhouses. Rebuilding with
`--with-books` would double-post them and land copies on the wrong account.
Do not pass that flag.
