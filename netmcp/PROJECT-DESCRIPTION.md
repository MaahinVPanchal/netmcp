# NetMCP – AI Network Inspector

## Inspiration

We wanted AI assistants (Cursor, Claude Code) to **see** what happens when a web app loads—not just the code, but the real network traffic, API calls, and console errors. Debugging “why did my Supabase call fail?” or “what endpoints does this page hit?” usually meant manually opening DevTools, copying requests, and pasting into chat. We were inspired by the **Model Context Protocol (MCP)** to give the AI first-class tools: navigate to a URL, capture everything, and query it in natural language. NetMCP turns the browser and network into inspectable data the AI can reason about.

---

## What it does

NetMCP is an **MCP server** that lets AI assistants:

- **Capture browser traffic** – Open any URL in Chrome (Playwright), record every HTTP request, XHR/fetch, and optional response bodies. Capture console logs (errors, warnings, info) alongside network.
- **Discover APIs without a browser** – `fetch_and_extract_apis` GETs a page, parses HTML/JS for API/backend URLs. Works on AWS Lambda where there is no browser.
- **Query and debug** – Tools like `get_network_logs`, `get_failed_requests`, `search_requests`, `get_console_errors` let the AI inspect stored traffic, find slow or failed calls, and see backend URLs.
- **High-level flows** – “Super effective” tools: `check_signup_flow` (auto-detect URLs, capture traffic, analyze forms and errors), `analyze_web_app`, `smart_navigate` with scrolling and form filling, `test_api_endpoint` for direct API checks.

You can run it **locally** (file storage + Playwright) or **deploy to AWS** (API Gateway → Lambda → DynamoDB) with built-in cost protection (billing alerts, anomaly detection, concurrency limits, TTL). A Chrome extension and Node proxy can also send traffic to the same ingest API.

---

## How we built it

- **MCP server:** Python, **FastAPI** + **FastMCP**. All tools are registered in `tools.py` and exposed over HTTP at `/mcp` for Cursor/Claude (stateless JSON-RPC for Lambda).
- **Browser automation:** **Playwright** (primary) and **Selenium** (alternative). We capture request/response lifecycle and console messages, with configurable scrolling, waiting, and optional response bodies (capped at 50KB).
- **Storage:** Two backends—**JSONL file** for local dev (`storage_backend: files`) and **DynamoDB** for AWS (on-demand, TTL 24h, no provisioned capacity).
- **AWS:** **SAM (Serverless Application Model)** – one template defines API Gateway, Lambda, DynamoDB, CloudWatch log retention, optional billing alarm and cost anomaly detection. Lambda runs the same FastAPI app via Mangum; no browser in the cloud, so `fetch_and_extract_apis` and all query tools work there.
- **Extras:** Chrome extension (DevTools → `/ingest`), Node.js proxy for logging to the same ingest endpoint, Docker image for the MCP server. Config via `mcp.json` and `.env` (frontend/backend URLs, storage backend, ingest filters).

---

## Challenges we ran into

- **Lambda has no browser:** Playwright needs Chromium, which we don’t run in Lambda. We kept “navigate + capture” as a local-only feature and added `fetch_and_extract_apis` so the AI can still discover API URLs from HTML/JS without a browser. We documented this split (local = full capture, Lambda = query + extract) clearly.
- **Stateless MCP over HTTP:** Cursor/Claude can use a single HTTP endpoint. We made the MCP handler stateless (no SSE/session), so each request is self-contained and works with Lambda’s request-response model.
- **Cost control:** We didn’t want a surprise AWS bill. The SAM template adds a billing alarm (e.g. $15), cost anomaly detection, Lambda reserved concurrency (e.g. 10), DynamoDB on-demand, TTL, short log retention, and documented rough monthly cost (~$5–12 for moderate use).
- **Performance of capture:** Full-page capture with scrolling and response bodies can be slow. We introduced “fast mode” (single-pass scroll, fewer waits), tunable scroll/wait configs, and made response-body capture opt-in to keep runs quick.

---

## Accomplishments that we're proud of

- **One server, two environments:** Same codebase runs locally (file + Playwright) and on AWS (DynamoDB, no browser). One `mcp.json`/env toggle; Cursor/Claude point at localhost or the deployed URL.
- **Rich tool set:** From low-level (`get_network_logs`, `search_requests`) to high-level (`check_signup_flow`, `analyze_web_app`, `test_api_endpoint`) so you can say “check my signup flow” or “show failed requests with bodies” and get actionable results.
- **Console + network together:** Capturing both network and console logs in the same session makes it much easier to correlate API failures with JavaScript errors.
- **Production-minded deploy:** Cost protection, IAM scoped to the table, TTL, and clear docs (including Windows/WSL) so teams can deploy without surprises.

---

## What we learned

- **MCP over HTTP** works well for serverless: stateless JSON-RPC fits Lambda and avoids long-lived connections. FastMCP made it straightforward to expose many tools behind one endpoint.
- **Browser vs. no-browser** is a real split: we embraced it by designing “extract APIs from page source” for Lambda and “full browser capture” for local, instead of forcing one path.
- **Cost and safety:** Billing alarms and anomaly detection are easy to add in SAM and give real peace of mind when handing the stack to others.
- **AI usability:** Naming tools and writing descriptions so the model can choose the right one (e.g. “get_failed_requests_with_bodies” vs “get_failed_requests”) improved reliability of “ask in plain language, get the right data.”

---

## What's next for NetMCP

- **WebSocket and more protocols:** Today we capture the HTTP upgrade for WebSockets but not frame-by-frame; we’d like to capture WebSocket frames and explore gRPC/HTTP-based flows where feasible.
- **More “super effective” flows:** Reusable recipes for login, checkout, or other critical paths, with optional assertions (e.g. “expect no 5xx on these endpoints”).
- **Scheduling and CI:** Run `check_signup_flow` or `analyze_web_app` on a schedule (e.g. EventBridge) and store results for trend analysis or regression checks.
- **Better body handling:** Smarter handling of large or binary responses (sampling, streaming, or summary-only) so capture stays fast and storage stays bounded.
- **Multi-tab and auth:** Support multiple tabs and persisted auth (cookies/localStorage) so the AI can walk through authenticated flows without re-login every time.
