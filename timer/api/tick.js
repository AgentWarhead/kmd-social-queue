// The publisher timer (2026-11-18). GitHub fires the publisher's own cron only
// every few hours, so posts on every account ran late. Vercel calls this every
// 5 minutes (vercel.json) and it starts the publisher workflow, which posts
// whatever is due for every account, one post per account per run.
// Only Vercel's cron may call it: Vercel sends "Bearer <CRON_SECRET>".
// The GitHub key (PUBLISHER_GITHUB_TOKEN, AgentWarhead, kmd-social-queue only,
// Actions read and write) lives in Vercel's settings and is never logged.
export default async function handler(req, res) {
  const secret = process.env.CRON_SECRET;
  if (!secret || req.headers.authorization !== `Bearer ${secret}`) {
    return res.status(401).json({ ok: false, error: "not the cron" });
  }
  const token = process.env.PUBLISHER_GITHUB_TOKEN;
  if (!token) return res.status(500).json({ ok: false, error: "PUBLISHER_GITHUB_TOKEN is not set" });
  const r = await fetch(
    "https://api.github.com/repos/AgentWarhead/kmd-social-queue/actions/workflows/publish.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kmd-publisher-timer",
      },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  // GitHub answers 204 when the run is started. Anything else fails loudly,
  // so it shows in Vercel's logs and its failed-cron notice.
  if (r.status !== 204) {
    const text = (await r.text()).slice(0, 300);
    console.error(`dispatch failed: ${r.status} ${text}`);
    return res.status(502).json({ ok: false, status: r.status });
  }
  return res.status(200).json({ ok: true, started: new Date().toISOString() });
}
