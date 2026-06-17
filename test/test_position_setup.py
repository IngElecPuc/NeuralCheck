from neuralcheck.application.game_controller import GameController


def test_manual_position_requires_exactly_one_king_per_color():
    controller = GameController()

    result = controller.apply_manual_position(
        {
            "e1": "white king",
            "a1": "white rook",
        },
        white_turn=True,
    )

    assert result.valid is False
    assert "Debe existir exactamente un rey negro" in result.errors


def test_manual_position_rejects_unpromoted_pawn_on_last_rank():
    controller = GameController()

    result = controller.apply_manual_position(
        {
            "e1": "white king",
            "e8": "black king",
            "a8": "white pawn",
        },
        white_turn=True,
    )

    assert result.valid is False
    assert "Peón en fila de promoción sin promover: a8" in result.errors


def test_manual_position_applies_valid_board_and_clears_history():
    controller = GameController()
    controller.click_square("e2")
    controller.click_square("e4")
    assert controller.history_rows()

    result = controller.apply_manual_position(
        {
            "e1": "white king",
            "e8": "black king",
            "d4": "white queen",
        },
        white_turn=False,
    )

    assert result.valid is True
    assert controller.piece_at("d4") == "white queen"
    assert controller.active_color == "black"
    assert controller.history_rows() == []


def test_fen_position_applies_active_color():
    controller = GameController()

    result = controller.apply_fen_position("4k3/8/8/8/3Q4/8/8/4K3 b - - 0 1")

    assert result.valid is True
    assert controller.piece_at("d4") == "white queen"
    assert controller.active_color == "black"


def test_pointer_marks_last_executed_move_not_next_player():
    controller = GameController()

    controller.click_square("e2")
    controller.click_square("e4")
    rows = controller.history_rows()
    assert rows[0].white_pointer is True
    assert rows[0].black_pointer is False

    controller.click_square("e7")
    controller.click_square("e5")
    rows = controller.history_rows()
    assert rows[0].white_pointer is False
    assert rows[0].black_pointer is True


def test_history_navigation_can_jump_to_specific_half_move():
    controller = GameController()
    controller.click_square("e2")
    controller.click_square("e4")
    controller.click_square("e7")
    controller.click_square("e5")
    controller.click_square("g1")
    controller.click_square("f3")

    assert controller.jump_to_move(0, True) is True
    assert controller.piece_at("e4") == "white pawn"
    assert controller.piece_at("e5").startswith("Empty")

    assert controller.jump_to_move(0, False) is True
    assert controller.piece_at("e5") == "black pawn"


def test_next_step_jumps_fen_and_play_replays_next_move():
    controller = GameController()
    controller.click_square("e2")
    controller.click_square("e4")
    controller.click_square("e7")
    controller.click_square("e5")

    controller.go_to_first()
    assert controller.piece_at("e2") == "white pawn"
    assert controller.piece_at("e4").startswith("Empty")

    assert controller.next_step() is True
    assert controller.piece_at("e4") == "white pawn"

    controller.go_to_first()
    replayed = controller.execute_current_replay_move()
    assert replayed.moved is True
    assert replayed.movement == "e4"
    assert controller.piece_at("e4") == "white pawn"


def test_legacy_pre_move_fen_history_next_step_stays_aligned(tmp_path):
    import yaml

    legacy_history = [
        [
            ["e4", "c6"],
            [
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            ],
        ],
        [
            ["Bc4", "d5"],
            [
                "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "rnbqkbnr/pp1ppppp/2p5/8/2B1P3/8/PPPP1PPP/RNBQK1NR b KQkq - 1 2",
            ],
        ],
    ]
    game_file = tmp_path / "legacy_game.yaml"
    game_file.write_text(yaml.safe_dump(legacy_history, allow_unicode=True), encoding="utf-8")

    controller = GameController()
    controller.load_game(game_file)

    assert controller.piece_at("e2") == "white pawn"
    assert controller.piece_at("e4").startswith("Empty")

    assert controller.next_step() is True
    rows = controller.history_rows()
    assert rows[0].white_pointer is True
    assert rows[0].black_pointer is False
    assert controller.piece_at("e2").startswith("Empty")
    assert controller.piece_at("e4") == "white pawn"
    assert controller.piece_at("c7") == "black pawn"
    assert controller.piece_at("c6").startswith("Empty")

    assert controller.next_step() is True
    rows = controller.history_rows()
    assert rows[0].white_pointer is False
    assert rows[0].black_pointer is True
    assert controller.piece_at("c7").startswith("Empty")
    assert controller.piece_at("c6") == "black pawn"

    assert controller.jump_to_move(1, True) is True
    rows = controller.history_rows()
    assert rows[1].white_pointer is True
    assert rows[1].black_pointer is False
    assert controller.piece_at("c4") == "white bishop"
    assert controller.piece_at("f1").startswith("Empty")


def test_position_editor_palette_is_visual_4x4_grid():
    from neuralcheck.ui_position_editor import EMPTY_SQUARE, position_editor_palette_options

    palette = position_editor_palette_options()
    assert len(palette) == 16
    assert palette.count(EMPTY_SQUARE) == 4
    assert set(palette) >= {
        "white king",
        "white queen",
        "white rook",
        "white bishop",
        "white knight",
        "white pawn",
        "black king",
        "black queen",
        "black rook",
        "black bishop",
        "black knight",
        "black pawn",
    }
