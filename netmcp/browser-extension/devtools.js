// Ingest URL is read from storage (set in popup). Default for local dev.
const DEFAULT_INGEST_BASE = "http://localhost:8000";

chrome.devtools.network.onRequestFinished.addListener(async (request) => {
  const { ingestBaseUrl } = await chrome.storage.local.get("ingestBaseUrl");
  const base = ingestBaseUrl || DEFAULT_INGEST_BASE;
  const ingestUrl = base.replace(/\/$/, "") + "/ingest";

  request.getContent((responseBody) => {
    const entry = {
      url: request.request.url,
      method: request.request.method,
      status: request.response.status,
      response_time_ms: request.time,
      request_headers: Object.fromEntries(
        (request.request.headers || []).map((h) => [h.name, h.value])
      ),
      request_body: request.request.postData?.text || "",
      response_headers: Object.fromEntries(
        (request.response.headers || []).map((h) => [h.name, h.value])
      ),
      response_body: (responseBody || "").substring(0, 5000),
    };

    fetch(ingestUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    }).catch(console.error);
  });
});
