"""Regression tests for song interaction notifications."""

import pytest

from app import create_app, db
from models import Notification, Song, User
from services.notification_service import rate_song


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def test_rating_another_users_song_creates_notification(app):
    with app.app_context():
        sharer = User(username="aaliya", email="aaliya@example.com")
        rater = User(username="kenji", email="kenji@example.com")
        db.session.add_all([sharer, rater])
        db.session.flush()

        song = Song(title="Neon City", artist="Night Transit", shared_by=sharer.id)
        db.session.add(song)
        db.session.commit()

        rate_song(rater.id, song.id, 5)

        notification = db.session.query(Notification).filter_by(
            user_id=sharer.id,
            notification_type="song_rated",
        ).one()
        assert "kenji" in notification.body
        assert "Neon City" in notification.body
        assert "5 stars" in notification.body


def test_rating_own_song_does_not_notify_self(app):
    with app.app_context():
        sharer = User(username="solo", email="solo@example.com")
        db.session.add(sharer)
        db.session.flush()

        song = Song(title="Self Review", artist="Solo", shared_by=sharer.id)
        db.session.add(song)
        db.session.commit()

        rate_song(sharer.id, song.id, 4)

        assert db.session.query(Notification).filter_by(user_id=sharer.id).count() == 0
