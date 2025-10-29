# app.py
import os
import random
from heapq import heappop, heappush
from itertools import count

from flask import Flask, render_template_string, jsonify, request, url_for
from werkzeug.utils import secure_filename
from PIL import Image

# -----------------------------------------------------------------------------
# Flask setup
# -----------------------------------------------------------------------------
app = Flask(__name__)

# Where we save the 3x3 image tiles (Render provides ephemeral disk per deploy;
# this is fine for a toy app)
UPLOAD_FOLDER = os.path.join(app.root_path, "static")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Limit upload size (4 MB) and restrict to common image types
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Global game state (simple demo). For multi-user production, use sessions/db.
tiles = []            # list of tile image URLs
current_state = []    # list of 9 ints representing board (0 is blank)
move_count = 0        # number of user moves


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Manhattan distance heuristic for A*
def manhattan_distance(state):
    distance = 0
    for index, value in enumerate(state):
        if value == 0:
            continue
        target_x, target_y = divmod(value - 1, 3)
        x, y = divmod(index, 3)
        distance += abs(target_x - x) + abs(target_y - y)
    return distance


# A* search to find the minimum number of moves to solve the 8-puzzle
def a_star_search(initial_state):
    goal_state = tuple(range(1, 9)) + (0,)
    parent_map = {tuple(initial_state): None}
    g_score = {tuple(initial_state): 0}
    f_score = {tuple(initial_state): manhattan_distance(initial_state)}

    open_set = []
    heappush(open_set, (f_score[tuple(initial_state)], next(count()), tuple(initial_state)))

    while open_set:
        _, __, current = heappop(open_set)

        if current == goal_state:
            # Reconstruct path length (number of moves)
            moves = 0
            while parent_map[current]:
                current = parent_map[current]
                moves += 1
            return moves

        current_index = current.index(0)
        x, y = divmod(current_index, 3)
        neighbors = []
        if x > 0: neighbors.append(current_index - 3)
        if x < 2: neighbors.append(current_index + 3)
        if y > 0: neighbors.append(current_index - 1)
        if y < 2: neighbors.append(current_index + 1)

        for neighbor in neighbors:
            new_state = list(current)
            new_state[current_index], new_state[neighbor] = new_state[neighbor], new_state[current_index]
            new_state = tuple(new_state)

            tentative_g = g_score[current] + 1
            if new_state not in g_score or tentative_g < g_score[new_state]:
                parent_map[new_state] = current
                g_score[new_state] = tentative_g
                f_score[new_state] = tentative_g + manhattan_distance(new_state)
                heappush(open_set, (f_score[new_state], next(count()), new_state))

    return -1  # Unsolvable (shouldn’t happen if we generate solvable shuffles)


# Cut image to 3x3 and save tiles to /static
def split_image(img: Image.Image, upload_folder: str):
    # Make it square (crop the smallest side), then resize to 300x300
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((300, 300))

    tile_size = img.size[0] // 3
    pieces = []
    for i in range(3):
        for j in range(3):
            L = j * tile_size
            U = i * tile_size
            tile = img.crop((L, U, L + tile_size, U + tile_size))
            tile_path = os.path.join(upload_folder, f"tile_{i}_{j}.png")
            tile.save(tile_path)
            pieces.append(url_for("static", filename=f"tile_{i}_{j}.png"))

    return pieces


# Generate a random solvable permutation
def shuffle_tiles():
    state = list(range(1, 9)) + [0]
    while True:
        random.shuffle(state)
        if is_solvable(state):
            return state


