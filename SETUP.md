# Instagram posting agent â€” setup

Two accounts, one schedule, fully automatic. Once this is running your computer
does not need to be on: the job runs on GitHub's servers.

```
@ramongtzl.growthwealth   Round 2   01:00 daily   book card
                          Round 2b  14:00 daily   book card
@ramonhouses              carousel  Tue 11:00     8 slides, English
                          carousel  Wed 11:00     8 slides, Spanish
                          carousel  Sun 12:00     8 slides, English
                          carousel  Mon 12:00     8 slides, Spanish
```

Spanish carousels run a day after their English twin so the two never land in
the same hour on the same account.

## How it works

1. **Images are hosted publicly.** The Instagram Graph API takes an image *URL*,
   not a file upload â€” this is the constraint the whole design is built around.
   `build_web_assets.py` packs every image at web weight (JPEG q90, or the
   original PNG where that is smaller) and writes `schedule.csv` beside them.
2. **GitHub serves them** from a public repo via GitHub Pages.
3. **GitHub Actions runs hourly**, `post_agent.py` checks whether anything is due
   in the current Pacific hour, and publishes it.
4. **`state.json` is committed back** after each post, so nothing is ever posted
   twice â€” even if a run is retried.

## What you need to do

Everything below needs your login, so I cannot do it. Nothing here needs code.

### 1. Both Instagram accounts must be Business or Creator, each linked to a Facebook Page

In the Instagram app: **Settings â†’ Account type and tools â†’ Switch to
professional account**, then connect it to a Facebook Page you own. Do this for
both accounts. The API will not publish to a personal account.

### 2. Create a Meta app

At <https://developers.facebook.com/apps> â†’ **Create app** â†’ type **Business**.
Add the **Instagram Graph API** product.

One app can cover both accounts as long as your user administers both Pages.
Note that the two accounts currently sit in **different Business portfolios**
(growthwealth under business id `1167560481763862`, ramonhouses separately) â€” if
the token only returns one of them, add both Pages to the same portfolio in
Business Settings, or issue a second token and I will split the config.

### 3. Get a long-lived token

In **Graph API Explorer**, select your app and grant:

```
instagram_basic
instagram_content_publish
pages_show_list
pages_read_engagement
business_management
```

Exchange the short-lived token for a long-lived one (valid ~60 days):

```
GET https://graph.facebook.com/v21.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id=<APP_ID>
    &client_secret=<APP_SECRET>
    &fb_exchange_token=<SHORT_LIVED_TOKEN>
```

### 4. Find each Instagram account id

```
GET https://graph.facebook.com/v21.0/me/accounts?access_token=<TOKEN>
GET https://graph.facebook.com/v21.0/<PAGE_ID>?fields=instagram_business_account&access_token=<TOKEN>
```

The `instagram_business_account.id` is what the agent needs â€” one per account.

### 5. Create the repo and turn on Pages

New **public** repo, e.g. `ramon-social-assets`. Public matters: Actions minutes
are unlimited, and Pages serves the images. Everything in it is going onto
Instagram anyway, so nothing private is exposed â€” but do not put anything else
in this repo.

Push the contents of this `_AGENT` folder, with `workflow-post.yml` renamed to
`.github/workflows/post.yml`.

Then **Settings â†’ Pages â†’ Source: deploy from branch â†’ main / root**. Your base
URL becomes `https://<username>.github.io/ramon-social-assets`.

### 6. Add the secrets

**Settings â†’ Secrets and variables â†’ Actions â†’ New repository secret:**

| Secret | Value |
|---|---|
| `IG_TOKEN` | the long-lived token from step 3 |
| `IG_USER_GROWTH` | Instagram account id for @ramongtzl.growthwealth |
| `IG_USER_HOUSES` | Instagram account id for @ramonhouses |
| `ASSET_BASE_URL` | `https://<username>.github.io/ramon-social-assets` |

Secrets are write-only â€” nobody can read them back, including me.

### 7. Test before trusting it

**Actions â†’ post-to-instagram â†’ Run workflow**, leave *dry run* ticked. It logs
exactly what it would post without calling the API. When that looks right, run it
again with dry run **off** during an hour that has something scheduled.

## Rebuilding the schedule

After rendering new content:

