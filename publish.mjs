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

async function api(path, params) {
  const body = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = await fetch(`${API}/${path}`, { method: "POST", body });
  const json = await res.json();
  if (json.error) throw new Error(json.error.message);
  return json;
}

async function waitReady(containerId) {
  for (let i = 0; i < 12; i++) {
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
    const mediaId = entry.images ? await publishCarousel(entry) : await publishImage(entry);
    entry.status = "published";
    entry.media_id = mediaId;
    entry.published_at = new Date().toISOString();
    console.log(`published ${entry.id} -> ${mediaId}`);
  } catch (e) {
    entry.status = "failed";
    entry.error = String(e.message).slice(0, 300);
    console.error(`FAILED ${entry.id}: ${entry.error}`);
  }
  changed = true;
}

if (changed) {
  writeFileSync("queue.json", JSON.stringify(queue, null, 2) + "\n");
  console.log("queue updated");
} else {
  console.log("nothing due");
}
