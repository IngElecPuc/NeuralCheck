from neuralcheck.application.game_controller import GameController


def test_controller_exposes_active_player_selection_contract():
    controller = GameController()

    assert controller.active_color == "white"
    assert controller.can_select("e2") is True
    assert controller.can_select("e7") is False
    assert controller.legal_targets("e2") == ["e3", "e4"]


def test_controller_click_selects_and_moves_without_ui_accessing_engine_internals():
    controller = GameController()

    selected = controller.click_square("e2")
    assert selected.selected is True
    assert selected.origin == "e2"
    assert selected.legal_targets == ("e3", "e4")
    assert controller.selected == ("e2", "white pawn")

    moved = controller.click_square("e4")
    assert moved.moved is True
    assert moved.movement == "e4"
    assert controller.selected is None
    assert controller.piece_at("e2").startswith("Empty")
    assert controller.piece_at("e4") == "white pawn"
    assert controller.active_color == "black"


def test_controller_rejects_wrong_turn_selection():
    controller = GameController()

    result = controller.click_square("e7")

    assert result.moved is False
    assert result.invalid_reason == "wrong_turn"
    assert controller.selected is None


def test_controller_history_rows_hide_chessboard_history_shape():
    controller = GameController()
    controller.click_square("e2")
    controller.click_square("e4")

    rows = controller.history_rows()

    assert len(rows) == 1
    assert rows[0].turn_number == 1
    assert rows[0].white_move == "e4"
    assert rows[0].black_move == ""

def test_controller_replays_capture_promotion_with_check_suffix():
    controller = GameController()
    moves = [
        "d4",
        "d5",
        "c4",
        "e5",
        "dxe5",
        "d4",
        "e3",
        "Bb4+",
        "Bd2",
        "dxe3",
        "Bxb4",
        "exf2+",
        "Ke2",
        "fxg1=N+",
    ]

    result = controller.load_line_from_initial(moves)

    assert result.valid is True
    assert result.errors == ()
    assert controller.piece_at("g1") == "black knight"
    assert controller.active_color == "white"
    assert controller.current_fen(include_state=True).startswith(
        "rnbqk1nr/ppp2ppp/8/4P3/1BP5/8/PP2K1PP/RN1Q1BnR w"
    )

