from neuralcheck.application.clock import BLACK_SIGNAL_START, CORRESPONDENCE, ChessClock


def main() -> None:
    bullet = ChessClock(mode="bullet_1_1")
    bullet.tick(white_turn=True)
    assert bullet.snapshot().white_seconds == 59
    bullet.on_move_completed(white_player=True)
    assert bullet.snapshot().white_seconds == 60

    signal_clock = ChessClock(mode="blitz_3_0", start_policy=BLACK_SIGNAL_START)
    assert signal_clock.snapshot().waiting_for_start
    signal_clock.tick(white_turn=True)
    assert signal_clock.snapshot().white_seconds == 180
    signal_clock.signal_start()
    signal_clock.tick(white_turn=True)
    assert signal_clock.snapshot().white_seconds == 179

    signal_clock.pause()
    signal_clock.tick(white_turn=False)
    assert signal_clock.snapshot().black_seconds == 180
    signal_clock.resume()
    signal_clock.tick(white_turn=False)
    assert signal_clock.snapshot().black_seconds == 179

    fide = ChessClock(mode="fide_90_40_30_30")
    for _ in range(40):
        fide.on_move_completed(white_player=True)
    assert fide.snapshot().white_seconds == 5400 + 1200 + 1800

    fide.set_time_control(CORRESPONDENCE)
    assert not fide.snapshot().visible

    print("Clock controls smoke passed")


if __name__ == "__main__":
    main()
