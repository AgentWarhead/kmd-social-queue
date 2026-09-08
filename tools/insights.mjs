// Reads what actually happened to every post this repo published.
//
//     node tools/insights.mjs            summary by format and by post
//     node tools/insights.mjs --json     the raw rows, for further work
//
// Joins queue.json (which knows the lane, the format and the caption we
// chose) against the Graph API (which knows what it did). Neither side can
// answer "which lane works" alone, which is the whole reason this exists.
//
// The supported metric set was discovered by asking the API, not assumed,
// and it DIFFERS BY PRODUCT TYPE. Reels refuse profile_visits and follows.
// The Graph API rejects the whole request when one metric is invalid, so
// asking for the feed set on a reel returns nothing at all. The first
// version of this file did exactly that, printed a dash for all twelve
// reels, and very nearly taught its reader that reels get no reach. They
// are in fact the best performing format on this account by a factor of
// three. A blank is now a loud error, never a quiet zero.

import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const IG_ID = "17841446312533398";
const API = "https://graph.facebook.com/v21.0";

let TOKEN = process.env.META_GRAPH_TOKEN;
if (!TOKEN) {
  try {
    TOKEN = execFileSync("powershell.exe",
      ["-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('META_GRAPH_TOKEN','User')"],
      { encoding: "utf8" }).trim();
  } catch { /* ignore */ }
}
if (!TOKEN) { console.error("no META_GRAPH_TOKEN"); process.exit(1); }

const get = async (p) =>
  (await fetch(`${API}/${p}${p.includes("?") ? "&" : "?"}access_token=${TOKEN}`)).json();

const COMMON = ["reach", "views", "saved", "shares", "likes", "comments", "total_interactions"];
const FEED_ONLY = ["profile_visits", "follows"];
const metricsFor = (productType) =>
  productType === "REELS" ? COMMON : COMMON.concat(FEED_ONLY);

const queue = JSON.parse(readFileSync(path.join(ROOT, "queue.json"), "utf8"));
const published = queue.filter((e) => e.status === "published" && e.media_id);

const format = (e) => (e.video ? "reel" : e.images ? "carousel" : "image");
const rows = [];

for (const e of published) {
  const meta = await get(`${e.media_id}?fields=media_product_type,timestamp,permalink`);
  if (meta.error) {
    rows.push({ id: e.id, format: format(e), gone: true, reason: meta.error.message.slice(0, 60) });
    continue;
  }
  const wanted = metricsFor(meta.media_product_type);
  const r = await get(`${e.media_id}/insights?metric=${wanted.join(",")}`);
  const m = {};
  if (r.error) {
    // Never let a refused request read as a row of zeros.
    console.error(`INSIGHTS REFUSED for ${e.id} (${meta.media_product_type}): ${r.error.message.slice(0, 120)}`);
    process.exitCode = 1;
  } else {
    for (const d of r.data) m[d.name] = d.values[0].value;
  }
  rows.push({
    id: e.id,
    format: format(e),
    product: meta.media_product_type,
    posted: meta.timestamp.slice(0, 10),
    permalink: meta.permalink,
    words: e.caption.split(/\s+/).length,
    ...m,
  });
}

const acct = await get(`${IG_ID}?fields=followers_count,media_count,username`);

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ account: acct, rows }, null, 2));
  process.exit(0);
}

const live = rows.filter((r) => !r.gone);
const gone = rows.filter((r) => r.gone);
const sum = (xs, k) => xs.reduce((a, b) => a + (b[k] || 0), 0);
const avg = (xs, k) => (xs.length ? sum(xs, k) / xs.length : 0);

console.log(`@${acct.username}  ${acct.followers_count} followers  ${acct.media_count} posts on the account`);
console.log(`${live.length} of them published by this queue and still readable` +
            (gone.length ? `, ${gone.length} unreadable` : ""));
console.log();

console.log("BY FORMAT");
console.log("format     n   reach   views   likes  saves  shares  comments  follows  reach/follower");
console.log("-".repeat(94));
for (const f of ["reel", "carousel", "image"]) {
  const xs = live.filter((r) => r.format === f);
  if (!xs.length) continue;
  console.log(
    `${f.padEnd(9)} ${String(xs.length).padStart(2)}  ` +
    `${avg(xs, "reach").toFixed(1).padStart(6)}  ${avg(xs, "views").toFixed(1).padStart(6)}  ` +
    `${avg(xs, "likes").toFixed(1).padStart(6)} ${avg(xs, "saved").toFixed(1).padStart(6)} ` +
    `${avg(xs, "shares").toFixed(1).padStart(7)} ${avg(xs, "comments").toFixed(1).padStart(9)} ` +
    `${avg(xs, "follows").toFixed(1).padStart(8)}  ` +
    `${(avg(xs, "reach") / acct.followers_count * 100).toFixed(1).padStart(6)}%`);
}
const all = live;
console.log("-".repeat(94));
console.log(`${"ALL".padEnd(9)} ${String(all.length).padStart(2)}  ` +
  `${avg(all, "reach").toFixed(1).padStart(6)}  ${avg(all, "views").toFixed(1).padStart(6)}  ` +
  `${avg(all, "likes").toFixed(1).padStart(6)} ${avg(all, "saved").toFixed(1).padStart(6)} ` +
  `${avg(all, "shares").toFixed(1).padStart(7)} ${avg(all, "comments").toFixed(1).padStart(9)} ` +
  `${avg(all, "follows").toFixed(1).padStart(8)}  ` +
  `${(avg(all, "reach") / acct.followers_count * 100).toFixed(1).padStart(6)}%`);

console.log();
console.log("EVERY POST, best reach first");
console.log("reach  views  likes  saves  shr  cmt  fol  format    posted      id");
console.log("-".repeat(94));
for (const r of [...live].sort((a, b) => (b.reach || 0) - (a.reach || 0))) {
  console.log(
    `${String(r.reach ?? "-").padStart(5)}  ${String(r.views ?? "-").padStart(5)}  ` +
    `${String(r.likes ?? "-").padStart(5)}  ${String(r.saved ?? "-").padStart(5)}  ` +
    `${String(r.shares ?? "-").padStart(3)}  ${String(r.comments ?? "-").padStart(3)}  ` +
    `${String(r.follows ?? "-").padStart(3)}  ${r.format.padEnd(9)} ${r.posted}  ${r.id}`);
}

if (gone.length) {
  console.log();
  console.log("UNREADABLE (deleted on Instagram, or the id is not a published media id)");
  for (const r of gone) console.log(`  ${r.format.padEnd(9)} ${r.id}`);
}

const totalFollows = sum(live, "follows");
const totalReach = sum(live, "reach");
console.log();
console.log(`Totals across ${live.length} posts: ${totalReach} reach, ${sum(live, "total_interactions")} interactions, ` +
            `${sum(live, "profile_visits")} profile visits, ${totalFollows} follows.`);
