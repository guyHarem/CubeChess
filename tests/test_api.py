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


if __name__ == '__main__':
    unittest.main()
