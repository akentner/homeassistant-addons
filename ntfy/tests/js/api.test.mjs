import test from "node:test";
import assert from "node:assert/strict";
import { ApiClientError, buildUrl, request, get, post, del } from "../../app/web/static/lib/api.mjs";

const resp = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body });

test("buildUrl encodes and stays relative", () => {
  assert.equal(buildUrl("users/a+b", { topic: "x*" }), "api/users/a%2Bb?topic=x%2A");
  assert.equal(buildUrl("users", { a: null, b: undefined, c: 0 }), "api/users?c=0");
  assert.throws(() => buildUrl("/users"));
  assert.throws(() => buildUrl("http://evil/x"));
});

test("request maps error bodies to ApiClientError", async () => {
  const fetchImpl = async () => resp(409, { error: "protected", message: "m" });
  await assert.rejects(request("DELETE", "users/x", { fetchImpl }), (e) => {
    assert.ok(e instanceof ApiClientError);
    assert.equal(e.status, 409);
    assert.equal(e.code, "protected");
    assert.equal(e.message, "m");
    return true;
  });
});

test("204 returns null", async () => {
  assert.equal(await request("DELETE", "x", { fetchImpl: async () => resp(204) }), null);
});

test("network failure becomes network_error", async () => {
  const fetchImpl = async () => {
    throw new TypeError("boom");
  };
  await assert.rejects(get("health", { fetchImpl }), (e) => e.code === "network_error" && e.status === 0);
});

test("headers, body and helper options", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push([url, init]);
    return resp(200, { ok: true });
  };
  await get("health", { fetchImpl });
  await post("users", { body: { username: "bob" }, fetchImpl });
  await del("users/bob", { body: { confirm: "bob" }, fetchImpl });
  assert.equal(calls[0][1].headers.Accept, "application/json");
  assert.equal(calls[0][1].headers["Content-Type"], undefined);
  assert.equal(calls[0][1].credentials, "same-origin");
  assert.equal(calls[1][0], "api/users");
  assert.equal(calls[1][1].method, "POST");
  assert.equal(calls[1][1].headers["Content-Type"], "application/json");
  assert.equal(calls[1][1].body, '{"username":"bob"}');
  assert.equal(calls[2][1].method, "DELETE");
  assert.equal(calls[2][1].body, '{"confirm":"bob"}');
});
