"""Load FRONTEND_URL, BACKEND_URL (and optional settings) from mcp.json so user config is in one place."""
import json
import os

# Paths to try: env NETMCP_CONFIG, then ../mcp.json, then ./mcp.json (relative to this file)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVER_DIR = _SCRIPT_DIR
_NETMCP_ROOT = os.path.dirname(_MCP_SERVER_DIR)


def load_netmcp_config() -> None:
    path = os.getenv("NETMCP_CONFIG")
    if path and os.path.isfile(path):
        pass
    else:
        for base in (_NETMCP_ROOT, _MCP_SERVER_DIR, os.getcwd()):
            for name in ("mcp.json", "netmcp-config.json"):
                p = os.path.join(base, name)
                if os.path.isfile(p):
                    path = p
                    break
            if path:
                break
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    netmcp = data.get("netmcp") or data.get("mcpServers", {}).get("netmcp") or {}
    if isinstance(netmcp, dict):
        if netmcp.get("frontend_url") and not os.getenv("FRONTEND_URL"):
            os.environ["FRONTEND_URL"] = str(netmcp["frontend_url"]).strip()
        if netmcp.get("backend_url") and not os.getenv("BACKEND_URL"):
            os.environ["BACKEND_URL"] = str(netmcp["backend_url"]).strip()
        if netmcp.get("ingest_filter_urls") is not None and not os.getenv("INGEST_FILTER_URLS"):
            v = netmcp.get("ingest_filter_urls")
            os.environ["INGEST_FILTER_URLS"] = v if isinstance(v, str) else ",".join(v) if v else ""
        if netmcp.get("storage_backend") and not os.getenv("STORAGE_BACKEND"):
            os.environ["STORAGE_BACKEND"] = str(netmcp["storage_backend"]).strip().lower()
        if netmcp.get("netmcp_log_file") and not os.getenv("NETMCP_LOG_FILE"):
            os.environ["NETMCP_LOG_FILE"] = str(netmcp["netmcp_log_file"]).strip()