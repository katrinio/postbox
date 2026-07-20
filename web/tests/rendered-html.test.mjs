import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

// The "/" route is a client component gated by auth state (a Bearer token in
// localStorage), so the server renders the document shell and the home screen
// hydrates on the client. This test verifies the route is served directly —
// 200, correct document, no auth redirect — rather than the client-only home
// content, which is not present in the server-rendered HTML by design.
test("serves the / route shell without an auth redirect", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Postbox — тихая переписка<\/title>/i);
  assert.match(html, /Postbox/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});
