from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from bitchord_addon_auth import BitChordAuth
from lichord.server import _cached_search
from lichord_presence.web import _loopback_host


def test_auth_missing_credentials_returns_bit_chord_challenge_without_network():
    auth = BitChordAuth(hosts=["music.example.com"], get_json=lambda _url: (_ for _ in ()).throw(AssertionError()))
    result = auth.verify_headers({})
    assert not result.ok
    assert result.status == 401
    assert result.error == "missing"
    assert "WWW-Authenticate" in result.headers
    assert '"code": "missing"' in result.body


def test_auth_rejects_malformed_token_without_fetching_keys():
    auth = BitChordAuth(hosts=["music.example.com"], get_json=lambda _url: (_ for _ in ()).throw(AssertionError()))
    result = auth.verify("not.a.jwt", "v1.1234567890123." + "A" * 86)
    assert not result.ok
    assert result.error == "invalid_token"


def test_cache_coalesces_concurrent_identical_searches():
    started = Event()
    release = Event()
    count = 0
    count_lock = Lock()

    def loader():
        nonlocal count
        with count_lock:
            count += 1
        started.set()
        assert release.wait(3)
        return [{"title": "one"}]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_cached_search, ("coalesce-test",), loader) for _ in range(8)]
        assert started.wait(3)
        release.set()
        assert all(f.result(timeout=3) == [{"title": "one"}] for f in futures)
    assert count == 1


def test_settings_host_must_be_loopback():
    assert _loopback_host("127.0.0.1:8790") == "127.0.0.1"
    assert _loopback_host("[::1]:8790") == "::1"
    assert _loopback_host("localhost:8790") == "localhost"
    assert _loopback_host("attacker.example:8790") is None
