## Solution plan

**Issue:** [The last song in a playlist never shows up](https://github.com/Justraymond99/ai201-project5-mixtape-starter#the-five-open-issues)

### Understand

`get_playlist_songs()` correctly queries every song associated with a playlist and orders the results by `playlist_entries.position`. The defect happens after the database query: `services/playlist_service.py` serializes `songs[:-1]` instead of `songs`. Python's `[:-1]` slice intentionally stops before the final element, so the last song is removed from every non-empty result.

Expected behavior: the service should return every song in the playlist in ascending position order.

Actual behavior: a playlist with five songs returns four, and a playlist with one song returns an empty list. Empty playlists still return an empty list, which is why that case does not expose the bug.

### Map

Files and code paths involved:

- `routes/playlists.py` — receives the playlist-song request and calls the playlist service.
- `services/playlist_service.py` — contains `get_playlist_songs()` and the incorrect `songs[:-1]` slice.
- `models.py` — defines `Playlist`, `Song`, and the `playlist_entries` association table used by the query.
- `tests/test_playlists.py` — contains coverage for the returned count, ordering, and empty-playlist behavior.
- `REPRODUCTION.md` — records the local reproduction steps, observed failure, and expected behavior.

The primary implementation change belongs in `services/playlist_service.py`. Test validation belongs in `tests/test_playlists.py`.

### Plan

1. Confirm the failure by running `pytest tests/test_playlists.py -q` against the buggy implementation and verify that the five-song playlist returns only four songs.
2. Update `get_playlist_songs()` in `services/playlist_service.py` so it serializes the complete `songs` query result rather than `songs[:-1]`.
3. Run the existing playlist tests to confirm that all five songs are returned in ascending position order and that an empty playlist still returns `[]`.
4. Add or preserve a focused one-song playlist test so the off-by-one behavior cannot regress unnoticed; a single-song playlist must return exactly that one song.
5. Run the complete test suite with `pytest tests/ -q` to check that the change does not affect unrelated services or route behavior.

### Inputs & outputs

**Input:** a valid `playlist_id` passed to `get_playlist_songs()`.

The function uses that ID to load the playlist and query all associated `Song` records through `playlist_entries`, ordered by ascending `position`.

**Output:** a list of serialized song dictionaries containing every song in the playlist, in playlist order.

Behavior after the fix:

- Five-song playlist → list of five song dictionaries.
- One-song playlist → list containing one song dictionary.
- Empty playlist → empty list.
- Missing playlist ID → existing `ValueError` behavior remains unchanged.

### Risks & unknowns

- The ordering depends on `playlist_entries.position`; the fix must not remove or alter the existing `order_by(asc(...))` clause in `services/playlist_service.py`.
- Duplicate or invalid position values could produce ambiguous ordering. This issue does not require changing the data model, but `models.py` and seed data should be checked if ordering tests behave inconsistently.
- The service may be used by both direct tests and `routes/playlists.py`; the full suite should be run to ensure returning the previously omitted item does not expose assumptions about list length elsewhere.
- The current tests cover five-song and empty playlists. A one-song regression test is important because the buggy slice turns that valid playlist into an empty result.
- No pagination appears in this service. If pagination is added later, full-result behavior should be reconsidered rather than reintroducing list slicing at serialization time.

### Edge cases

- A playlist containing exactly one song should return that song.
- An empty playlist should return `[]` without raising an error.
- Songs should remain ordered by ascending `playlist_entries.position` even if they were created in a different order.
- A playlist with many songs should return the first, middle, and final entries without truncation.
- A nonexistent playlist ID should continue to raise `ValueError`.
- If two entries have the same position, the function should not silently drop either song, even though their relative order may need a future tie-breaker.
