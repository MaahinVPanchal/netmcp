# VoiceZero.ai – Step 1 / Step 2 / Step 3 Check (NetMCP + Browser)

## What was checked

- **NetMCP** (remote): `navigate_with_playwright` to voicezero.ai returns **"Playwright not installed"** on the Lambda backend, so no network capture was done from NetMCP for voicezero.ai.
- **NetMCP stored logs**: Only older entries (e.g. `api/test`, example.com). No failed requests. No voicezero.ai traffic.
- **Browser (cursor-ide-browser)**:
  - Opened https://voicezero.ai and took a snapshot + console + network.
  - **Console**: One error — `Unrecognized feature: 'web-share'.` (from the page, around line 243). This comes from a Permissions-Policy / feature policy and can affect any code that checks or uses `navigator.share` or the `web-share` feature.
  - **Network**: Main resources (HTML, JS, fonts, Vimeo, analytics) return 200. One request to `https://snippet.partnerstack.com/api/ps.js` had **no statusCode** in the captured list (may be blocked, CORS, or still pending).

## What “Step 1, Step 2, Step 3” are on the site

On the homepage hero, the value prop is shown as:

1. **They leave a voice mail**
2. **AI reads between the lines**
3. **You act on insights**

In the accessibility snapshot these do **not** appear as separate interactive elements (buttons/links). They appear as text in the hero. So “not working” could mean:

- **A.** The **visual/animation** for these three steps (e.g. carousel, cycling text, or step indicator) is not advancing or not visible.
- **B.** The **product flow** after signup (Step 1 = leave voicemail, Step 2 = AI analysis, Step 3 = act on insights) is broken in the app.
- **C.** Some **links or CTAs** tied to these steps (e.g. “Start Free” or section links) are not working.

## Why Step 1 / 2 / 3 might not be “working”

1. **Permissions-Policy `web-share`**
   - The console error suggests the page (or an iframe/script) uses a feature named `'web-share'` in a Permissions-Policy. Browsers that don’t recognize it can log this and, depending on implementation, could affect script behavior.
   - **Fix**: Remove or adjust the `web-share` feature in the Permissions-Policy (or use a well-supported feature name) so the error goes away and any dependent logic (e.g. share buttons) works.

2. **PartnerStack script**
   - `snippet.partnerstack.com/api/ps.js` did not show a success status in the captured network list. If this script is required for layout or for CTAs near the steps, a blocked or failed load could break that part of the page.
   - **Check**: In DevTools → Network, confirm whether `ps.js` loads (status 200). If it’s blocked (adblocker, policy, or CORS), consider loading it in a way that doesn’t block the hero or step UI, or make the steps work without it.

3. **NetMCP not capturing voicezero.ai**
   - Because Playwright isn’t installed on the remote NetMCP server, you can’t use NetMCP to capture voicezero.ai traffic from Cursor right now.
   - **Fix**: Run NetMCP **locally** (with Playwright installed: `pip install playwright && playwright install chromium`), set `frontend_url` to `https://voicezero.ai` in `mcp.json`, then run `navigate_to_app` or `navigate_with_playwright`. After that, use **get_network_logs** and **get_failed_requests** to see which requests fail when you use the steps (e.g. click “Start Free” or go through the 3-step flow).

## Recommended next steps

1. **Fix the `web-share` Permissions-Policy** on voicezero.ai so the console error is gone and any share/step-related logic can run.
2. **Verify PartnerStack script** loads (Network tab) and that the hero and step section don’t depend on it for critical behavior.
3. **Run NetMCP locally** with Playwright, navigate to voicezero.ai, reproduce “step 1 / 2 / 3 not working,” then inspect **get_network_logs** and **get_failed_requests** for failing or missing API calls.
4. **Clarify** whether “not working” is (A) hero animation/carousel, (B) in-app flow after login, or (C) specific buttons/links — then test that path specifically with NetMCP and the browser.
