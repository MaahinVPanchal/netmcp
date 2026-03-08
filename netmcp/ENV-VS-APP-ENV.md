# NetMCP .env vs your app .env

## You do **not** need to add your app secrets to NetMCP

NetMCP’s **mcp-server/.env** only needs:

- **FRONTEND_URL** – page to open in the browser (e.g. `https://voicezero.ai` or `http://localhost:5173`)
- **BACKEND_URL** – your API/Supabase base (e.g. `https://kitebvteletvheszekfg.supabase.co`) for filtering/reference
- **STORAGE_BACKEND**, **NETMCP_LOG_FILE** – for file storage

Do **not** put these in NetMCP’s .env:

- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` / `VITE_SUPABASE_SERVICE_ROLE_KEY`
- `VITE_GOOGLE_GEMINI_API_KEY`, `ELEVENLABS_SIGNING_SECRET`
- `VITE_SITE_URL`, `VITE_STRIPE_*`, `STRIPE_*`

Those stay in **your voicezero app repo’s .env**. The browser loads your app (voicezero.ai or localhost); the app uses its own env. NetMCP only opens the URL and records network requests—it never reads your app’s .env.

---

## Why there are no Supabase requests in the log yet

Supabase (and other API) requests appear when the **page** makes them: login, signup, API calls, etc. So:

1. Run **navigate_to_app** (or **navigate_with_playwright** with your frontend URL).
2. In the **Chrome window** that opens, use the app: sign in, open a page that calls your API, etc.
3. Then run **get_network_logs** or **search_requests(url_contains="supabase")** — you’ll see those requests.

So you don’t “pass” the app .env to NetMCP; you just open the frontend and use the app in the captured browser.

---

## Testing with **local** frontend (optional)

If you want to capture traffic from your **local** dev server (so you can test before deploy):

1. **In the NetMCP project** (`netmcp/mcp-server/.env`):
   - Set `FRONTEND_URL=http://localhost:5173` (or your app’s port, e.g. 3000).

2. **In your voicezero app repo**:
   - Keep its `.env` as is (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, etc.).
   - Run the app: `npm run dev` (or `yarn dev`).

3. **Start NetMCP** (e.g. `run-mcp-server.bat`), then in Cursor run **navigate_to_app**.
   - Chrome opens **localhost:5173**; your app loads with its .env and calls Supabase/APIs.
   - NetMCP captures those requests; use **get_network_logs** / **search_requests** to inspect them.

Summary:

| Where              | What to put |
|--------------------|------------|
| **NetMCP** `mcp-server/.env` | `FRONTEND_URL`, `BACKEND_URL`, `STORAGE_BACKEND`, `NETMCP_LOG_FILE` only. |
| **Your app** (voicezero) `.env` | All VITE_*, Stripe, Supabase keys, etc. |

No need to copy your app’s .env into the NetMCP testing project.
