// Minimal service worker; popup and devtools use storage for backend URL.
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get("ingestBaseUrl", (data) => {
    if (!data.ingestBaseUrl) {
      chrome.storage.local.set({ ingestBaseUrl: "http://localhost:8000" });
    }
  });
});
