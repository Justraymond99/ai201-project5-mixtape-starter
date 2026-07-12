# Mixtape Bug Hunt Submission

## AI Usage

I used ChatGPT as a code-navigation and debugging assistant during this project. I first used it to summarize the repository structure, identify the responsibilities of the model, route, and service layers, and trace the documented route-to-service call chains. During investigation, I used it to compare the working playlist notification flow with the rating flow, explain the difference between a rolling 24-hour window and a calendar-day boundary, inspect how SQL joins can duplicate ORM entities, and generate boundary-focused regression test cases.

I did not treat the AI's first explanation as proof of a root cause. Each diagnosis was verified against the actual implementation and the behavior encoded in the repository's tests. For the feed and notification bugs, I added focused regression tests that construct the failing state directly. The final fixes are deliberately small and limited to the affected service functions.

## Codebase Map

### Main files and responsibilities

- `app.py` creates the Flask application, configures SQLAlchemy, registers the song, playlist, user, and feed blueprints, and creates the database tables.
- `models.py` defines the application's SQLAlchemy data model. `User` stores profile, friendship, streak, and last-listened state. `Song` stores shared-song metadata and connects to tags, ratings, and listening events. `ListeningEvent` records when a user played a song. `Rating` stores one score per user/song pair. `Playlist` uses the `playlist_entries` association table to store song membership, explicit position, who added the song, and when it was added. `Notification` stores recipient, type, body, creation time, and read state.
- `routes/songs.py` handles song-facing HTTP endpoints such as search and rating, validates request data, and delegates business logic to services.
- `routes/playlists.py` handles playlist creation, song addition, and playlist-song retrieval.
- `routes/users.py` handles user profile, streak, and notification endpoints.
- `routes/feed.py` handles the listening-now and general activity-feed endpoints.
- `services/streak_service.py` creates listening events and updates the user's consecutive-calendar-day streak.
- `services/feed_service.py` queries listening events for friends and formats listening-now and activity responses.
- `services/search_service.py` searches songs by title or artist and serializes their tags.
- `services/notification_service.py` creates and retrieves notifications and owns the song-rating and playlist-add interaction flows.
- `services/playlist_service.py` creates playlists and retrieves songs ordered by `playlist_entries.position`.
- `seed_data.py` creates representative users, friendships, songs, tags, listening events, ratings, playlists, and notifications for local testing.
- `tests/` contains focused service-layer tests using an in-memory SQLite database.

### Data flow: rating a song

1. A client sends `POST /songs/<song_id>/rate`.
2. `routes/songs.py` parses the user ID and score, then calls `notification_service.rate_song()`.
3. `rate_song()` validates the score, loads the `Song` and rating `User`, and either inserts a new `Rating` or updates the existing rating for that user/song pair.
4. The rating is committed.
5. When the rater is not the original sharer, the service creates a `song_rated` notification for the song's `shared_by` user.
6. The route serializes the rating and returns the HTTP response.

### Pattern noticed

The routes are thin adapters: they parse HTTP input and format responses, while the service layer owns business rules, database queries, and side effects. The five reported bugs were therefore traceable from endpoint to a small number of service functions. The models also reveal several important domain rules: ratings are unique per user/song pair, playlists have explicit ordering in an association table, and song tags form a many-to-many relationship that can multiply SQL rows during joins.

---

## Issue #1 — My listening streak keeps resetting

### How I reproduced it

I used the existing streak test setup with a user who listened on Saturday, June 15, 2024 and then again on Sunday, June 16, 2024. Calling `update_listening_streak()` for Saturday set the streak to 1. Calling it for the immediately following Sunday incorrectly left/reset the streak at 1 instead of incrementing it to 2.

### How I found the root cause

I traced the documented endpoint from the user streak/listening behavior into `services/streak_service.py`, then read `record_listening_event()` and `update_listening_streak()` top to bottom. The calculated `days_since_last` value was correct for Saturday-to-Sunday: it was exactly 1. The suspicious part was the additional weekday condition attached to the consecutive-day branch. The existing Sunday-specific regression test confirmed that this condition was the exact cause.

### The root cause

The code only incremented a streak when `days_since_last == 1 and today.weekday() != 6`. Python's `weekday()` returns `6` for Sunday, so every valid Saturday-to-Sunday consecutive listen was deliberately excluded from the increment branch and fell into the reset branch. The streak requirement is based on consecutive calendar days, not weekdays or week boundaries, so the Sunday check was unrelated to the domain rule.

### My fix and side-effect check

I removed the Sunday exclusion and now increment whenever `days_since_last == 1`. Same-day listens still return without incrementing, first listens still start at 1, and gaps of two or more days still reset to 1. The existing tests cover first listen, same-day duplicate listens, ordinary consecutive days, skipped days, and the Saturday-to-Sunday boundary.

---

## Issue #2 — Friends Listening Now shows people from yesterday

### How I reproduced it

I fixed the service clock at 9:00 AM UTC on June 17, 2024, created a friend listening event at 11:00 PM UTC on June 16, and called `get_friends_listening_now()`. Under the original rolling 24-hour filter, the event was only ten hours old and therefore appeared even though it belonged to the previous calendar day.

