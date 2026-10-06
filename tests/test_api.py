import unittest
from api.app import app


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


if __name__ == '__main__':
    unittest.main()
