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