### How I found the root cause

I traced `GET /feed/<user_id>/listening-now` into `services/feed_service.py`. The service defined `RECENT_THRESHOLD = timedelta(hours=24)` and calculated `cutoff = now - 24 hours`. I compared that implementation to the user-facing requirement, which says the feed should show what friends played today. The mismatch became conclusive when the controlled test showed that a previous-day event still satisfied the rolling cutoff.

### The root cause

The service implemented “within the last 24 hours,” but the feature requires “on the current calendar day.” A rolling duration crosses midnight. At 9:00 AM, an event from 11:00 PM yesterday is recent in elapsed-time terms but is not from today, so it should not appear.

### My fix and side-effect check

I replaced the rolling cutoff with the start of the current UTC day: midnight with hour, minute, second, and microsecond set to zero. The query now includes events at or after today's boundary. I added regression coverage proving that an event from 11:00 PM yesterday is excluded, while multiple events from today are included and still deduplicated to the most recent song per friend. The separate general activity feed was left unchanged because its documentation explicitly says it is not filtered by recency.

---

## Issue #3 — The same song keeps showing up twice in search

### How I reproduced it

I searched for `Crown Heights`, which matches `Crown Heights Anthem`. That song has three tags in the test data. The original search returned the same song three times, while songs with zero or one tag appeared once.

### How I found the root cause

I traced `GET /songs/search` to `services/search_service.py` and examined the SQLAlchemy query. The query selected `Song` rows and outer-joined the `song_tags` association table. I then compared the result counts to tag counts in `tests/test_search.py`. The duplicate count matching the number of tag rows made the join multiplication the confirmed cause.

### The root cause

A many-to-many join produces one SQL row for each matching song/tag association. Because the query joined `song_tags` but did not deduplicate the selected songs, a song with three tags produced three result rows. The duplication was conditional on tag count, which explains why some songs appeared once and others appeared multiple times.

### My fix and side-effect check

I added `.distinct()` to the song query so each matching `Song` is returned once regardless of how many tag associations it has. Tag serialization still works through the model relationship. The existing search tests cover songs with no tags, one tag, multiple tags, no matches, and ordinary title/artist matches.

---

## Issue #4 — Rating a shared song does not create a notification

### How I reproduced it

I created two users, made one user the original sharer of a song, and had the other user rate it five stars through `rate_song()`. The `Rating` row was saved successfully, but querying `Notification` for the sharer returned no `song_rated` notification.

### How I found the root cause

I traced the rating endpoint to `notification_service.rate_song()` and compared it line by line with the working `add_to_playlist()` flow in the same module. Both flows validated the actor and song and committed the interaction. The playlist path then called `create_notification()` for the original sharer, while the rating path returned immediately after committing the rating. That structural difference precisely matched the symptom: the primary action succeeded, but its notification side effect never happened.

### The root cause

The rating workflow had no notification creation step. There was no typo or failed query; the architectural orchestration was incomplete. `rate_song()` persisted the rating and returned it without creating a `song_rated` notification for the song's original sharer.

### My fix and side-effect check

After committing the rating, I now call `create_notification()` when the rater is not the original sharer. The notification includes the rater username, song title, and score. I added regression tests proving that rating another user's song creates exactly the expected notification and rating one's own song does not create a self-notification. Score validation and existing-rating update behavior remain unchanged.

---

## Issue #5 — The last song in a playlist never shows up

### How I reproduced it

I created a playlist containing five songs in positions 1 through 5 and called `get_playlist_songs()`. The original function returned only four songs. When another song is added, the previously omitted song moves out of the final position and appears, while the newly final song becomes the omitted one.

### How I found the root cause

I traced `GET /playlists/<playlist_id>/songs` into `services/playlist_service.py`. The SQL query correctly joined `playlist_entries`, filtered by playlist ID, sorted by ascending position, and loaded all rows. The final return expression then serialized `songs[:-1]`. Because Python slices exclude the final element when using `[:-1]`, the problem was isolated to the response construction rather than the database query or playlist ordering.

### The root cause

The service intentionally sliced the complete ordered result list with `songs[:-1]`. That expression returns every element except the last. As new songs were appended at the highest position, the identity of the hidden song changed, exactly matching the user's report.

### My fix and side-effect check

I removed the slice and serialize the full `songs` list. The existing playlist tests verify that all songs are returned, ordering is preserved, and an empty playlist returns an empty list. Removing the slice also handles a one-song playlist correctly instead of turning it into an empty response.

---

## Commit Review

The `bugfix/mixtape` branch contains separate conventional commits for each fix:

- `fix: preserve streak across Sunday boundary`
- `fix: filter listening-now feed to current day`
- `fix: deduplicate songs with multiple tags in search`
- `fix: notify sharers when their songs are rated`
- `fix: return the final song in playlist results`
- `test: cover calendar-day listening feed boundary`
- `test: cover rating notification regression`
- `docs: add codebase map and root cause analyses`

## Git Log Screenshot

Add the required screenshot of `git log --oneline` here before submitting through the course portal.