```bash
python build_web_assets.py            # everything
python build_web_assets.py --days 60  # just the next 60 days, for a smaller repo
```

Then commit and push. The agent picks up the new `schedule.csv` on its next run.

## The one maintenance job

**The token expires about every 60 days.** When it does, posting stops silently â€”
the run fails, but Instagram never tells you. Two options:

- Put a calendar reminder to refresh it and update the secret, or
- Ask me to add a monthly workflow that refreshes the token automatically and
  writes it back as a secret. That needs a repo-scoped PAT, so it is a
  deliberate choice rather than a default.

## Limits and guardrails

- **25 posts per account per 24 hours** (Instagram's limit). The schedule uses 2
  on growthwealth and at most 1 on ramonhouses per day.
- Images must be JPEG/PNG, 320â€“1440px wide, aspect between 4:5 and 1.91:1. The
  1080Ã—1080 cards are comfortably inside that.
- Carousels take 2â€“10 items. Ours are 8.
- **Reels are not published by this agent.** Video publishing is a different API
  path with its own review requirements â€” post those by hand for now, or ask me
  to add them once image posting has been running cleanly for a couple of weeks.


---

## 8. Extra channels: Facebook, LinkedIn, YouTube (added 2026-09-04)

Every schedule row now carries a `channels` column. Images and carousels go
`ig,fb,li`; reels go `ig,fb,yt`. Each target is tracked on its own in
`state.json`, so a LinkedIn failure is retried next hour without re-posting
the Instagram copy. A channel whose secrets are missing is **skipped with a
log line**, never an error - add them one at a time.

### Facebook - both Ramon Houses Pages

Targets: `facebook.com/profile.php?id=61551446820788` and
`facebook.com/ramongtzl.houses`. No new token: the agent derives a Page token
from `IG_TOKEN` through `/me/accounts` at run time.

1. In the Meta app, make sure `pages_manage_posts` and `pages_read_engagement`
   are granted. If the long-lived token was minted before those were added,
   redo step 4 with **both Pages ticked** in the login dialog.
2. `python auth/facebook_pages.py` (with `IG_TOKEN` in the environment) prints
   every Page id the token can post to.
3. Secret **`FB_PAGE_IDS`** = the two ids, comma-separated.

### LinkedIn - profile + company page

Targets: `linkedin.com/in/ramongtzl` and company `143590036`.

1. Create an app at linkedin.com/developers, associated with the company page.
   Products: **Share on LinkedIn** + **Sign In with LinkedIn using OpenID
   Connect** (instant). For the *company page* also request **Community
   Management API** - LinkedIn reviews it, usually days. Profile posting works
   without it.
2. Auth tab: redirect URL `http://localhost:8765/callback`.
3. `python auth/linkedin_auth.py` - log in, it prints the values.
4. Secrets **`LI_ACCESS_TOKEN`**, **`LI_PERSON_URN`**, **`LI_ORG_ID`** (=143590036).

**Tokens last 60 days and cannot be refreshed by the agent.** Calendar reminder
at day 50, re-run the script, update the secret. Reels are *not* sent to
LinkedIn (its video upload is a separate flow); the reel idea reaches LinkedIn
as the Tuesday carousel instead.

### YouTube - @Ramonhouses Shorts

The Friday reel (1080x1920, under 60 s) uploads as a Short. Title = the hook
line + `#Shorts`; description = the caption; hashtags become tags.

1. Google Cloud: enable **YouTube Data API v3**; OAuth consent screen External
   and **In production** (in Testing the refresh token dies in 7 days - the
   same trap as the gmail-multi setup); Desktop OAuth client.
2. `python auth/youtube_auth.py` - sign in as the channel owner.
3. Secrets **`YT_CLIENT_ID`**, **`YT_CLIENT_SECRET`**, **`YT_REFRESH_TOKEN`**.

**Until Google verifies the app, API uploads are locked to PRIVATE.** They
still land in YouTube Studio and can be flipped public by hand, or request
verification once from the consent screen. Quota allows six uploads a day.

### Testing a channel

Actions -> Run workflow -> dry run **on** logs every target it *would* hit.
Then set `channels` to `fb` only on one row in `schedule.csv`, push, and run
with dry run **off** to make a single real post before trusting the fan-out.
