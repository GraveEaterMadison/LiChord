from lichord_presence.config import PresenceConfig


def test_player_service_selection_is_validated():
    selected = PresenceConfig.from_mapping({"player_service": "org.mpris.MediaPlayer2.spotify"})
    invalid = PresenceConfig.from_mapping({"player_service": "com.attacker.Player"})
    assert selected.player_service == "org.mpris.MediaPlayer2.spotify"
    assert invalid.player_service == ""
