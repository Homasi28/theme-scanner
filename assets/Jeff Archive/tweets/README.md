# @jfsrev tweet scrape

- Refreshed: 2026-09-07 06:06 UTC
- SQLite rows: 1,534 (`posts` table); originals (`is_reply=0`): 1,507.
- Date range: 2025-09-04T02:18:07.000Z through 2026-09-06T06:51:46.000Z.
- Search: `from:jfsrev -is:retweet -is:reply`; recency order; max 100; no expansions.
- Current run: 1,298 API posts returned, approximately `$6.49` (at $0.005/post). Cumulative estimate: `$8.01`.
- Target 1,500 achieved: yes.
- Remaining pagination token: `b26v89c19zqg8o3fsce6gttypi0x9ugekvpsbskzhno1p` (not followed after target).
- CSV: `/workspace/jfsrev/tweets/jfsrev_tweets.csv`
- SQLite DB: `/workspace/jfsrev/tweets/jfsrev_tweets.db`
- Raw pages: `/workspace/jfsrev/tweets/raw/search_0001.json` onward through the fetched page sequence.

The ingest preserves reply/retweet flags and uses `INSERT OR REPLACE`; every stored post has an `https://x.com/jfsrev/status/{id}` URL.
