from neuralcheck.application.clock import (
    AUTO_START,
    BLACK_SIGNAL_START,
    CORRESPONDENCE,
    ChessClock,
)


def test_rapid_clock_ticks_active_player():
    clock = ChessClock.rapid_3_0()

    snapshot = clock.tick(white_turn=True)
    assert snapshot.mode == "blitz_3_0"
    assert snapshot.visible
    assert snapshot.running
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


def test_increment_is_applied_to_player_who_moved():
    clock = ChessClock(mode="bullet_1_1")

    clock.tick(white_turn=True)
    snapshot = clock.on_move_completed(white_player=True)

    assert snapshot.white_seconds == 60
    assert snapshot.black_seconds == 60


def test_fide_control_adds_increment_from_move_one_and_bonus_after_move_40():
    clock = ChessClock(mode="fide_90_40_30_30")

    snapshot = clock.on_move_completed(white_player=True)
    assert snapshot.white_seconds == 5430

    for _ in range(39):
        snapshot = clock.on_move_completed(white_player=True)

    assert snapshot.white_seconds == 5400 + (40 * 30) + 1800


def test_black_signal_policy_waits_until_start_signal():
    clock = ChessClock(mode="blitz_3_0", start_policy=BLACK_SIGNAL_START)

    waiting = clock.snapshot()
    assert waiting.start_policy == BLACK_SIGNAL_START
    assert waiting.waiting_for_start
    assert not waiting.running

    clock.tick(white_turn=True)
    assert clock.snapshot().white_seconds == 180

    started = clock.signal_start()
    del started
    assert clock.snapshot().running
    assert not clock.snapshot().waiting_for_start


def test_pause_and_resume_stop_countdown():
    clock = ChessClock(mode="blitz_3_0", start_policy=AUTO_START)
    clock.pause()

    paused = clock.tick(white_turn=True)
    assert paused.paused
    assert paused.white_seconds == 180

    clock.resume()
    running = clock.tick(white_turn=True)
    assert running.running
    assert running.white_seconds == 179
