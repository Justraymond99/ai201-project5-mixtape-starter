# Project Journal

## Week 8 — Reproduction & solution planning

**Reproduction commit link:** [test: document missing final playlist song reproduction](https://github.com/Justraymond99/ai201-project5-mixtape-starter/commit/c8885427f1c78527cf8b938c617964e443e84cc5)

**Reproduction summary:**
I reproduced the issue by tracing `get_playlist_songs()` and running the playlist tests with a five-song fixture. The database query returned all five songs, but the `songs[:-1]` slice removed the final item, so the service returned only four songs.

**PLAN.md link:** [PLAN.md](https://github.com/Justraymond99/ai201-project5-mixtape-starter/blob/bugfix/mixtape/PLAN.md)

**Walkthrough video (recommended):** Not recorded.

**Blockers or open questions:**
No current blockers. I will add or confirm focused coverage for a one-song playlist and run the complete test suite before finalizing the fix in Week 9.
