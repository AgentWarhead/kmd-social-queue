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
let newFailure = false;

// The cron asks for every 15 minutes and GitHub does not oblige. Measured
// over 30 real runs the gap ran 1.7 to 5.8 hours, median 3.3. Slots four
// hours apart therefore land in the SAME run, and the loop below would
// fire them seconds apart. So a run publishes at most one post, and only
// if the last one has had time to breathe. A backlog drains one per run;
// posts arriving late is a schedule slipping, posts arriving together is
// a feed looking broken.
const MIN_GAP_MIN = 45;

// Retry policy, Brett's call 2026-09-08: a post is never abandoned for a
// transient failure. It keeps trying on a widening backoff until it either
// publishes or goes so far past its slot that publishing it would be worse
// than not. The old code gave up after three attempts, which meant one bad
// afternoon silently cost a post.
//
// The horizon exists because late is not free. A caption that opens with
// "Saturday." is wrong on Monday, and a scan finding described as "this
// week" stops being true. Two days is the point where the content starts
// lying, so that is where a human gets asked instead of a robot deciding.
const RETRY_BACKOFF_MIN = [15, 30, 60, 120, 240];
const GIVE_UP_HOURS = 48;
const backoffFor = (n) => RETRY_BACKOFF_MIN[Math.min(n, RETRY_BACKOFF_MIN.length) - 1];
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
  if (entry.next_try && new Date(entry.next_try) > now) continue;   // still in backoff
  try {
    console.log(`publishing ${entry.id}...`);
    const mediaId = entry.video ? await publishReel(entry) : entry.images ? await publishCarousel(entry) : await publishImage(entry);
    entry.status = "published";
    entry.media_id = mediaId;
    entry.published_at = new Date().toISOString();
    delete entry.next_try;
    delete entry.alerted;
    delete entry.error;
    console.log(`published ${entry.id} -> ${mediaId}`);
    changed = true;
    break;   // one per run, so a backlog spaces itself out
  } catch (e) {
    entry.attempts = (entry.attempts || 0) + 1;
    entry.error = String(e.message).slice(0, 300);
    const overdueH = (now - new Date(entry.publish_at)) / 3600e3;
    if (overdueH > GIVE_UP_HOURS) {
      entry.status = "missed";
      newFailure = true;
      console.error(`MISSED ${entry.id}: ${overdueH.toFixed(1)} h past its slot after ${entry.attempts} attempts. Giving up, because posting it now would be worse than not. Last error: ${entry.error}`);
    } else {
      const wait = backoffFor(entry.attempts);
      entry.next_try = new Date(now.getTime() + wait * 60000).toISOString();
      if (entry.attempts >= 3 && !entry.alerted) {
        entry.alerted = true;      // shout once, then keep working quietly
        newFailure = true;
        console.error(`STRUGGLING ${entry.id}: ${entry.attempts} attempts, ${overdueH.toFixed(1)} h overdue, still retrying every ${wait} min: ${entry.error}`);
      } else {
        console.error(`RETRY ${entry.id} (attempt ${entry.attempts}, next in ${wait} min): ${entry.error}`);
      }
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

// A failure turns the run red ONCE, on the run where it happened, so
// GitHub emails the boss.
//
// It used to go red on every later run too, because the condition read a
// queue-wide "failed" state against an "acknowledged" flag that nothing in
// this repo ever set. Two things followed. Every run stayed red forever, so
// a SECOND real failure looked identical to the first and was invisible.
// Worse, the workflow only committed queue.json when this file exited 0, so
// once a failure existed the queue status stopped being saved, and every
// post that succeeded got published again on the next run. The workflow now
// commits with if: always(), and this exits 1 only for a failure that just
// happened.
const struggling = queue.filter(e => e.status === "pending" && e.attempts);
if (struggling.length) {
  console.log(`still retrying: ${struggling.map(e => `${e.id} (${e.attempts} attempts, next ${e.next_try})`).join(", ")}`);
}
const missed = queue.filter(e => e.status === "missed");
if (missed.length) {
  console.log(`gave up on: ${missed.map(e => e.id).join(", ")} (needs a human)`);
}
if (newFailure) {
  console.error("a post needs attention; see queue.json. It is still being retried unless it says missed.");
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
