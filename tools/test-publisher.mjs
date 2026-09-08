// The publisher's scheduling rules, tested without touching Instagram.
//
//     node tools/test-publisher.mjs
//
// Born 2026-09-08. The cron asks for every 15 minutes and GitHub does not
// oblige: measured over 30 real runs the gap ran 1.7 to 5.8 hours, median
// 3.3. The loop published every due entry back to back, so two slots four
// hours apart landed in one run and went out seconds apart. Posts arriving
// late is a schedule slipping. Posts arriving together is a feed looking
// broken.
//
// It runs the REAL publish.mjs with fetch stubbed, so it tests the shipped
// file rather than a copy of its logic. Point it at the pre-fix version and
// the first case fails, which is the only reason to trust it.

import { writeFileSync, copyFileSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const RUNNER = `
let n = 0;
globalThis.fetch = async (url, opts) => {
  const u = String(url);
  if (opts && opts.method === "POST" && u.includes("/media_publish"))
    return { json: async () => ({ id: "MEDIA_" + ++n }) };
  if (opts && opts.method === "POST" && u.includes("/media")) {
    if (String(opts.body).includes("BOOM"))
      return { json: async () => ({ error: { message: "simulated Graph API failure" } }) };
    return { json: async () => ({ id: "CONTAINER_" + Math.random().toString(36).slice(2, 7) }) };
  }
  if (u.includes("fields=status_code"))
    return { json: async () => ({ status_code: "FINISHED" }) };
  return { json: async () => ({ error: { message: "unstubbed " + u } }) };
};
await import("./publish.mjs");
`;

const hoursAgo = (h) => new Date(Date.now() - h * 3600e3).toISOString();
const minsAgo = (m) => new Date(Date.now() - m * 60e3).toISOString();

const due = [
  { id: "a", publish_at: hoursAgo(6), image: "x.jpg", caption: "a", status: "pending" },
  { id: "b", publish_at: hoursAgo(4), image: "x.jpg", caption: "b", status: "pending" },
  { id: "c", publish_at: hoursAgo(2), image: "x.jpg", caption: "c", status: "pending" },
];
const alreadyPosted = (m) => ({
  id: "z", publish_at: hoursAgo(8), image: "x.jpg", caption: "z",
  status: "published", published_at: minsAgo(m),
});

const failing = (attempts) => ({
  id: "bad", publish_at: hoursAgo(9), image: "x.jpg", caption: "BOOM",
  status: "pending", ...(attempts ? { attempts } : {}),
});

const CASES = [
  { name: "three due at once publishes exactly one", queue: due, expect: 1 },
  { name: "a post ten minutes old holds the next one", queue: [alreadyPosted(10), ...due], expect: 0 },
  { name: "a post ninety minutes old lets one through", queue: [alreadyPosted(90), ...due], expect: 1 },
  { name: "nothing due publishes nothing", expect: 0,
    queue: [{ id: "f", publish_at: new Date(Date.now() + 6 * 3600e3).toISOString(),
              image: "x.jpg", caption: "f", status: "pending" }] },

  // The duplicate-post bug. A run that tips a post to failed must go red
  // ONCE. Every run after that must be green, or the workflow stops
  // committing queue.json and republishes everything that succeeded.
  { name: "a third strike turns THIS run red", queue: [failing(2)], expect: 0, exit: 1 },
  { name: "a post that failed on an earlier run leaves this one green",
    queue: [{ ...failing(3), status: "failed" }, ...due], expect: 1, exit: 0 },
  { name: "a first strike does not turn the run red", queue: [failing(0)], expect: 0, exit: 0 },
];

let failed = 0;
for (const c of CASES) {
  const dir = mkdtempSync(path.join(tmpdir(), "kmdpub-"));
  try {
    copyFileSync(path.join(ROOT, "publish.mjs"), path.join(dir, "publish.mjs"));
    writeFileSync(path.join(dir, "runner.mjs"), RUNNER);
    writeFileSync(path.join(dir, "queue.json"), JSON.stringify(c.queue, null, 2));
    let out = "", code = 0;
    try {
      out = execFileSync(process.execPath, ["runner.mjs"],
        { cwd: dir, encoding: "utf8", env: { ...process.env, META_GRAPH_TOKEN: "test-token" } });
    } catch (e) {
      out = (e.stdout || "") + (e.stderr || ""); code = e.status;
    }
    const q = JSON.parse(readFileSync(path.join(dir, "queue.json"), "utf8"));
    const posted = q.filter((e) => e.status === "published" && e.id !== "z").map((e) => e.id);
    const exitOk = c.exit === undefined || code === c.exit;
    const ok = posted.length === c.expect && exitOk;
    if (!ok) failed++;
    console.log(`${ok ? "ok  " : "FAIL"}  ${c.name}`);
    console.log(`        expected ${c.expect} published, got ${posted.length}${posted.length ? " (" + posted.join(",") + ")" : ""}` +
      (c.exit === undefined ? "" : `; expected exit ${c.exit}, got ${code}`));
    if (!ok) console.log(out.split("\n").map((l) => "        | " + l).join("\n"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

console.log(failed ? `\n${failed} of ${CASES.length} FAILED` : `\nPASS: ${CASES.length} cases`);
process.exit(failed ? 1 : 0);
