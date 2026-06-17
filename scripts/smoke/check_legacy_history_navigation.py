from pathlib import Path
import tempfile

import yaml

from neuralcheck.application.game_controller import GameController


LEGACY_HISTORY = [
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


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        game_path = Path(tmpdir) / "legacy_game.yaml"
        game_path.write_text(yaml.safe_dump(LEGACY_HISTORY, allow_unicode=True), encoding="utf-8")

        controller = GameController()
        controller.load_game(game_path)
        if not controller.next_step():
            raise AssertionError("Could not navigate to first white move")
        if controller.piece_at("e4") != "white pawn":
            raise AssertionError("Legacy white half-move navigation is not aligned")

        if not controller.next_step():
            raise AssertionError("Could not navigate to first black move")
        if controller.piece_at("c6") != "black pawn":
            raise AssertionError("Legacy black half-move navigation is not aligned")

    print("Legacy history navigation smoke passed")


if __name__ == "__main__":
    main()
