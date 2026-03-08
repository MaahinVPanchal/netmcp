const http = require("http");
const httpProxy = require("http-proxy");
const axios = require("axios");

const MCP_INGEST_URL =
  process.env.MCP_INGEST_URL || "http://localhost:8000/ingest";
const PROXY_PORT = parseInt(process.env.PROXY_PORT || "8080", 10);

const proxy = httpProxy.createProxyServer({});

const server = http.createServer((req, res) => {
  const target = req.headers["x-target-host"] || "http://localhost:3000";
  const startTime = Date.now();
  const reqChunks = [];

  req.on("data", (chunk) => reqChunks.push(chunk));

  proxy.web(req, res, { target }, (err) => {
    console.error("Proxy error:", err);
    res.writeHead(502);
    res.end("Bad gateway");
  });

  proxy.on("proxyRes", (proxyRes, req, res) => {
    const responseTime = Date.now() - startTime;
    const responseChunks = [];

    proxyRes.on("data", (chunk) => responseChunks.push(chunk));
    proxyRes.on("end", async () => {
      const responseBody = Buffer.concat(responseChunks).toString();
      const requestBody = Buffer.concat(reqChunks).toString();

      const logEntry = {
        url: `${target}${req.url}`,
        method: req.method,
        status: proxyRes.statusCode,
        response_time_ms: responseTime,
        request_headers: req.headers,
        request_body: requestBody,
        response_headers: proxyRes.headers,
        response_body: responseBody.substring(0, 5000),
      };

      try {
        await axios.post(MCP_INGEST_URL, logEntry);
      } catch (e) {
        console.error("Failed to log request:", e.message);
      }
    });
  });
});

server.listen(PROXY_PORT, () => {
  console.log(`NetMCP Proxy running on port ${PROXY_PORT}`);
  console.log(`Sending logs to: ${MCP_INGEST_URL}`);
});
