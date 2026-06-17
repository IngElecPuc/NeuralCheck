from neuralcheck.application.clock import CORRESPONDENCE, RAPID_3_0, ChessClock


def test_rapid_clock_ticks_active_player():
    clock = ChessClock.rapid_3_0()

    snapshot = clock.tick(white_turn=True)
    assert snapshot.mode == RAPID_3_0
    assert snapshot.visible
    assert snapshot.white_seconds == 179
    assert snapshot.black_seconds == 180

    snapshot = clock.tick(white_turn=False)
    assert snapshot.white_seconds == 179
    assert snapshot.black_seconds == 179


def test_correspondence_clock_is_hidden_and_does_not_tick():
    clock = ChessClock.rapid_3_0()
    clock.set_correspondence()

    snapshot = clock.tick(white_turn=True)
    assert snapshot.mode == CORRESPONDENCE
    assert not snapshot.visible
    assert not snapshot.running
    assert snapshot.white_seconds == 0
    assert snapshot.black_seconds == 0
