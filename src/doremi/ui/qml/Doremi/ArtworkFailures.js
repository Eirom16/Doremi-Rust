.pragma library

// Presentation-only, per-engine backoff for missing/expired artwork URLs.
// A new URL is tried immediately; reopening a failed URL retries after 5 min.
var failures = Object.create(null)
var order = []
var maxEntries = 128
var retryAfterMs = 300000

function sourceFor(url, now) {
    now = now === undefined ? Date.now() : now
    if (failures[url] && failures[url] > now)
        return ""
    return url
}

function remember(url, now) {
    if (!url)
        return
    now = now === undefined ? Date.now() : now
    if (!failures[url])
        order.push(url)
    failures[url] = now + retryAfterMs
    while (order.length > maxEntries)
        delete failures[order.shift()]
}
