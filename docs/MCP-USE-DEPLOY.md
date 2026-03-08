# Deploy NetMCP to mcp-use (manufact.com)

NetMCP is a **Python** app (FastAPI + FastMCP). mcp-use may default to a **Node** image, which causes `pip3: not found` if you set Python build commands.

## Option 1: Use the root Dockerfile (recommended)

This repo has a **root-level `Dockerfile`** that uses Python and runs NetMCP.

1. In mcp-use build settings, **clear** the custom Build Command and Start Command (leave them empty if the platform uses the Dockerfile when present).
2. Or set **Build Command** to empty and **Start Command** to empty, and ensure the platform is set to use the **Dockerfile** at the repo root.
3. **Port:** keep **8000**.
4. Redeploy.

If the platform always uses its own Dockerfile and ignores ours, use Option 2.

## Option 2: Point to Python app and set runtime to Python

If mcp-use has a **Root Directory** or **App Directory** setting:

- Set it to **`netmcp/mcp-server`** (so the build context is the Python app).
- Set **Runtime** or **Environment** to **Python 3.12** (or 3.11).
- **Build command:** `pip install -r requirements.txt`  
  (or `pip3 install -r requirements.txt` if the Python image uses `pip3`).
- **Start command:** `python main.py` or `uvicorn main:app --host 0.0.0.0 --port 8000`.
- **Port:** **8000**.

## Option 3: Don’t build on mcp-use – use your Lambda URL

NetMCP is already deployed on **AWS Lambda**. You can “provide” it to mcp-use without building there:

1. Deploy NetMCP to Lambda (see [netmcp/infra/DEPLOY.md](../netmcp/infra/DEPLOY.md)).
2. In mcp-use, look for **“Add existing server”**, **“Connect external MCP”**, or **“Deploy an existing MCP server”**.
3. Paste your **mcp-http** URL, e.g.  
   `https://YOUR_API.execute-api.us-east-1.amazonaws.com/Prod/mcp-http`
4. No build or repo needed on mcp-use – they just use the URL.

## If the platform ignores the Dockerfile

Some platforms only use a Dockerfile when it’s in a specific path or when “Use Dockerfile” is enabled. Check for:

- **Use Dockerfile** or **Dockerfile path** (e.g. `./Dockerfile` or `Dockerfile`).
- **Runtime: Docker** so the root `Dockerfile` is used instead of Node + build commands.

Once the Python image is used (via our Dockerfile or Python runtime), port **8000** and `uvicorn main:app` will work.

---

## Option 4: Platform uses Node image and injects your Build/Start (workaround)

If mcp-use **always generates a Node-based Dockerfile** and ignores the repo Dockerfile ("Dockerfile generated successfully" in logs), install Python **inside** the Node Alpine image so the build succeeds.

In **Build & Runtime** use:

| Field | Value |
|-------|--------|
| **Build Command** | `apk add --no-cache python3 py3-pip && cd mcp-server && pip3 install -r requirements.txt` |
| **Start Command** | `python3 main.py` |
| **Port** | `8000` |

Then **Redeploy**. The build step installs Python + pip in the Alpine image; the start step runs NetMCP. Use **Start Command** `python3 main.py` so the app respects the **PORT** env var (many platforms set it).

**Important:** This repo has a **`mcp-server`** folder at the **repo root** (a copy of `netmcp/mcp-server`) so that mcp-use’s build finds it. Ensure the project connected in mcp-use is this repo and the root directory is the repo root (not a subfolder). After pushing, use the commands above.
