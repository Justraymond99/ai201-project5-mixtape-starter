# Issue reproduction — Last playlist song is missing

## Environment

- Branch: `bugfix/mixtape`
- Test file: `tests/test_playlists.py`
- Service under test: `services/playlist_service.py`

## Steps to reproduce

1. Create a playlist containing five songs with positions 1 through 5.
2. Call `get_playlist_songs(playlist_id)`.
3. Inspect the returned list length and song titles.

The existing test `test_playlist_returns_all_songs` captures the reproduction:

```python
songs = get_playlist_songs(playlist_id)
assert len(songs) == 5
```

Before the fix, the service returned:

```python
return [song.to_dict() for song in songs[:-1]]
```

The `songs[:-1]` slice excludes the final item. A five-song playlist therefore returns only four songs, and a one-song playlist returns an empty list.

## Expected behavior

`get_playlist_songs` should return every song associated with the playlist, ordered by ascending playlist position.

## Actual behavior reproduced

The final song is omitted from every non-empty playlist because the result list is sliced before serialization.

## Reproduction command

```bash
pytest tests/test_playlists.py -q
```

With the buggy implementation, `test_playlist_returns_all_songs` and `test_playlist_returns_songs_in_order` fail. The empty-playlist test still passes, which can hide the off-by-one error if only empty-state behavior is checked.
