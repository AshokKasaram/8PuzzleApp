# 8PuzzleApp – AI-Powered Image Puzzle Solver

**🎮 Live Demo:** [Play Here](https://eightpuzzleapp.onrender.com)

> Where algorithmic intelligence meets interactive design — solving puzzles, one tile at a time.

---

## Introduction
Welcome to **8PuzzleApp**, an interactive AI-powered puzzle solver built with **Flask**, **Python**, and **JavaScript**.  
Upload any image and the app transforms it into a classic 3×3 *8-puzzle*, then uses the **A\*** search algorithm to compute and visualize the shortest solution path.

This app showcases **artificial intelligence**, **algorithmic reasoning**, and **full-stack web development** — perfect for highlighting data science, AI, and software engineering skills.

---

## Key Features

- **Dynamic Image Scrambling** – Upload any image; it’s sliced into 9 tiles to form a playable puzzle.
- **AI-Powered Solver (A\*)** – Select from multiple admissible heuristics:
  - Manhattan Distance
  - Misplaced Tiles
  - Linear Conflict
- **Interactive Options**
  - *Minimum Moves* – Compute optimal move count  
  - *Play Solution* – Watch the AI replay the best solution step-by-step  
  - *Hint* – Get the next best move  
  - *Copy Share Link* – Share an exact puzzle configuration  
  - *Reset* – Start fresh instantly
- **Optional Seed Control** – Deterministic shuffling for reproducible puzzles
- **Clean Reset Logic** – Refresh or click **Reset** to clear the board
- **Responsive UI** – Works across desktop and mobile

---

## Technical Highlights

| Layer         | Technology                 | Description                                              |
|---------------|----------------------------|----------------------------------------------------------|
| **Backend**   | Flask (Python)            | Routes, user sessions, A\* search orchestration          |
| **Algorithm** | A\* Search                 | Multiple admissible heuristics for optimal pathfinding   |
| **Frontend**  | HTML5, CSS3, Vanilla JS   | Real-time interactivity and puzzle visualization         |
| **Imaging**   | Pillow (PIL)              | Crops/splits uploaded images into 3×3 tiles              |
| **Deployment**| Render                    | Cloud deploy with session isolation & health endpoints   |

---

## How It Works

1. **Upload** an image (PNG, JPG, JPEG, or WEBP)  
2. The app crops to square and splits it into 9 tiles  
3. Tiles are shuffled (optionally using a custom seed)  
4. You can:  
   - Move tiles manually  
   - Run the **AI solver** for the optimal path  
   - Replay the **solution animation**  
   - Compare heuristics for efficiency  
   - Share a generated URL for the exact configuration

---

## Advanced Features

- **Multi-Heuristic Benchmarking:** Compare Manhattan, Misplaced, and Linear Conflict
- **Performance & Health Endpoints**
  - `GET /healthz` → Health check & uptime
  - `GET /metrics` → Internal metrics (moves, tiles, state)
- **Session-Scoped Game State:** Puzzles isolated per user session
- **Educational Insight:** Visualizes how search and heuristics affect pathfinding

---
### A* Search Objective

**Formula:** `f(n) = g(n) + h(n)`  
- **g(n):** Cost so far (moves made)  
- **h(n):** Heuristic estimate of remaining cost


### Heuristic Comparison

| Heuristic            | Description                              | Pros                 | Cons        |
|----------------------|------------------------------------------|----------------------|-------------|
| **Misplaced Tiles**  | Counts tiles not in correct position     | Fast, simple         | Low accuracy|
| **Manhattan Distance** | Sum of row & column distances          | Balanced, reliable   | Baseline    |
| **Linear Conflict**  | Manhattan + penalties for row/col conflicts | Most accurate     | Slower      |

---

## Installation (Run Locally)

```bash
# Clone the repository
git clone https://github.com/<your-username>/8PuzzleApp.git
cd 8PuzzleApp

# (Recommended) create a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app locally
python app.py

Now visit 👉 [http://localhost:5000](http://localhost:5000)

---

## Deployment (Render)

- **Platform:** Render  
- **Auto-Deploy:** From GitHub on push  
- **Runtime:** `runtime.txt` → Python **3.11.9**  
- **Environment Variables:**
  - `SECRET_KEY`
  - `PORT` *(if required by Render)*  
- **Health & Ops:**
  - `/healthz` – Health check & uptime  
  - `/metrics` – Internal metrics for observability  

### One-Click Deployment Checklist
1. Connect repo in **Render**
2. Set environment variables (`SECRET_KEY`, `PORT`)
3. Specify build/run commands if using a `Procfile` or `gunicorn`
4. Enable **Auto-Deploy**

---

## API & Routes (Selected)

| **Method** | **Route**     | **Purpose**                        |
|-------------|---------------|------------------------------------|
| GET         | `/`           | Home page + puzzle UI              |
| POST        | `/upload`     | Upload image & create puzzle       |
| POST        | `/solve`      | Run A\* solver                     |
| GET         | `/healthz`    | Health check & uptime              |
| GET         | `/metrics`    | Internal metrics (debug/teaching)  |

> **Note:** Some routes may be protected by session context; avoid calling the solver before a board exists.

---

## Project Structure (Typical)

8PuzzleApp/
├─ app.py
├─ static/
│  ├─ css/
│  └─ js/
├─ templates/
│  └─ index.html
├─ utils/
│  ├─ astar.py
│  ├─ heuristics.py
│  └─ image_ops.py
├─ requirements.txt
├─ runtime.txt
└─ README.md
