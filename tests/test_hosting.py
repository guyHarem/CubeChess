"""
Hosted mode: what changes when the game faces the internet (CUBECHESS_ENV=production, serve.py).
On a developer's machine none of these restrictions apply, which the other test files rely on.
"""
import os
import subprocess
import sys
import tempfile
import unittest

from api import app as app_module
from api.app import app, game_manager, rooms
from api.limits import Limiter, Slots
from api.thinker import Busy, ProcessThinker, think

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestLimits(unittest.TestCase):
    def test_limiter_counts_per_visitor_and_forgets_with_time(self):
        clock = FakeTime()
        limiter = Limiter(3, 60, now=clock)
        self.assertEqual([limiter.allow("ann") for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow("bob"))          # someone else is not affected
        clock.now = 59
        self.assertFalse(limiter.allow("ann"))
        clock.now = 61                                  # the first three have aged out
        self.assertTrue(limiter.allow("ann"))

    def test_slots_limit_what_runs_at_the_same_time(self):
        slots = Slots(2)
        self.assertEqual([slots.take("ann"), slots.take("ann"), slots.take("ann")], [True, True, False])
        self.assertTrue(slots.take("bob"))
        slots.give_back("ann")
        self.assertTrue(slots.take("ann"))


class HostedTestCase(unittest.TestCase):
    def setUp(self):
        app.config["PRODUCTION"] = True
        self.saved_limits = dict(app_module.limits)
        self.client = app.test_client()

    def tearDown(self):
        app.config["PRODUCTION"] = False
        app_module.limits.update(self.saved_limits)
        for room_id in [room_id for room_id in rooms._rooms if room_id not in ("main", "practice")]:
            del rooms._rooms[room_id]

    def open(self, **body):
        return self.client.post('/api/games', json=body)

    def room(self, kind="local", **body):
        return self.open(kind=kind, **body).get_json()["game_id"]


class TestLockedDown(HostedTestCase):
    def test_the_shared_test_rooms_are_closed(self):
        for query in ("", "?game=main", "?game=practice"):
            res = self.client.get('/api/game/state' + query)
            self.assertEqual((res.status_code, res.get_json()["gone"]), (404, True), query)
        self.assertEqual(self.client.post('/api/game/move', json={"from": [4, 1, 0], "to": [4, 3, 0]}).status_code, 404)

    def test_games_of_your_own_work_as_usual(self):
        game = self.room()
        res = self.client.post(f'/api/game/move?game={game}', json={"from": [4, 1, 0], "to": [4, 3, 0]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.post(f'/api/game/undo?game={game}').status_code, 200)

    def test_positions_can_only_be_edited_on_practice_boards(self):
        setup = {"size": 5, "z_min": -1, "z_max": 1, "pieces": [{"coord": [2, 2, 0], "type": "Knight", "color": "white"}]}
        for kind, extra in (("local", {}), ("computer", {"computer": {"color": "black", "level": "easy"}})):
            game = self.room(kind, **extra)
            for path in ("setup", "place", "remove", "turn", "rocks"):
                res = self.client.post(f'/api/debug/{path}?game={game}', json=setup)
                self.assertEqual((res.status_code, res.get_json()["error"]), (400, "That is not available here"), (kind, path))
        practice = self.room("practice")
        res = self.client.post(f'/api/debug/setup?game={practice}', json=setup)
        self.assertEqual((res.status_code, res.get_json()["board_size"]["size"]), (200, 5))

    def test_health_check(self):
        self.assertEqual(self.client.get('/api/health').get_json(), {"success": True})

    def test_nothing_is_locked_on_a_developers_machine(self):
        app.config["PRODUCTION"] = False
        self.assertEqual(self.client.get('/api/game/state').status_code, 200)
        self.assertEqual(self.client.post('/api/debug/turn', json={"player": "white"}).status_code, 200)
        self.client.post('/api/game/new')

    def test_oversized_requests_are_refused(self):
        res = self.client.post('/api/games', data=b'{"kind": "local", "x": "' + b"a" * 100_000 + b'"}',
                               content_type="application/json")
        self.assertNotEqual(res.status_code, 200)


class TestVisitorLimits(HostedTestCase):
    def test_too_many_new_games(self):
        app_module.limits["new_games"] = Limiter(2, 60)
        self.assertEqual([self.open(kind="local").status_code for _ in range(3)], [200, 200, 429])
        refused = self.open(kind="local").get_json()
        self.assertEqual((refused["success"], refused["slow_down"]), (False, True))

    def test_too_many_requests_of_any_kind(self):
        game = self.room()
        app_module.limits["requests"] = Limiter(3, 60)
        codes = [self.client.get(f'/api/game/state?game={game}').status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])
        # The pages themselves are not counted
        with self.client.get('/') as page:
            self.assertNotEqual(page.status_code, 429)

    def test_computer_moves_are_limited_and_counted_back(self):
        game = self.room("computer", computer={"color": "white", "level": "easy"})
        app_module.limits["thinking"] = Slots(0)
        self.assertEqual(self.client.post(f'/api/game/computer-move?game={game}').status_code, 429)
        app_module.limits["thinking"] = Slots(1)
        for _ in range(2):    # the slot is given back after each move, so one at a time is enough
            reply = self.client.post(f'/api/game/computer-move?game={game}')
            self.assertEqual(reply.status_code, 200)
            self.client.post(f'/api/game/undo?game={game}')

    def test_no_limits_on_a_developers_machine(self):
        app.config["PRODUCTION"] = False
        app_module.limits["new_games"] = Limiter(1, 60)
        self.assertEqual([self.open(kind="local").status_code for _ in range(3)], [200, 200, 200])


class TestBusyComputer(unittest.TestCase):
    def tearDown(self):
        game_manager._think = think
        app.test_client().post('/api/game/new')

    def test_a_full_line_turns_requests_away_without_harm(self):
        client = app.test_client()
        client.post('/api/game/new', json={"computer": {"color": "white", "level": "easy"}})

        def busy(game, level, seconds):
            raise Busy("The computer is busy with other games. It will move in a moment.")

        game_manager._think = busy
        res = client.post('/api/game/computer-move')
        data = res.get_json()
        self.assertEqual((res.status_code, data["success"], data["busy"], data["move_history"]), (400, False, True, []))
        game_manager._think = think              # a worker is free again: the same request now succeeds
        self.assertTrue(client.post('/api/game/computer-move').get_json()["success"])

    def test_the_thinker_has_a_bounded_line(self):
        thinker = ProcessThinker(workers=1, waiting=1)
        self.assertTrue(thinker._places.acquire(blocking=False))   # one thinking
        self.assertTrue(thinker._places.acquire(blocking=False))   # one waiting
        with self.assertRaises(Busy):
            thinker(None, "easy", None)
        thinker._places.release()
        thinker._places.release()


class TestPages(unittest.TestCase):
    """The server hands out the built pages itself, so one program is all a host needs"""

    def setUp(self):
        self.saved = app.config["DIST"]
        self.folder = tempfile.TemporaryDirectory()
        app.config["DIST"] = self.folder.name
        os.mkdir(os.path.join(self.folder.name, "assets"))
        for name, text in (("index.html", "<!doctype html><title>game</title>"), ("favicon.svg", "<svg/>"),
                           (os.path.join("assets", "index-abc123.js"), "console.log(1)")):
            with open(os.path.join(self.folder.name, name), "w") as f:
                f.write(text)
        self.client = app.test_client()

    def tearDown(self):
        app.config["DIST"] = self.saved
        self.folder.cleanup()

    def test_front_page(self):
        with self.client.get('/') as res:
            self.assertEqual((res.status_code, res.mimetype), (200, "text/html"))
            self.assertIn(b"<title>game</title>", res.data)
            self.assertEqual(res.headers["Cache-Control"], "no-cache")   # always the newest build

    def test_built_files_are_cached_for_good(self):
        with self.client.get('/assets/index-abc123.js') as res:
            self.assertEqual(res.status_code, 200)
            self.assertIn("immutable", res.headers["Cache-Control"])
            self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
        with self.client.get('/favicon.svg') as res:
            self.assertEqual(res.status_code, 200)

    def test_nothing_outside_the_build_is_served(self):
        for path in ('/missing.js', '/assets/../../api/app.py', '/..%2f..%2frequirements.txt', '/%2e%2e/serve.py'):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_unknown_api_paths_are_not_pages(self):
        res = self.client.get('/api/nope')
        self.assertEqual((res.status_code, res.is_json), (404, True))

    def test_a_missing_build_says_so(self):
        app.config["DIST"] = os.path.join(self.folder.name, "nowhere")
        res = self.client.get('/')
        self.assertEqual(res.status_code, 404)
        self.assertIn("not built", res.get_json()["error"])


class TestStartUp(unittest.TestCase):
    """Things decided when the program starts, so they are checked in a fresh process"""

    def run_python(self, code, **environment):
        env = {**os.environ, **environment}
        env.pop("CUBECHESS_ENV", None) if "CUBECHESS_ENV" not in environment else None
        return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)

    CROSS_SITE = ("from api.app import app\n"
                  "r = app.test_client().get('/api/health', headers={'Origin': 'https://elsewhere.example'})\n"
                  "print('allowed' if 'Access-Control-Allow-Origin' in r.headers else 'not allowed')")

    def test_other_sites_cannot_call_the_hosted_api(self):
        self.assertEqual(self.run_python(self.CROSS_SITE, CUBECHESS_ENV="production").stdout.strip(), "not allowed")
        # In development the pages come from another port, so there it is allowed
        self.assertEqual(self.run_python(self.CROSS_SITE).stdout.strip(), "allowed")

    def test_the_development_server_refuses_to_run_hosted(self):
        done = subprocess.run([sys.executable, "api/app.py"], cwd=ROOT, capture_output=True, text=True, timeout=60,
                              env={**os.environ, "CUBECHESS_ENV": "production"})
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("serve.py", done.stderr)

    def test_visitors_behind_the_hosts_proxy_are_told_apart(self):
        code = ("from api import app as m\n"
                "from api.limits import Limiter\n"
                "m.limits['new_games'] = Limiter(1, 60)\n"
                "c = m.app.test_client()\n"
                "post = lambda ip: c.post('/api/games', json={'kind': 'local'}, headers={'X-Forwarded-For': ip}).status_code\n"
                "print(post('203.0.113.1'), post('203.0.113.1'), post('203.0.113.2'))")
        self.assertEqual(self.run_python(code, CUBECHESS_ENV="production").stdout.strip(), "200 429 200")
        # Told not to trust a proxy, everyone arriving through one address counts as one visitor
        self.assertEqual(self.run_python(code, CUBECHESS_ENV="production", CUBECHESS_TRUST_PROXY="0").stdout.strip(),
                         "200 429 429")


if __name__ == '__main__':
    unittest.main()
