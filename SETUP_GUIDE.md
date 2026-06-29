# Going Live — Step-by-Step Setup Guide

This guide turns the downloaded folder into a **live tracker that updates by itself every day**
and publishes a webpage you can open anytime. Written for non-experts — just follow the steps.

There are three "levels of live." Pick where you want to land:

| Level | What it does | What you need | Effort |
|-------|--------------|---------------|--------|
| **A. Preview** | See it work once, with sample data | Nothing (or Python) | 2 min |
| **B. Real data** | Pulls live market data each run | Python on your computer | 10 min |
| **C. Fully live (recommended)** | Runs daily by itself in the cloud, publishes a webpage | A free GitHub account | 20 min |

**The big shortcut:** Level C runs everything in the cloud, so **you don't have to install
Python at all.** If you just want the automatic version, skip to **Part 2**.

---

## Part 1 — Run it on your computer (optional, for testing)

Do this only if you want to preview it locally first. If not, jump to Part 2.

### 1. Install Python (one time)
- Go to **python.org/downloads**, download Python 3, and install it.
- **Windows:** on the first install screen, tick **"Add Python to PATH"** before clicking Install.

### 2. Unzip the folder
Unzip `macro-risk-tracker.zip` somewhere easy, like your Desktop.

### 3. Run it
- **Windows:** double-click **`run-windows.bat`**.
- **Mac:** right-click **`run-mac.command`** → Open (the first time, macOS asks you to confirm).
- A black window opens, installs a couple of small libraries, and runs the tracker.

That uses sample data (`--offline`). To use **real live data**, run with the live flag:
- **Windows:** open a Command Prompt in the folder and type `python src\main.py --no-ai`
- **Mac:** in Terminal, `python3 src/main.py --no-ai`

(The `--no-ai` part means "skip the AI-written summary." See Part 3 to turn that on.)

### 4. Look at the results
- **Spreadsheet:** open `output/macro_risk_tracker.xlsx`.
- **Webpage:** the page needs to be *served* (not just double-clicked). In the folder, run
  `python -m http.server 8000` then open **http://localhost:8000/dashboard/** in your browser.
  (Or just use the always-on web version from Part 2 — easier.)

---

## Part 2 — Make it fully live and automatic (recommended)

This puts the tracker on **GitHub**, which will run it **every weekday automatically** and host the
webpage for free. You do **not** need to install anything for this.

### Step 1 — Create a free GitHub account
Go to **github.com** and sign up (free). Skip if you already have one.

### Step 2 — Create a new repository
1. Click the **+** (top right) → **New repository**.
2. Name it `macro-risk-tracker`.
3. Choose **Public** (simplest; the tracker holds no personal data — your API key is added
   separately as a hidden secret, never in the files).
4. Click **Create repository**.

### Step 3 — Upload the files
1. On the new empty repo page, click **"uploading an existing file"** (a link in the middle).
2. **Unzip** `macro-risk-tracker.zip` on your computer first.
3. Open the unzipped folder, select **everything inside it**, and **drag it onto the GitHub page**.
   - Important: make sure the `.github` folder comes along (it contains the daily schedule).
     If drag-and-drop skips it, that's fine — Step 6 explains a one-click alternative.
4. Click **Commit changes** at the bottom.

### Step 4 — (Optional) Add your AI key for the daily written brief
Without this, the tracker still works and writes a plain summary. With it, a cheap AI model
writes a nicer 150-word brief each day (cost: a fraction of a cent per day).
1. Get a key at **console.anthropic.com** → API Keys → Create Key. Copy it.
2. In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
3. Name: `ANTHROPIC_API_KEY`  ·  Value: paste your key  ·  **Add secret**.

### Step 5 — Turn on the webpage (GitHub Pages)
1. In your repo: **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
That's it — the daily job will publish your dashboard here:
**`https://YOUR-USERNAME.github.io/macro-risk-tracker/`**

### Step 6 — Run it once now (to test, and to publish the page)
1. Go to the **Actions** tab.
2. If asked, click the green button to **enable workflows**.
3. Click **daily-risk-tracker** on the left → **Run workflow** → **Run workflow** (green button).
4. Wait ~1–2 minutes. A green check means success.
5. Open your Pages URL from Step 5. Your live dashboard is up.

From now on it runs **by itself every weekday** (after the US market close) and refreshes the page
and the spreadsheet. You don't have to do anything.

---

## Part 3 — Using it day to day

### See your dashboard
Bookmark your Pages URL (`https://YOUR-USERNAME.github.io/macro-risk-tracker/`). It shows every
story's 1–10 level, the indicators, and the daily brief.

### Get the spreadsheet
In your repo, open the `output` folder and click `macro_risk_tracker.xlsx` → **Download**.
It refreshes after each daily run.

### Update the "manual" indicators (the human-judgment ones)
Some indicators have no free live feed (e.g. CMBS office delinquency, rare-earth licensing,
insurance exits). Update them anytime — **right on GitHub**, no computer needed:
1. In your repo, click **`manual_input.csv`** → the **pencil icon** (Edit).
2. Change a number in the `value` column. (Event indicators use 0 = calm, 1 = watch, 2 = stress.)
3. **Commit changes.** The next run uses your new numbers. (Or trigger a run via Step 6.)

