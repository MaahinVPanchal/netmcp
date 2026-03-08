document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.local.get("ingestBaseUrl", (data) => {
    const input = document.getElementById("ingestBaseUrl");
    if (input) input.value = data.ingestBaseUrl || "http://localhost:8000";
  });

  document.getElementById("save").addEventListener("click", () => {
    const input = document.getElementById("ingestBaseUrl");
    const url = (input?.value || "").trim().replace(/\/$/, "");
    if (url) {
      chrome.storage.local.set({ ingestBaseUrl: url }, () => {
        document.getElementById("save").textContent = "Saved!";
        setTimeout(() => { document.getElementById("save").textContent = "Save"; }, 1500);
      });
    }
  });
});
