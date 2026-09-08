// KMD Instagram cloud publisher. Runs on GitHub Actions cron; publishes
// due queue entries via the Instagram Graph API. The laptop is not the
// clock; this is. Token comes from the META_GRAPH_TOKEN repo secret.
import { readFileSync, writeFileSync } from "node:fs";

const IG_ID = "17841446312533398";
const TOKEN = process.env.META_GRAPH_TOKEN;
const REPO = process.env.GITHUB_REPOSITORY || "AgentWarhead/kmd-social-queue";
const RAW = `https://raw.githubusercontent.com/${REPO}/main/`;
const API = "https://graph.facebook.com/v21.0";

if (!TOKEN) { console.error("no META_GRAPH_TOKEN"); process.exit(1); }

const queue = JSON.parse(readFileSync("queue.json", "utf8"));
const now = new Date();
let changed = false;

// The cron asks for every 15 minutes and GitHub does not oblige. Measured
// over 30 real runs the gap ran 1.7 to 5.8 hours, median 3.3. Slots four
// hours apart therefore land in the SAME run, and the loop below would
// fire them seconds apart. So a run publishes at most one post, and only
// if the last one has had time to breathe. A backlog drains one per run;
// posts arriving late is a schedule slipping, posts arriving together is
// a feed looking broken.
const MIN_GAP_MIN = 45;
const lastPublished = queue
  .filter(e => e.status === "published" && e.published_at)
  .map(e => new Date(e.published_at))
  .sort((a, b) => b - a)[0];
if (lastPublished) {
  const mins = (now - lastPublished) / 60000;
  if (mins < MIN_GAP_MIN) {
    console.log(`last post was ${Math.round(mins)} min ago, under the ${MIN_GAP_MIN} min floor; holding`);
    process.exit(0);
  }
}

async function api(path, params) {
  const body = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = await fetch(`${API}/${path}`, { method: "POST", body });
  const json = await res.json();
  if (json.error) throw new Error(json.error.message);
  return json;
}

async function waitReady(containerId, attempts = 12) {
  for (let i = 0; i < attempts; i++) {
    const res = await fetch(`${API}/${containerId}?fields=status_code&access_token=${TOKEN}`);
    const json = await res.json();
    if (json.status_code === "FINISHED") return;
    if (json.status_code === "ERROR") throw new Error("container ERROR");
    await new Promise(r => setTimeout(r, 5000));
  }
  throw new Error("container not ready after 60s");
}

async function publishImage(entry) {
  const c = await api(`${IG_ID}/media`, {
    image_url: RAW + entry.image,
    caption: entry.caption,
  });
  await waitReady(c.id);
  const pub = await api(`${IG_ID}/media_publish`, { creation_id: c.id });
  return pub.id;
}

async function publishCarousel(entry) {
  const children = [];
  for (const img of entry.images) {
    const c = await api(`${IG_ID}/media`, {
      image_url: RAW + img,
      is_carousel_item: "true",
    });
    await waitReady(c.id);
    children.push(c.id);
  }
  const carousel = await api(`${IG_ID}/media`, {
    media_type: "CAROUSEL",
    children: children.join(","),
    caption: entry.caption,
  });
  await waitReady(carousel.id);
  const pub = await api(`${IG_ID}/media_publish`, { creation_id: carousel.id });
  return pub.id;
}

for (const entry of queue) {
  if (entry.status !== "pending") continue;
  if (new Date(entry.publish_at) > now) continue;
  try {
    console.log(`publishing ${entry.id}...`);
    const mediaId = entry.video ? await publishReel(entry) : entry.images ? await publishCarousel(entry) : await publishImage(entry);
    entry.status = "published";
    entry.media_id = mediaId;
    entry.published_at = new Date().toISOString();
    console.log(`published ${entry.id} -> ${mediaId}`);
    changed = true;
    break;   // one per run, so a backlog spaces itself out
  } catch (e) {
    entry.attempts = (entry.attempts || 0) + 1;
    entry.error = String(e.message).slice(0, 300);
    if (entry.attempts >= 3) {
      entry.status = "failed";
      console.error(`FAILED ${entry.id} after ${entry.attempts} attempts: ${entry.error}`);
    } else {
      console.error(`RETRY ${entry.id} (attempt ${entry.attempts}/3, next tick): ${entry.error}`);
    }
  }
  changed = true;
}

if (changed) {
  writeFileSync("queue.json", JSON.stringify(queue, null, 2) + "\n");
  console.log("queue updated");
} else {
  console.log("nothing due");
}

// A failed post turns the run red so GitHub emails the boss.
// The queue write above still happened; the failure is loud, not lost.
if (queue.some(e => e.status === "failed" && !e.acknowledged)) {
  console.error("one or more posts FAILED; see queue.json");
  process.exit(1);
}

// Reels: video processing is slower, so the readiness poll gets 5 minutes.
async function publishReel(entry) {
  const c = await api(`${IG_ID}/media`, {
    media_type: "REELS",
    video_url: RAW + entry.video,
    caption: entry.caption,
    share_to_feed: "true",
  });
  await waitReady(c.id, 100);
  const pub = await api(`${IG_ID}/media_publish`, { creation_id: c.id });
  return pub.id;
}
