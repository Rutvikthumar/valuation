# FCFF Valuation Studio

A Damodaran-style FCFF DCF + Monte Carlo valuation tool, as a web app.
Growth anchored to historical CAGR, decayed to the risk-free rate; margins
are sector benchmarks, not management guidance — same philosophy as the
original script, now with a form so you can value *any* company without
touching code.

## Two valuation tools, one app
- **Home page** (`app.py`) — your custom history-anchored model: growth anchored strictly
  to 3-5yr historical CAGR, no management guidance, Monte Carlo + comparison view.
- **Ginzu Valuation page** (`pages/2_Ginzu_Valuation.py`) — a generic Python port of
  Damodaran's classic `fcffsimpleginzu.xlsx`. You set your own growth/margin/reinvestment/WACC
  assumptions directly, same as the spreadsheet's Input sheet. Validated against the workbook's
  own bundled example (Almarai): reproduces its $7.19/share estimate exactly.

## Files
- `engine.py` / `ginzu_engine.py` — the math for each model, framework-agnostic.
- `app.py` / `pages/2_Ginzu_Valuation.py` — Streamlit UI for each.
- `companies.json` / `ginzu_companies.json` — saved companies per tool.
- `requirements.txt` — dependencies.

### What the Ginzu port does *not* cover
Straight from the original workbook's scope — do these adjustments to your inputs before
entering them, same as you'd do on the spreadsheet's own worksheets:
- R&D capitalization
- Operating lease → debt conversion
- Employee stock option value (Black-Scholes)
- Country-risk-premium / industry-average lookups — enter your own WACC and sales-to-capital
  ratio directly instead

## Run it locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opens at `http://localhost:8501`.

## Put it on GitHub
```bash
cd fcff-app
git init
git add .
git commit -m "FCFF valuation studio"
git branch -M main
git remote add origin https://github.com/<your-username>/fcff-valuation-studio.git
git push -u origin main
```
(Create the empty repo on github.com first, or use `gh repo create` if you have the GitHub CLI.)

## Host it on the web (free)
1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **New app**, pick your `fcff-valuation-studio` repo, branch `main`, main file `app.py`.
3. Deploy. You get a public URL (e.g. `yourname-fcff.streamlit.app`) you can open from your phone
   or any browser — no local Python needed after this.
4. Every `git push` to `main` auto-redeploys the live app.

**Note on `companies.json`:** Streamlit Cloud's filesystem is ephemeral — companies you add
*in the deployed app* won't survive a redeploy. Two options if you want saved companies to
persist: (a) edit `companies.json` locally and push it to GitHub whenever you add a company
you want to keep, or (b) if you want durable multi-user storage, swap `load_companies`/
`save_companies` in `app.py` for a small SQLite file or a free hosted store (e.g. Supabase) —
happy to wire that up if you get to that point.

## Where to get the numbers
This tool deliberately does not auto-pull "consensus" figures — you enter revenue history,
margins, and balance sheet items yourself (10-K/10-Q, SEC filings), consistent with the
model's original discipline of ignoring management guidance and TAM slides.
