# Publisher timer

A Vercel project with this folder as its Root Directory. Every 5 minutes
Vercel calls /api/tick, which starts the publisher workflow on GitHub. The
publisher posts whatever is due for every account, one post per account
per run, so accounts never wait on each other.

Settings in Vercel (Production):

- PUBLISHER_GITHUB_TOKEN: a fine-grained GitHub token from AgentWarhead,
  this repo only, Actions read and write.
- CRON_SECRET: any long random string. Vercel sends it with each cron call.

Needs a Pro plan: Hobby allows a cron once a day only.