Reviewing these once a week — and sanity-checking any level that moved — is the
"human-in-the-loop" step that keeps the tracker trustworthy.

### Change how often it runs
Edit `.github/workflows/daily.yml`, the line `cron: "10 22 * * 1-5"`. The five fields are
`minute hour day month weekday` in **UTC**. Examples:
- Every day at 22:10 UTC: `10 22 * * *`
- 6:00 AM Seattle (≈14:00 UTC): `0 14 * * 1-5`

---

## Troubleshooting

- **Actions tab shows a red X.** Click the run to see the error. Most common: the `.github`
  folder didn't upload. Re-upload it, or recreate the file at
  `.github/workflows/daily.yml` using **Add file → Create new file** and paste the contents.
- **Dashboard shows "Could not load data."** The page loads `latest.json`, which only appears
  after the first successful run (Step 6). Run the workflow once, then refresh.
- **No AI brief, just a plain summary.** That means no API key — totally fine. Add the secret
  in Step 4 if you want the AI version.
- **Live data shows "(baseline)".** That indicator's free feed didn't respond that run; it falls
  back to the last value. Usually self-corrects next run.

---

## What it costs
- **GitHub Actions + Pages:** free for public repositories.
- **AI brief (optional):** a few cents a *month* using the cheap default model. Omit the key to
  pay nothing.

That's it. Once Part 2 is done, you have a self-updating macro-risk tracker with a live webpage
and a downloadable spreadsheet — no maintenance required beyond your weekly review of the
manual indicators.

---

## Part 4 — The automated AI rating agent

By default the tracker moves its *market* indicators (copper, oil, VIX, MOVE) automatically
every day, and holds the *judgment* indicators (Taiwan tension, Hormuz status, China export
curbs, etc.) at their baseline until a human edits them. The **agent** automates that second
group too — so you never have to adjust numbers by hand.

### How it works (and why it's trustworthy)
The agent does **not** invent scores. For each judgment indicator it:
1. **Searches** authoritative sources for the *current* status (live web search).
2. **Classifies** that evidence strictly against a fixed rubric in `config/framework.yaml`
   (band 0 = benign, 1 = watch, 2 = stress; or the latest published number).
3. **Logs** the value, a confidence level, a one-line rationale, and the source links to
   `data/agent_assessments.json` — every indicator, every run, fully auditable.

Safety rails: a **low-confidence** result never flips the number — it keeps the prior value and
is flagged for review. The deterministic engine still does all the math. And **you always win**:
anything you pin in `manual_input.csv` overrides the agent. The full rubric is in **`FRAMEWORK.md`**.

### Turning it on
It's already wired into the workflow and needs only your `ANTHROPIC_API_KEY` secret (Part 2,
Step 4). With that set:
- **Every weekday:** market data + narrative refresh (free; reuses the last agent ratings).
- **Every Monday:** the agent re-researches all judgment indicators.
- **Anytime:** Actions tab → Run workflow (leave "Run the AI rating agent" ticked) for a full refresh now.

No key set? Everything still runs — judgment indicators just stay at baseline until you edit them.

### Overriding the agent
Open `manual_input.csv` (edit it right on GitHub), put a number in the `value` column for any
indicator to **pin** it, and commit. Blank = let the agent decide. The agent skips anything you've
pinned and notes it in the audit log.

### Reviewing what it did
After an agent run, open `data/agent_assessments.json` in your repo. Each entry shows the value,
confidence, rationale, and sources. The `review_flags` list at the bottom is your short worklist —
indicators that were low-confidence or that changed — worth a 2-minute glance.

### Cost & tuning
- The agent makes one small web-grounded call per judgment indicator (~46 of them) on its run day.
  Weekly cadence keeps this to roughly a **dollar or two a month** on the default model.
- Cheaper: set a repository **variable** `AGENT_MODEL` to `claude-haiku-4-5-20251001`
  (Settings → Secrets and variables → Actions → Variables). Haiku is a fraction of the cost.
- Less often / more often: edit the second `cron` line in `.github/workflows/daily.yml`
  (`30 13 * * 1` = Mondays; `* * 1,4` would be Mon & Thu, etc.).

---

## Part 5 — Alerts & automatic config checks (Phase 2)

### Band-crossing alerts (so you never have to check)
The tracker can notify you **only when a story (or the overall level) crosses into a new risk
band** — Low → Moderate → Elevated → High → Severe — versus the previous run. Small wiggles are
ignored; you only hear from it when risk meaningfully changes.

Pick any channel (all free, set as repo **Secrets** under Settings → Secrets and variables → Actions):

- **Discord / Slack (easiest):** in your server, create an Incoming Webhook URL, then add a secret
  `ALERT_WEBHOOK_URL` with that URL. The format is auto-detected.
