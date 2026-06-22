# Snake Game

A classic Snake arcade game built with Python and Pygame. Control the snake, eat food, and avoid colliding with walls or yourself. The game tracks your score and displays a game‑over screen with an option to restart.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Game](#running-the-game)
- [Controls](#controls)
- [Gameplay](#gameplay)
- [License](#license)

## Features

- Simple, responsive controls using the arrow keys.
- Random food placement that never appears on the snake.
- Score tracking displayed in the top‑left corner.
- Game‑over detection for wall and self collisions.
- Restart the game by pressing **R** after a game over.
- Clean, modular code with constants defined in `constants.py`.

## Requirements

- Python 3.8 or newer
- Pygame 2.0.0 or newer (listed in `requirements.txt`)

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/snake-game.git
   cd snake-game
   ```

2. **Create a virtual environment (optional but recommended)**

   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Running the Game

Execute the main script:

```bash
python main.py
```

The game window will open. If you encounter any issues, ensure that Pygame installed correctly and that your Python version meets the requirement.

## Controls

| Action          | Key          |
|-----------------|--------------|
| Move Up         | ↑ (Up Arrow) |
| Move Down       | ↓ (Down Arrow) |
| Move Left       | ← (Left Arrow) |
| Move Right      | → (Right Arrow) |
| Pause/Exit      | Esc          |
| Restart (after Game Over) | R |

## Gameplay

- The snake starts in the center of the screen moving to the right.
- Each time the snake eats a red food block, the score increments and the snake grows by one block.
- Colliding with the window borders or any part of the snake’s own body ends the game.
- After a game over, press **R** to restart without closing the window.

## License

This project is released under the MIT License. Feel free to modify and share!