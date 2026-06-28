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