- **Telegram:** create a bot via @BotFather, get its token and your chat id, then add secrets
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **Email:** add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, and `ALERT_EMAIL_TO`.

Tuning: set a repository **variable** `ALERT_MIN_LEVEL` (e.g. `5`) to only be alerted about
crossings at/above Elevated. Default `0` = all crossings, both up and down.

Test it now: locally run `python src/main.py --test-alert` (with the env vars set), or just wait —
the daily workflow sends alerts automatically when a crossing happens. Add `--no-alert` to any run
to stay silent.

### Automatic config checks (CI)
A self-test (`tests/selftest.py`) now runs **on every push** (workflow `ci-selftest`) and as a
**guard before each daily run**. It catches the kind of bug that would silently corrupt the
tracker — most importantly a `baseline_band` that doesn't match the band its `baseline_value`
maps to (which would make day-zero levels disagree with the published reports) — plus missing
fields, bad thresholds, duplicate ids, framework gaps, and non-deterministic scoring. If anything
is wrong, the check fails loudly instead of shipping bad numbers. Run it yourself anytime:
`python tests/selftest.py`.

---

## Part 6 — Backtest & methodology (Phase 4)

**Backtest.** `python src/backtest.py` replays documented historical values of the market/data
indicators (the 2020 COVID dash-for-cash and the 2022 rate/MOVE shock) through the live scoring
engine, and writes `dashboard/backtest.json`. The dashboard then shows, per episode, how the most
affected stories' levels would have moved. Run `python src/backtest.py --live --start 2019-06-01
--end 2026-06-01` to replay real history pulled from the live feeds instead.

Honest scope (also shown on the dashboard): only the market/data indicators are varied; judgment
indicators are held at baseline, so backtested levels reflect ONLY the market-driven component — a
partial validation of the engine's mechanics, not a claim the tracker would have predicted events.

**Methodology.** `METHODOLOGY.md` (versioned) documents the scoring math, the agent trust model, data
sources, the backtest's limits, and an explicit "what this is and isn't." Read it before relying on
the numbers.

**Agent cross-checking.** The highest-weight indicators are rated twice; if the two independent reads
disagree, the rating is held at low confidence and flagged for review instead of moving the meter on
a single, possibly-wrong reading. Tune with the `AGENT_CROSSCHECK_MIN_WEIGHT` variable (default 1.5),
and optionally set `AGENT_MODEL_2` to use a different model for the second opinion.

---

## Part 7 — The overnight-event scout

The rating agent answers a fixed question ("re-rate the 46 known indicators"). The **scout**
answers an open one: *"did something material happen that the tracker doesn't already capture?"*

Each run (it's wired into the daily workflow, one cheap web-grounded call) the scout scans credible
feeds for recent developments and triages each into:
- **Re-rate existing** — already captured by an indicator; the rating agent will handle it.
- **Coverage gap** — fits an existing story but no indicator captures it; it proposes a new indicator + rubric.
- **New risk** — fits no existing story; it proposes a new story stub (name, why, a proposed 1–10, rubric).

**It proposes; it never changes anything.** Proposals land in a review queue (`data/scout_queue.json`)
and on the dashboard's **Scout** panel with status `pending`. You stay in control:

```
python src/scout.py --list                     # see pending proposals
python src/scout.py --status <id> approved      # or: dismissed
python src/scout.py --snippet <id>              # paste-ready YAML to merge an approved proposal
```

Approving is a two-step you do deliberately: mark it approved, then paste the `--snippet` YAML into
`config/stories.yaml` (and `config/framework.yaml` for a new rubric) and commit. The self-test runs on
that commit, so a malformed addition is caught before it ships. Tune the scan window with `--days`,
and the model with the `SCOUT_MODEL` repo variable.

Why this design: an LLM scanning the news at 3am *will* surface false positives. The value is entirely
in the triage discipline and the human gate — the scout widens what the tracker can notice without ever
letting unvetted machine output move your numbers.

---

## Part 8 — One-step approval & the briefs

**Smoother approval.** Instead of pasting YAML by hand, merge an approved scout proposal in one step:

```
python src/scout.py --apply <id>
```

This backs up the config, inserts the new indicator/story and its rubric, validates that the files
still parse, **runs the self-test**, and — if anything fails — **rolls everything back cleanly** so a
bad proposal can never corrupt your config. On success it marks the proposal `applied`; you then just
commit `config/`. (`--snippet` is still there if you prefer to review/paste manually.)

**The briefs in the tracker.** The three polished Set PDFs are served from `dashboard/briefs/` and
linked from the dashboard (a "Briefs" row, and a "Full brief" link on each story's Background panel).
Each story also shows an inline **Background** summary, kept in `config/briefs.yaml` (decoupled from the
scoring config so editing prose never risks the math). A **living brief** (`dashboard/briefs/living_brief.html`)
is regenerated on every run from the current stories + latest levels, so any story the scout adds shows
up automatically — that's the "auto-updating brief." The curated Set PDFs remain the deep-dive
originals; regenerate them deliberately when you want a new polished edition.
