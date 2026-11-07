from lichord_presence.config import PresenceConfig
from lichord_presence.discord_ipc import build_activity, link_for, text_for

def test_all_text_slots():
    track = {"title": "Song", "artist": "Artist", "album": "Record"}
    assert text_for("title", track) == "Song"
    assert text_for("artist", track) == "Artist"
    assert text_for("album", track) == "Record"
    assert text_for("artist_album", track) == "Artist — Record"
    assert text_for("off", track) is None

def test_default_activity_has_listening_type_and_buttons():
    cfg = PresenceConfig.from_mapping({"application_id": "123"})
    track = {"title": "Song", "artist": "Artist", "album": "Record",
             "video_id": "abc123", "artwork": "https://example.com/art.jpg"}
    payload = build_activity(cfg, track, True, 10, 200, now=1000)
    assert payload["type"] == 2
    assert payload["details"] == "Song"
    assert payload["state"] == "Artist"
    assert payload["timestamps"] == {"start": 990, "end": 1190}
    assert len(payload["buttons"]) == 2

def test_hide_details_does_not_leak_track_metadata():
    cfg = PresenceConfig.from_mapping({"hide_details": True})
    payload = build_activity(cfg, {"title": "Private song", "artist": "Private artist"}, True, 1, 10)
    assert "details" not in payload and "state" not in payload and "assets" not in payload

def test_paused_activity_has_no_timestamps():
    cfg = PresenceConfig.from_mapping({"timestamps": True})
    payload = build_activity(cfg, {"title": "Song"}, False, 20, 100)
    assert "timestamps" not in payload

def test_local_track_never_gets_external_links():
    assert link_for("title", {"local": True, "video_id": "/home/user/music.flac"}) is None

def test_config_rejects_invalid_options():
    cfg = PresenceConfig.from_mapping({"line1": "not-a-field", "button1": "script"})
    assert cfg.line1 == "title"
    assert cfg.button1 == "off"



def test_clickable_lines_use_matching_discord_url_fields():
    cfg = PresenceConfig.from_mapping({"link_line1": True, "link_line2": True})
    track = {
        "title": "Song",
        "artist": "Artist",
        "album": "Record",
        "video_id": "abc123",
        "artist_id": "artist123",
    }
    payload = build_activity(cfg, track, True, 0, 100, now=1000)
    assert payload["details_url"] == "https://music.youtube.com/watch?v=abc123"
    assert payload["state_url"] == "https://music.youtube.com/channel/artist123"


def test_clickable_line_without_matching_url_is_omitted():
    cfg = PresenceConfig.from_mapping({"link_line1": True, "link_line2": True})
    payload = build_activity(
        cfg, {"title": "Local song", "artist": "Local artist", "local": True}, True, 0, 0
    )
    assert "details_url" not in payload
    assert "state_url" not in payload


def test_non_https_artwork_and_badge_are_omitted():
    cfg = PresenceConfig.from_mapping({"badge_url": "http://example.com/badge.png"})
    payload = build_activity(
        cfg, {"title": "Song", "artwork": "http://example.com/art.png"}, True, 0, 0
    )
    assert "assets" not in payload


def test_config_load_uses_the_same_validation_as_mapping(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"line1":"invalid","application_id":"not-a-number","badge_url":"http://bad"}'
    )
    cfg = PresenceConfig.load(path)
    assert cfg.line1 == "title"
    assert cfg.application_id == ""
    assert cfg.badge_url == ""


def test_config_rejects_non_https_application_url():
    cfg = PresenceConfig.from_mapping({"app_url": "javascript:alert(1)"})
    assert cfg.app_url == PresenceConfig().app_url
