"""Regression tests for the Friends Listening Now feed."""

from datetime import datetime, timezone

import pytest

from app import create_app, db
from models import ListeningEvent, Song, User
from services import feed_service


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def test_listening_now_excludes_previous_calendar_day(app, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2024, 6, 17, 9, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(feed_service, "datetime", FixedDateTime)

    with app.app_context():
        viewer = User(username="viewer", email="viewer@example.com")
        friend = User(username="friend", email="friend@example.com")
        db.session.add_all([viewer, friend])
        db.session.flush()
        viewer.friends.append(friend)

        song = Song(title="Late Night Track", artist="Artist", shared_by=friend.id)
        db.session.add(song)
        db.session.flush()

        yesterday = ListeningEvent(
            user_id=friend.id,
            song_id=song.id,
            listened_at=datetime(2024, 6, 16, 23, 0, tzinfo=timezone.utc),
        )
        db.session.add(yesterday)
        db.session.commit()

        assert feed_service.get_friends_listening_now(viewer.id) == []


def test_listening_now_includes_today_and_keeps_latest_per_friend(app, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2024, 6, 17, 9, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(feed_service, "datetime", FixedDateTime)

    with app.app_context():
        viewer = User(username="viewer2", email="viewer2@example.com")
        friend = User(username="friend2", email="friend2@example.com")
        db.session.add_all([viewer, friend])
        db.session.flush()
        viewer.friends.append(friend)

        first_song = Song(title="First", artist="Artist", shared_by=friend.id)
        latest_song = Song(title="Latest", artist="Artist", shared_by=friend.id)
        db.session.add_all([first_song, latest_song])
        db.session.flush()

        db.session.add_all([
            ListeningEvent(
                user_id=friend.id,
                song_id=first_song.id,
                listened_at=datetime(2024, 6, 17, 7, 0, tzinfo=timezone.utc),
            ),
            ListeningEvent(
                user_id=friend.id,
                song_id=latest_song.id,
                listened_at=datetime(2024, 6, 17, 8, 30, tzinfo=timezone.utc),
            ),
        ])
        db.session.commit()

        results = feed_service.get_friends_listening_now(viewer.id)
        assert len(results) == 1
        assert results[0]["song"]["title"] == "Latest"