# Check 8-puzzle solvability by counting inversions
def is_solvable(state):
    inv = 0
    for i in range(len(state)):
        for j in range(i + 1, len(state)):
            if state[i] and state[j] and state[i] > state[j]:
                inv += 1
    return inv % 2 == 0


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    global tiles, current_state, move_count

    if request.method == "POST":
        # Reset the game state
        move_count = 0

        if "file" not in request.files:
            return "No file part", 400

        img_file = request.files["file"]
        if img_file.filename == "":
            return "No selected file", 400

        if not allowed_file(img_file.filename):
            return "Invalid file type. Please upload PNG/JPG/JPEG/WEBP.", 400

        # Open with PIL and generate tiles
        filename = secure_filename(img_file.filename)
        try:
            img = Image.open(img_file.stream).convert("RGB")
        except Exception:
            return "Could not open image. Please try a different file.", 400

        tiles = split_image(img, UPLOAD_FOLDER)
        current_state = shuffle_tiles()

    # Render page
    return render_template_string(
        """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>8-Puzzle Game</title>
<style>
  body { font-family: Arial, sans-serif; text-align: center; padding: 20px; background-color: #87CEFA; }
  .grid { display: grid; grid-template-columns: repeat(3, 100px); gap: 5px; justify-content: center; margin: 20px auto; }
  .tile { width: 100px; height: 100px; border: 1px solid #1E90FF; cursor: pointer; background-size: cover; background-position: center; transition: background 0.2s ease; }
  .blank { background-color: #B0E0E6; cursor: default; }
  button { margin: 10px; padding: 10px 20px; font-size: 16px; background-color: #1E90FF; color: #fff; border: none; border-radius: 5px; }
  button:hover { background-color: #4682B4; }
  #status { margin-top: 20px; font-size: 18px; color: #2F4F4F; }
  @media (max-width: 600px) {
    .grid { grid-template-columns: repeat(3, 33vw); gap: 2vw; }
    .tile { width: 33vw; height: 33vw; }
  }
</style>
</head>
<body>
  <h1>8-Puzzle Game</h1>
  <p>Upload an image to scramble it into a 3×3 puzzle. Click tiles to move them and solve it!</p>

  <form method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept=".png,.jpg,.jpeg,.webp" required />
    <button type="submit">Upload Image</button>
  </form>

  <button id="show-solution" onclick="showSolution()">Show Solution</button>
  <button id="min-moves" onclick="getMinimumMoves()">Get Minimum Moves to Solve</button>

  <div id="grid" class="grid"></div>
  <p id="move-count">Moves: {{ move_count }}</p>
  <p id="status"></p>

<script>
  let state = {{ state|tojson }};
  let moveCount = {{ move_count|tojson }};
  const tiles = {{ tiles|tojson }};
  const grid = document.getElementById("grid");
  const moveCountDisplay = document.getElementById("move-count");
  const statusDisplay = document.getElementById("status");

  function renderGrid() {
    grid.innerHTML = '';
    if (!state || state.length === 0) {
      statusDisplay.textContent = "Upload an image to start!";
      return;
    }
    state.forEach((tile) => {
      const div = document.createElement('div');
      if (tile === 0) {
        div.className = 'tile blank';
      } else {
        div.className = 'tile';
        div.style.backgroundImage = `url(${tiles[tile - 1]})`;
        div.onclick = () => moveTile(tile);
      }
      grid.appendChild(div);
    });
  }

  function moveTile(tile) {
    fetch('/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `tile=${tile}`
    }).then(r => r.json())
     .then(data => {
        state = data.state;
        moveCount = data.move_count;
        moveCountDisplay.textContent = `Moves: ${moveCount}`;
        renderGrid();
        if (data.solved) {
          statusDisplay.textContent = "🎉 Congratulations! You solved the puzzle!";
        } else {
          statusDisplay.textContent = "";
        }
     });
  }

  function showSolution() {
    fetch('/solution').then(r => r.json()).then(data => {
      state = data.state;
      renderGrid();
      statusDisplay.textContent = "Here's the solved puzzle!";
    });
  }

  function getMinimumMoves() {
    fetch('/minimum-moves').then(r => r.json()).then(data => {
      if (data.minimum_moves !== undefined) {
        alert('Minimum moves to solve: ' + data.minimum_moves);
      } else {
        alert('Error: ' + data.error);
      }
    });
  }

  renderGrid();
</script>
</body>
</html>
        """,
        state=current_state,
        move_count=move_count,
        tiles=tiles,
    )


@app.route("/move", methods=["POST"])
def move_tile():
    global current_state, move_count
    if not current_state:
        return jsonify({"state": current_state, "move_count": move_count, "solved": False})

    try:
        tile = int(request.form["tile"])
    except Exception:
        return jsonify({"state": current_state, "move_count": move_count, "solved": False})

    blank_index = current_state.index(0)
    tile_index = current_state.index(tile)

    rb, cb = divmod(blank_index, 3)
    rt, ct = divmod(tile_index, 3)

    if abs(rb - rt) + abs(cb - ct) == 1:
        current_state[blank_index], current_state[tile_index] = current_state[tile_index], current_state[blank_index]
        move_count += 1
        solved = current_state == list(range(1, 9)) + [0]
        return jsonify({"state": current_state, "move_count": move_count, "solved": solved})

    return jsonify({"state": current_state, "move_count": move_count, "solved": False})


@app.route("/solution", methods=["GET"])
def show_solution():
    global current_state
    current_state = list(range(1, 9)) + [0]  # Solved state
    return jsonify({"state": current_state})


@app.route("/minimum-moves", methods=["GET"])
def minimum_moves():
    global current_state
    if current_state and is_solvable(current_state):
        moves = a_star_search(current_state)
        return jsonify({"minimum_moves": moves})
    return jsonify({"error": "This puzzle state is not solvable or not started"})


# -----------------------------------------------------------------------------
# Run (Render injects PORT). DO NOT USE debug=True in production.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
