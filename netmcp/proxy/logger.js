/**
 * Shared logger helpers for building log entries from request/response.
 * Used by index.js (proxy) and can be reused for other log sources.
 */

function buildLogEntry(options) {
  const {
    url,
    method = "GET",
    status = 0,
    response_time_ms = 0,
    request_headers = {},
    request_body = "",
    response_headers = {},
    response_body = "",
  } = options;

  return {
    url,
    method: method.toUpperCase(),
    status,
    response_time_ms,
    request_headers: typeof request_headers === "object" ? request_headers : {},
    request_body: typeof request_body === "string" ? request_body : "",
    response_headers: typeof response_headers === "object" ? response_headers : {},
    response_body: (typeof response_body === "string" ? response_body : "").substring(0, 5000),
  };
}

module.exports = { buildLogEntry };
