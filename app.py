# app.py
import os
import time
import logging
import random
from heapq import heappop, heappush
from itertools import count

from flask import (
    Flask, render_template_string, jsonify, request, url_for,
    session, send_from_directory
)
from werkzeug.utils import secure_filename
from PIL import Image

# -----------------------------------------------------------------------------
# App / config
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")  # set SECRET_KEY in Render
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB uploads
UPLOAD_FOLDER = os.path.join(app.root_path, "static")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
Image.MAX_IMAGE_PIXELS = 10_000_000  # guard against decompression bombs
START_TS = time.time()

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}'
)
app.logger.info("8-puzzle service starting")

# -----------------------------------------------------------------------------
# Session helpers (multi-user safe)
# -----------------------------------------------------------------------------
def _get_state(): return session.get("state", [])
def _set_state(s): session["state"] = s

def _get_moves(): return session.get("moves", 0)
def _set_moves(n): session["moves"] = n

def _get_tiles(): return session.get("tiles", [])
def _set_tiles(t): session["tiles"] = t

def _clear_session():
    for k in ("state", "moves", "tiles"):
        session.pop(k, None)

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def is_solvable(state):
    inv = 0
    for i in range(len(state)):
        for j in range(i + 1, len(state)):
            if state[i] and state[j] and state[i] > state[j]:
                inv += 1
    return inv % 2 == 0

def shuffle_tiles(seed: int | None = None):
    rng = random.Random(seed)
    state = list(range(1, 9)) + [0]
    while True:
        rng.shuffle(state)
        if is_solvable(state):
            return state

def split_image(img: Image.Image, upload_folder: str):
    # crop to square center, then resize to 300x300
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((300, 300))

    tile_size = img.size[0] // 3
    urls = []
    for i in range(3):
        for j in range(3):
            L = j * tile_size
            U = i * tile_size
            tile = img.crop((L, U, L + tile_size, U + tile_size))
            path = os.path.join(upload_folder, f"tile_{i}_{j}.png")
            tile.save(path)
            urls.append(url_for("static", filename=f"tile_{i}_{j}.png"))
    return urls

# -----------------------------------------------------------------------------
# Heuristics + A* with path
# -----------------------------------------------------------------------------
def h_manhattan(s):
    d = 0
    for i, v in enumerate(s):
        if v == 0:
            continue
        tx, ty = divmod(v - 1, 3)
        x, y = divmod(i, 3)
        d += abs(tx - x) + abs(ty - y)
    return d

def h_misplaced(s):
    return sum(1 for i, v in enumerate(s) if v and v != i + 1)

