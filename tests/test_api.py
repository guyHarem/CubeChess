import unittest
from api.app import app, game_manager


class FakeTime:
    """Stands in for the manager's clock source so tests can let time pass instantly"""
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def tick(self, seconds):
        self.now += seconds


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.post('/api/game/new')

    def move(self, from_coord, to_coord):
        return self.client.post('/api/game/move', json={"from": from_coord, "to": to_coord})

    def test_new_game_state(self):
        data = self.client.get('/api/game/state').get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["current_player"], "white")
        self.assertEqual(data["status"], "ongoing")
        self.assertIsNone(data["pending_promotion"])
        self.assertEqual(data["board"]["[4, 0, 0]"], "King(white)")
        self.assertEqual(data["board"]["[2, 2, -1]"], "Rock")
        self.assertEqual(len(data["board"]), 32 + 16)

    def test_draw_by_repetition_is_reported(self):
        dance = [([1, 0, 0], [2, 2, 0]), ([1, 7, 0], [2, 5, 0]), ([2, 2, 0], [1, 0, 0]), ([2, 5, 0], [1, 7, 0])]
        data = self.client.get('/api/game/state').get_json()
        self.assertIsNone(data["draw_reason"])
        self.assertEqual((data["halfmove_clock"], data["move_limit"]), (0, 50))
        for from_coord, to_coord in dance + dance:
            data = self.move(from_coord, to_coord).get_json()
        self.assertEqual(data["status"], "draw")
        self.assertEqual(data["draw_reason"], "repetition")
        self.assertEqual(data["halfmove_clock"], 8)
        data = self.client.post('/api/game/undo').get_json()
        self.assertEqual((data["status"], data["draw_reason"]), ("ongoing", None))

    def test_new_game_options(self):
        data = self.client.post('/api/game/new', json={"rocks": False, "move_limit": 30}).get_json()
        self.assertEqual(len(data["board"]), 32)
        self.assertEqual(data["move_limit"], 30)
        self.assertEqual(self.client.post('/api/game/new', json={"move_limit": 0}).status_code, 400)
        self.assertEqual(self.client.post('/api/game/new', json={"move_limit": "x"}).status_code, 400)
        data = self.client.post('/api/game/new').get_json()
        self.assertEqual((len(data["board"]), data["move_limit"]), (48, 50))

    def test_history_marks_check(self):
        # 1. f3 e5 2. g4 Qh4: mate in 2D chess, but here the king can step up a layer, so only check
        for from_coord, to_coord in [([5, 1, 0], [5, 2, 0]), ([4, 6, 0], [4, 4, 0]),
                                     ([6, 1, 0], [6, 3, 0]), ([3, 7, 0], [7, 3, 0])]:
            data = self.move(from_coord, to_coord).get_json()
        self.assertEqual(data["status"], "check")
        self.assertEqual(data["move_history"][-1]["check"], "check")
        self.assertIsNone(data["move_history"][-2]["check"])

    def test_legal_moves(self):
        res = self.client.get('/api/game/legal-moves?from=[4,1,0]')
        self.assertEqual(res.status_code, 200)
        self.assertIn([4, 3, 0], res.get_json()["legal_moves"])

    def test_legal_moves_empty_for_opponent_piece(self):
        data = self.client.get('/api/game/legal-moves?from=[4,6,0]').get_json()
        self.assertEqual(data["legal_moves"], [])

    def test_legal_moves_rejects_bad_input(self):
        for bad in ("__import__('os').getcwd()", "[1,2]", "[9,9,9]", "[1,2,\"a\"]", "5"):
            res = self.client.get('/api/game/legal-moves', query_string={"from": bad})
            self.assertEqual(res.status_code, 400, bad)
        self.assertEqual(self.client.get('/api/game/legal-moves').status_code, 400)

    def test_move_and_undo(self):
        res = self.move([4, 1, 0], [4, 3, 0])
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["current_player"], "black")
        self.assertEqual(data["status"], "ongoing")
        self.assertEqual(data["board"]["[4, 3, 0]"], "Pawn(white)")
        self.assertEqual(data["move_history"][0]["to"], [4, 3, 0])

        data = self.client.post('/api/game/undo').get_json()
        self.assertEqual(data["current_player"], "white")
        self.assertEqual(data["board"]["[4, 1, 0]"], "Pawn(white)")
        self.assertEqual(self.client.post('/api/game/undo').status_code, 400)

    def test_illegal_move_returns_400_with_board(self):
        for res in (self.move([0, 0, 0], [0, 5, 0]),    # rook through its own pawn
                    self.move([4, 6, 0], [4, 4, 0]),    # black moving first
                    self.move([9, 9, 9], [0, 0, 0])):   # off the board
            self.assertEqual(res.status_code, 400)
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("error", data)
        self.assertIn("board", self.move([0, 0, 0], [0, 5, 0]).get_json())

    def test_move_rejects_bad_body(self):
        self.assertEqual(self.client.post('/api/game/move', json={"from": [4, 1, 0]}).status_code, 400)
        self.assertEqual(self.move("abc", [4, 3, 0]).status_code, 400)
        self.assertEqual(self.client.post('/api/game/move', data="nope").status_code, 400)

    def test_promote_without_pending_pawn(self):
        res = self.client.post('/api/game/promote', json={"coord": [4, 1, 0], "piece_type": "Queen"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/game/promote', json={"coord": [4, 1, 0], "piece_type": "King"})
        self.assertEqual(res.status_code, 400)


class TestSandboxApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, path, body):
        return self.client.post('/api/debug/' + path, json=body)

    def legal_moves(self, coord):
        res = self.client.get('/api/game/legal-moves', query_string={"from": str(coord)})
        return res.get_json()["legal_moves"]

    def test_single_piece_on_empty_board(self):
        data = self.post('setup', {"rocks": False, "pieces": [
            {"coord": [3, 3, 0], "type": "Rook", "color": "white"}]}).get_json()
        self.assertEqual(data["board"], {"[3, 3, 0]": "Rook(white)"})
        self.assertEqual(data["status"], "ongoing")
        # 7 along X + 7 along Y + 4 along Z, no king needed
        self.assertEqual(len(self.legal_moves([3, 3, 0])), 18)

    def test_place_capture_and_block(self):
        self.post('setup', {"rocks": False, "pieces": [
            {"coord": [3, 3, 0], "type": "Rook", "color": "white"}]})
        self.post('place', {"coord": [3, 5, 0], "type": "Pawn", "color": "black"})
        self.post('place', {"coord": [5, 3, 0], "type": "Pawn", "color": "white"})
        moves = self.legal_moves([3, 3, 0])
        self.assertIn([3, 5, 0], moves)     # capture
        self.assertNotIn([3, 6, 0], moves)  # behind the enemy pawn
        self.assertNotIn([5, 3, 0], moves)  # own pawn
        data = self.client.post('/api/game/move', json={"from": [3, 3, 0], "to": [3, 5, 0]}).get_json()
        self.assertEqual(data["move_history"][-1]["captured_piece"], "Pawn(black)")

    def test_remove_and_turn(self):
        self.post('setup', {"rocks": False, "pieces": [
            {"coord": [3, 3, 0], "type": "Knight", "color": "black"},
            {"coord": [0, 0, 0], "type": "Knight", "color": "white"}]})
        self.assertEqual(self.legal_moves([3, 3, 0]), [])  # white to move
        data = self.post('turn', {"player": "black"}).get_json()
        self.assertEqual(data["current_player"], "black")
        self.assertEqual(len(self.legal_moves([3, 3, 0])), 24)
        data = self.post('remove', {"coord": [0, 0, 0]}).get_json()
        self.assertNotIn("[0, 0, 0]", data["board"])

    def test_rocks_toggle(self):
        self.post('setup', {"pieces": []})
        self.assertEqual(len(self.client.get('/api/game/state').get_json()["board"]), 16)
        self.assertEqual(self.post('rocks', {"enabled": False}).get_json()["board"], {})
        self.assertEqual(len(self.post('rocks', {"enabled": True}).get_json()["board"]), 16)

    def test_placed_pieces_only_keep_rights_on_home_squares(self):
        self.post('setup', {"rocks": False, "pieces": [
            {"coord": [0, 1, 0], "type": "Pawn", "color": "white"},
            {"coord": [5, 3, 0], "type": "Pawn", "color": "white"},
            {"coord": [4, 3, 1], "type": "King", "color": "white"},
            {"coord": [7, 3, 1], "type": "Rook", "color": "white"}]})
        self.assertIn([0, 3, 0], self.legal_moves([0, 1, 0]))
        self.assertNotIn([5, 5, 0], self.legal_moves([5, 3, 0]))
        self.assertNotIn([6, 3, 1], self.legal_moves([4, 3, 1]))  # no castling

    def test_bad_input(self):
        self.assertEqual(self.post('place', {"coord": [9, 9, 9], "type": "Rook", "color": "white"}).status_code, 400)
        self.assertEqual(self.post('place', {"coord": [1, 1, 0], "type": "Dragon", "color": "white"}).status_code, 400)
        self.assertEqual(self.post('place', {"coord": [1, 1, 0], "type": "Rook", "color": "red"}).status_code, 400)
        self.assertEqual(self.post('setup', {"pieces": [{"coord": [1, 1]}]}).status_code, 400)
        self.assertEqual(self.post('turn', {"player": "green"}).status_code, 400)


class TestClockAndResults(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.time = FakeTime()
        game_manager._now = self.time

    def tearDown(self):
        import time
        game_manager._now = time.monotonic
        self.client.post('/api/game/new')

    def new(self, **body):
        return self.client.post('/api/game/new', json=body).get_json()

    def move(self, from_coord, to_coord):
        return self.client.post('/api/game/move', json={"from": from_coord, "to": to_coord})

    def state(self):
        return self.client.get('/api/game/state').get_json()

    def test_no_clock_by_default(self):
        data = self.new()
        self.assertIsNone(data["clock"])
        self.assertIsNone(data["winner"])
        self.assertEqual(data["board_size"], {"size": 8, "z_min": -2, "z_max": 2})

    def test_clock_runs_only_for_the_player_to_move(self):
        data = self.new(clock={"initial": 300, "increment": 0})
        self.assertEqual(data["clock"], {"initial": 300, "increment": 0, "white": 300, "black": 300, "running": None})
        self.time.tick(40)  # nothing runs before White's first move
        data = self.move([4, 1, 0], [4, 3, 0]).get_json()
        self.assertEqual((data["clock"]["white"], data["clock"]["running"]), (300, "black"))
        self.time.tick(12)
        self.assertEqual(self.state()["clock"]["black"], 288)
        data = self.move([4, 6, 0], [4, 4, 0]).get_json()
        self.assertEqual((data["clock"]["black"], data["clock"]["running"]), (288, "white"))
        self.time.tick(7)
        self.assertEqual(self.state()["clock"]["white"], 293)
        self.assertEqual(self.state()["clock"]["black"], 288)

    def test_increment_is_added_after_each_timed_move(self):
        self.new(clock={"initial": 60, "increment": 5})
        self.move([4, 1, 0], [4, 3, 0])          # free first move, no increment
        self.time.tick(10)
        data = self.move([4, 6, 0], [4, 4, 0]).get_json()
        self.assertEqual(data["clock"]["black"], 55)   # 60 - 10 + 5
        self.time.tick(3)
        data = self.move([3, 1, 0], [3, 3, 0]).get_json()
        self.assertEqual(data["clock"]["white"], 62)   # 60 - 3 + 5

    def test_running_out_of_time_loses(self):
        self.new(clock={"initial": 30, "increment": 0})
        self.move([4, 1, 0], [4, 3, 0])
        self.time.tick(31)
        data = self.state()
        self.assertEqual((data["status"], data["winner"]), ("timeout", "white"))
        self.assertEqual((data["clock"]["black"], data["clock"]["running"]), (0, None))
        res = self.move([4, 6, 0], [4, 4, 0])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"], "The game is over")

    def test_undo_puts_the_time_back(self):
        self.new(clock={"initial": 100, "increment": 0})
        self.move([4, 1, 0], [4, 3, 0])
        self.time.tick(20)
        self.move([4, 6, 0], [4, 4, 0])           # black now has 80
        self.time.tick(5)
        data = self.client.post('/api/game/undo').get_json()
        self.assertEqual(data["current_player"], "black")
        self.assertEqual((data["clock"]["black"], data["clock"]["white"], data["clock"]["running"]), (80, 100, "black"))
        data = self.client.post('/api/game/undo').get_json()
        self.assertEqual((data["clock"]["black"], data["clock"]["running"]), (100, None))

    def test_bad_clock_settings(self):
        for clock in ({"initial": 5}, {"initial": 60, "increment": -1}, {"initial": "x"}, "fast", {"increment": 5}):
            self.assertEqual(self.client.post('/api/game/new', json={"clock": clock}).status_code, 400, clock)

    def test_resign(self):
        self.new(clock={"initial": 60, "increment": 0})
        self.move([4, 1, 0], [4, 3, 0])
        data = self.client.post('/api/game/resign').get_json()   # black is to move
        self.assertEqual((data["status"], data["winner"]), ("resigned", "white"))
        self.assertIsNone(data["clock"]["running"])
        self.assertEqual(self.move([4, 6, 0], [4, 4, 0]).status_code, 400)
        self.assertEqual(self.client.post('/api/game/resign').status_code, 400)
        self.assertEqual(self.client.post('/api/game/draw').status_code, 400)
        # Taking the last move back reopens the game
        data = self.client.post('/api/game/undo').get_json()
        self.assertEqual((data["status"], data["winner"]), ("ongoing", None))

    def test_resign_for_a_named_color(self):
        self.new()
        data = self.client.post('/api/game/resign', json={"color": "white"}).get_json()
        self.assertEqual((data["status"], data["winner"]), ("resigned", "black"))
        self.assertEqual(self.client.post('/api/game/resign', json={"color": "red"}).status_code, 400)

    def test_agreed_draw(self):
        self.new()
        data = self.client.post('/api/game/draw').get_json()
        self.assertEqual((data["status"], data["winner"], data["draw_reason"]), ("agreed_draw", None, None))
        self.assertEqual(self.move([4, 1, 0], [4, 3, 0]).status_code, 400)
        self.assertEqual(self.new()["status"], "ongoing")


class TestSmallBoardApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def tearDown(self):
        self.client.post('/api/game/new')

    def test_lesson_board(self):
        data = self.client.post('/api/debug/setup', json={"size": 5, "z_min": -1, "z_max": 1, "pieces": [
            {"coord": [2, 2, 0], "type": "Knight", "color": "white"},
            {"coord": [0, 0, -1], "type": "Rock"}]}).get_json()
        self.assertEqual(data["board_size"], {"size": 5, "z_min": -1, "z_max": 1})
        self.assertEqual(data["board"], {"[2, 2, 0]": "Knight(white)", "[0, 0, -1]": "Rock"})
        moves = self.client.get('/api/game/legal-moves', query_string={"from": "[2,2,0]"}).get_json()["legal_moves"]
        self.assertEqual(len(moves), 16)
        res = self.client.post('/api/game/move', json={"from": [2, 2, 0], "to": [2, 4, 1]})
        self.assertEqual(res.status_code, 200)
        # Off the small board
        self.assertEqual(self.client.post('/api/game/move', json={"from": [2, 4, 1], "to": [3, 6, 1]}).status_code, 400)

    def test_bad_board_sizes(self):
        for body in ({"size": 3}, {"size": 9}, {"z_min": 1}, {"z_max": 3}, {"size": "5"},
                     {"size": 5, "z_min": -1, "z_max": 1, "pieces": [{"coord": [5, 0, 0], "type": "Rook", "color": "white"}]}):
            self.assertEqual(self.client.post('/api/debug/setup', json=body).status_code, 400, body)


class TestPracticeGame(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.post('/api/game/new')

    def test_practice_game_is_separate_from_the_main_game(self):
        self.client.post('/api/game/move', json={"from": [4, 1, 0], "to": [4, 3, 0]})
        data = self.client.post('/api/debug/setup?game=practice', json={"size": 5, "z_min": -1, "z_max": 1, "pieces": [
            {"coord": [2, 2, 0], "type": "Knight", "color": "white"}]}).get_json()
        self.assertEqual(data["board_size"]["size"], 5)
        moves = self.client.get('/api/game/legal-moves', query_string={"from": "[2,2,0]", "game": "practice"}).get_json()
        self.assertEqual(len(moves["legal_moves"]), 16)
        self.client.post('/api/game/move?game=practice', json={"from": [2, 2, 0], "to": [2, 4, 1]})

        main = self.client.get('/api/game/state').get_json()
        self.assertEqual(main["board_size"]["size"], 8)
        self.assertEqual(len(main["move_history"]), 1)
        self.assertEqual(main["board"]["[4, 3, 0]"], "Pawn(white)")
        practice = self.client.get('/api/game/state?game=practice').get_json()
        self.assertEqual(practice["board"], {"[2, 4, 1]": "Knight(white)"})

    def test_unknown_game_is_rejected(self):
        self.assertEqual(self.client.get('/api/game/state?game=other').status_code, 400)


if __name__ == '__main__':
    unittest.main()
