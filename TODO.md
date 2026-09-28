# TODO: redesign verification

The UI/UX redesign (sessions, market snapshot, preview, report reading) is committed but not fully verified. Everything below is still to do.

## Status

| Area | Offline tests | Browser-tested (scripted backend) | Live run (real model) |
|------|---------------|-----------------------------------|-----------------------|
| Market snapshot backend | ✅ pytest | – | ❌ |
| Question preview endpoint | ✅ pytest | ✅ | – (no model calls) |
| Cancel on disconnect | ✅ pytest | – | ✅ once via curl (Deep run: 7 of 15 requests used) |
| Sessions + `Memory/` persistence | ✅ pytest | ✅ 19/19 flow checks | ❌ |
| Follow-up context | ✅ pytest | ✅ (flags and asset carry-over only) | ❌ report actually uses the context |
| App shell layout | – | ✅ | ❌ |
| Sessions rail and deep links | – | ✅ | ❌ |
| Market snapshot tiles | – | ✅ hover, keyboard, table | ❌ |
| Preview while typing | – | ✅ | ❌ |
| Section tabs and summary lead | – | ✅ | ❌ |
| Analyst drawer | – | ✅ | ❌ |
| Cancel and Try again (UI) | – | ✅ | ❌ |

## 1. Offline tests

```bash
cd Backend
pip install -r requirements-dev.txt
pytest -q          # expect 101 passed
```

## 2. Browser checks (1440×900 and 1280×800)

Start the app with `cd Backend && uvicorn server:app --port 5050` and open http://localhost:5050.

Done on 2026-09-28 with Playwright (headless Chromium) against a scripted backend: 67/67 checks at both sizes. The run turned up five layout and navigation bugs, each fixed in its own commit: the follow-up composer wrapped onto two rows at 1280px, the Run button wrapped to the left on the start screen, report text showed through under the floating composer, banners sat far from their run (the offline banner was below the fold), and `#b=` links within the open session were ignored.

- **Section tabs**
  - [x] Tabs appear for a report with 2 or more sections.
  - [x] Clicking a tab scrolls to that section.
  - [x] The active tab follows scrolling.
  - [x] The tabs stay stuck under the masthead.
  - [x] Scrolling is instant when reduced motion is on.
- **Summary lead**
  - [x] The executive summary shows as the lead block with the amber rule.
  - [x] The duplicated "BIFAS Executive Report: …" title is gone.
  - [x] Downloaded `.md` files still contain the full text.
- **Analyst drawer**
  - [x] Clicking a finished analyst opens the drawer.
  - [x] Previous and next move between analysts.
  - [x] Esc, the close button and a click on the backdrop all close it.
  - [x] Tab stays inside the drawer while it's open.
  - [x] Focus returns to the analyst row when it closes.
  - [x] The page behind doesn't scroll while it's open.
- **Cancel and Try again**
  - [x] Cancel during a run stops it and shows the "Analysis cancelled" banner.
  - [x] Nothing is saved to `Memory/`.
  - [x] Try again reruns the same question.
- **Re-run the earlier flows after these commits:**
  - [x] sessions (create, follow-up, switch, rename, delete, reload with `#s=…&b=…`)
  - [x] snapshot tiles (hover, arrow keys, table view)
  - [x] preview while typing
- **Quality:**
  - [x] no console errors
  - [x] no horizontal scroll
  - [x] visible focus on every control
- [ ] Palette sanity check: run the dataviz validator on `#239E96,#E2653E` against surface `#142031` in dark mode (it passed during development).

## 3. Live runs (real model, about 25–30 of the 500 daily requests)

- [ ] **Session A:**
  - Run "Gold and crude oil price analysis with dollar correlation" (Quick).
  - Snapshot tiles arrive before the report, with correct prices.
  - The stamp appears.
- [ ] **Follow-up context:** in session A, run "What about silver instead?".
  - The preview shows "Builds on 1 earlier briefing".
  - The report refers back to gold.
  - Prices come from fresh data.
- [ ] **Asset carry-over:** in session A, run "What are the main risks?".
  - The preview says "Continuing with …".
  - The analysis stays on the same assets.
- [ ] **Context off:** repeat a follow-up with "Builds on" switched off, and check the briefing is saved with `used_context: false`.
- [ ] **Session B:** create it and run "Bitcoin and Ethereum price trends" (Standard).
- [ ] **Persistence:** reload the page **and restart the server**. Sessions and threads come back from `Memory/sessions/`, and opening them makes zero `/api/analyze` requests (check the network tab).
- [ ] **Cancel from the UI:** cancel mid-run. The server log shows the cancellation, the quota rises by less than a full run, and a new run starts right away.
- [ ] **Usage file:** `Memory/usage.json` holds the counter, and `Backend/.bifas_usage.json` no longer exists.
- [ ] **Fallback model:** not yet tested end to end with `gemma-4-26b-a4b-it`. Optionally run once with `BIFAS_DAILY_LIMIT=0`.

## 4. Docs (after verification)

- [ ] **README:**
  - sessions and follow-ups, the `Memory/` folder, the new endpoints (`/api/preview`, `/api/sessions…`, the `session` and `context` params on `/api/analyze`, and the `session`/`market`/`cancelled` events)
  - the new env settings (`BIFAS_MEMORY_DIR`, `BIFAS_MAX_SESSIONS`)
  - an updated screenshot
- [ ] **TEST_REPORT.md:** add a v7.2 section with the results from steps 1–3.

## 5. Final git checks

- [ ] Commits are authored by p04pranav, with no co-author lines.
- [ ] `git ls-files | grep -E "\.env$|Memory/.+|\.claude|usage"` shows only `Memory/.gitkeep`.