def h_linear_conflict(s):
    def conflicts(line):
        vals = [v for v in line if v]
        inv = 0
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                if vals[i] > vals[j]:
                    inv += 1
        return inv

    man = h_manhattan(s)
    rows = sum(conflicts([s[r*3 + c] for c in range(3) if (s[r*3 + c] - 1) // 3 == r]) for r in range(3))
    cols = sum(conflicts([s[r*3 + c] for r in range(3) if (s[r*3 + c] - 1) % 3 == c]) for c in range(3))
    return man + 2 * (rows + cols)

HEURISTICS = {"manhattan": h_manhattan, "misplaced": h_misplaced, "linear": h_linear_conflict}

def a_star_with_path(initial_state, heuristic="manhattan"):
    h = HEURISTICS.get(heuristic, h_manhattan)
    start = tuple(initial_state)
    goal = tuple(range(1, 9)) + (0,)
    parent = {start: None}
    g = {start: 0}
    f = {start: h(start)}
    pq = []
    heappush(pq, (f[start], next(count()), start))
    while pq:
        _, __, cur = heappop(pq)
        if cur == goal:
            path = []
            while parent[cur] is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return len(path), path
        zi = cur.index(0)
        x, y = divmod(zi, 3)
        nbrs = []
        if x > 0: nbrs.append(zi - 3)
        if x < 2: nbrs.append(zi + 3)
        if y > 0: nbrs.append(zi - 1)
        if y < 2: nbrs.append(zi + 1)
        for ni in nbrs:
            nxt = list(cur)
            nxt[zi], nxt[ni] = nxt[ni], nxt[zi]
            nxt = tuple(nxt)
            ng = g[cur] + 1
            if nxt not in g or ng < g[nxt]:
                parent[nxt] = cur
                g[nxt] = ng
                f[nxt] = ng + h(nxt)
                heappush(pq, (f[nxt], next(count()), nxt))
    return -1, []

# -----------------------------------------------------------------------------
# Security headers (allow inline JS so the buttons work)
# -----------------------------------------------------------------------------
@app.after_request
def add_security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline';"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/favicon.ico")
def favicon():
    icon = os.path.join(UPLOAD_FOLDER, "favicon.ico")
    if os.path.exists(icon):
        return send_from_directory(UPLOAD_FOLDER, "favicon.ico", mimetype="image/x-icon")
    return ("", 204)

@app.route("/", methods=["GET", "POST"])
def home():
    # On plain GET (no shared state), clear session so a refresh starts from zero
    if request.method == "GET" and not request.args.get("state"):
        _clear_session()

    if request.method == "POST":
        if "file" not in request.files:
            return "No file part", 400
        f = request.files["file"]
        if f.filename == "":
            return "No selected file", 400
        if not allowed_file(f.filename):
            return "Invalid file type. Please upload PNG/JPG/JPEG/WEBP.", 400

        filename = secure_filename(f.filename)
        try:
            img = Image.open(f.stream).convert("RGB")
        except Exception:
            return "Could not open image. Please try a different file.", 400

        seed = request.form.get("seed")
        _set_tiles(split_image(img, UPLOAD_FOLDER))
        _set_state(shuffle_tiles(int(seed)) if (seed and seed.isdigit()) else shuffle_tiles())
        _set_moves(0)
        app.logger.info('new_game image_uploaded seed=%s filename="%s"', seed, filename)
    else:
        # Shared link support: /?state=1,2,3,4,5,6,7,8,0
        qs = request.args.get("state")
        if qs:
            try:
                st = [int(x) for x in qs.split(",")]
                if len(st) == 9 and is_solvable(st):
                    _set_state(st)
                    _set_moves(0)
                    app.logger.info("state_loaded_from_query")
            except Exception:
                pass

    tiles = _get_tiles()
    state = _get_state()
    moves = _get_moves()

    return render_template_string(
        """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>8-Puzzle Game</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;text-align:center;padding:20px;background:#87CEFA}
  .row{margin:8px 0}
  .grid{display:grid;grid-template-columns:repeat(3,100px);gap:5px;justify-content:center;margin:16px auto}
  .tile{width:100px;height:100px;border:1px solid #1E90FF;background-size:cover;background-position:center;cursor:pointer}
  .blank{background:#B0E0E6;cursor:default}
  button,select,input{padding:8px 12px;margin:0 6px 6px 0;border-radius:6px;border:1px solid #1E90FF;background:#1E90FF;color:#fff}
  button:hover{background:#4682B4}
  #status{margin-top:10px;color:#2F4F4F}
  @media (max-width:600px){
    .grid{grid-template-columns:repeat(3,33vw);gap:2vw}
    .tile{width:33vw;height:33vw}
  }
</style>
</head>
<body>
  <h1>8-Puzzle Game</h1>
  <p>Upload an image to scramble it into a 3×3 puzzle. Click tiles to move them and solve it!</p>

  <form method="post" enctype="multipart/form-data" class="row">
    <input type="file" name="file" accept=".png,.jpg,.jpeg,.webp" required>
    <input type="number" name="seed" placeholder="Optional seed">
    <button type="submit">Upload & Start</button>
  </form>

  <div class="row">
    <select id="heuristic">
      <option value="manhattan">Manhattan</option>
      <option value="misplaced">Misplaced tiles</option>
      <option value="linear">Linear conflict</option>
    </select>
    <button onclick="getMinimumMoves()">Min Moves</button>
    <button onclick="playSolution()">Play Solution</button>
    <button onclick="getHint()">Hint</button>
    <button onclick="copyShare()">Copy Share Link</button>
    <button onclick="resetSolved()">Show Solved</button>
    <button onclick="resetGame()">Reset</button>
  </div>

  <div id="grid" class="grid"></div>
  <div class="row"><strong id="move-count">Moves: {{ moves }}</strong></div>
  <div id="status"></div>

<script>
  let state = {{ state|tojson }};
  let moveCount = {{ moves|tojson }};
  const tiles = {{ tiles|tojson }};
  const grid = document.getElementById("grid");
  const moveCountDisplay = document.getElementById("move-count");
  const statusDisplay = document.getElementById("status");

  function renderGrid(){
    grid.innerHTML = '';
    if(!state || state.length===0){
      statusDisplay.textContent = "Upload an image to start!";
      return;
    }
    state.forEach((tile) => {
      const div = document.createElement('div');
      if(tile===0){
        div.className = 'tile blank';
      }else{
        div.className = 'tile';
        div.style.backgroundImage = `url(${tiles[tile-1]})`;
        div.onclick = () => moveTile(tile);
      }
      grid.appendChild(div);
    });
  }

  function moveTile(tile){
    fetch('/move', {
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:`tile=${tile}`
    }).then(r=>r.json()).then(d=>{
      state = d.state; moveCount = d.move_count;
      moveCountDisplay.textContent = `Moves: ${moveCount}`;
      renderGrid();
      statusDisplay.textContent = d.solved ? "🎉 Solved!" : "";
    });
  }

  function resetSolved(){
    fetch('/solution').then(r=>r.json()).then(d=>{
      state = d.state; renderGrid(); statusDisplay.textContent = "Solved state shown.";
    });
  }

  function getMinimumMoves(){
    const h = document.getElementById('heuristic').value;
    fetch('/minimum-moves?heuristic=' + h).then(r=>r.json()).then(d=>{
      if(d.minimum_moves !== undefined){
        alert(`Minimum moves (${d.heuristic}): ` + d.minimum_moves);
      }else{ alert('Error: ' + d.error); }
    });
  }

  function playSolution(){
    const h = document.getElementById('heuristic').value;
    fetch('/solve?heuristic=' + h).then(r=>r.json()).then(d=>{
      if(!d.path){ return alert(d.error || 'No solution.'); }
      const frames = d.path.slice();
      const step = () => {
        if(frames.length===0){ statusDisplay.textContent = "Replayed optimal solution."; return; }
        state = frames.shift(); renderGrid();
        setTimeout(step, 300);
      }; step();
    });
  }

  function getHint(){
    fetch('/hint').then(r=>r.json()).then(d=>{
      if(d.next_state){
        state = d.next_state; moveCount += 1;
        moveCountDisplay.textContent = `Moves: ${moveCount}`;
        renderGrid();
      }else{ alert(d.error || 'No hint'); }
    });
  }

  function copyShare(){
    if(!state || state.length!==9) return;
    const url = new URL(window.location.href);
    url.searchParams.set('state', state.join(','));
    navigator.clipboard.writeText(url.toString());
    alert('Shareable link copied!');
  }

  function resetGame(){
    fetch('/reset', { method: 'POST' })
      .then(()=> window.location.href = '/'); // reload empty
  }

  renderGrid();
</script>
</body>
</html>
        """,
        state=state,
        moves=moves,
        tiles=tiles,
    )

@app.route("/move", methods=["POST"])
def move_tile():
    st = _get_state()
    if not st:
        return jsonify({"state": st, "move_count": _get_moves(), "solved": False})

    try:
        tile = int(request.form["tile"])
    except Exception:
        return jsonify({"state": st, "move_count": _get_moves(), "solved": False})

    blank = st.index(0)
    ti = st.index(tile)
    rb, cb = divmod(blank, 3)
    rt, ct = divmod(ti, 3)

    if abs(rb - rt) + abs(cb - ct) == 1:
        st[blank], st[ti] = st[ti], st[blank]
        _set_state(st)
        _set_moves(_get_moves() + 1)
        solved = st == list(range(1, 9)) + [0]
        return jsonify({"state": st, "move_count": _get_moves(), "solved": solved})

    return jsonify({"state": st, "move_count": _get_moves(), "solved": False})

@app.route("/solution")
def show_solution():
    _set_state(list(range(1, 9)) + [0])
    return jsonify({"state": _get_state()})

@app.route("/minimum-moves")
def minimum_moves():
    st = _get_state()
    heur = request.args.get("heuristic", "manhattan")
    if st and is_solvable(st):
        moves, _ = a_star_with_path(st, heur)
        return jsonify({"minimum_moves": moves, "heuristic": heur})
    return jsonify({"error": "This puzzle state is not solvable or not started"})

@app.route("/solve")
def solve():
    st = _get_state()
    heur = request.args.get("heuristic", "manhattan")
    if st and is_solvable(st):
        moves, path = a_star_with_path(st, heur)
        return jsonify({"moves": moves, "path": [list(p) for p in path], "heuristic": heur})
    return jsonify({"error": "No solution available"})

@app.route("/hint")
def hint():
    st = _get_state()
    if st and is_solvable(st):
        _, path = a_star_with_path(st, "manhattan")
        if path:
            return jsonify({"next_state": list(path[0])})
    return jsonify({"error": "No hint available"})

@app.route("/reset", methods=["POST"])
def reset():
    _clear_session()
    return jsonify({"ok": True})

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "uptime_sec": round(time.time() - START_TS, 1)})

@app.route("/metrics")
def metrics():
    return jsonify({
        "has_state": bool(_get_state()),
        "moves": _get_moves(),
        "tiles": len(_get_tiles()),
    })

# -----------------------------------------------------------------------------
# Run (Render sets PORT)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
