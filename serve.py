"""
Run the game for real visitors: one program serving the built pages and the API.

    npm --prefix cubechess-frontend run build     # once, and after every change to the pages
    venv/bin/python serve.py                       # then open http://localhost:8000

Settings (environment variables):
    PORT                    port to listen on (default 8000)
    HOST                    address to listen on (default 0.0.0.0: reachable from other machines)
    CUBECHESS_THINKERS      computer moves thought about at the same time, one CPU core each
                            (default: the number of cores minus one, at most 4)
    CUBECHESS_TRUST_PROXY   set to 0 when no proxy stands in front of this server; otherwise
                            the visitor's address is read from the proxy's X-Forwarded-For

The server is a single process on purpose: games live in its memory, so two processes would
each have their own set. Restarting it ends the games in progress.
"""
import os

os.environ["CUBECHESS_ENV"] = "production"   # must be set before api.app is imported

if __name__ == "__main__":
    from waitress import serve

    from api.app import app, rooms
    from api.thinker import ProcessThinker, default_workers

    if not os.path.isfile(os.path.join(app.config["DIST"], "index.html")):
        raise SystemExit("The pages are not built yet. Run: npm --prefix cubechess-frontend run build")

    workers = int(os.environ.get("CUBECHESS_THINKERS", default_workers()))
    thinker = ProcessThinker(workers=workers)
    rooms.set_thinker(thinker)
    thinker.warm_up()

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    print(f"Serving on http://{host}:{port} with {workers} computer thinker(s)", flush=True)
    # Plenty of threads: a computer move holds one for seconds while the pages keep asking for news
    serve(app, host=host, port=port, threads=32, ident=None)
