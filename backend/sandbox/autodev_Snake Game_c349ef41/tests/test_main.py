import sys; sys.path.insert(0, ".")
import builtins
import types
import pytest
from unittest import mock

# Mock pygame modules before importing the game code
mock_pygame = types.SimpleNamespace()
mock_pygame.init = mock.Mock()
mock_pygame.display = types.SimpleNamespace(set_mode=mock.Mock(return_value=mock.Mock()),
                                            set_caption=mock.Mock(),
                                            flip=mock.Mock())
mock_pygame.time = types.SimpleNamespace(Clock=mock.Mock(return_value=mock.Mock(tick=mock.Mock())))
mock_pygame.event = types.SimpleNamespace(get=mock.Mock(return_value=[]))
mock_pygame.draw = types.SimpleNamespace(rect=mock.Mock())
mock_pygame.font = types.SimpleNamespace(SysFont=mock.Mock(return_value=mock.Mock(render=mock.Mock(return_value=mock.Mock()))),
                                        init=mock.Mock())
mock_pygame.key = types.SimpleNamespace(get_pressed=mock.Mock(return_value={}))
mock_pygame.K_UP = 273
mock_pygame.K_DOWN = 274
mock_pygame.K_LEFT = 276
mock_pygame.K_RIGHT = 275
mock_pygame.K_ESCAPE = 27
mock_pygame.K_r = 114
mock_pygame.QUIT = 12
mock_pygame.KEYDOWN = 2

sys.modules['pygame'] = mock_pygame

from main import Game
from constants import WIDTH, HEIGHT, BLOCK_SIZE

@pytest.fixture
def game():
    g = Game()
    # Ensure deterministic start position
    g.reset()
    return g

def test_reset_initial_state(game):
    start_x = WIDTH // 2 - (WIDTH // 2) % BLOCK_SIZE
    start_y = HEIGHT // 2 - (HEIGHT // 2) % BLOCK_SIZE
    assert game.snake == [(start_x, start_y)]
    assert game.direction == (BLOCK_SIZE, 0)
    assert game.score == 0
    assert isinstance(game.food, tuple) and len(game.food) == 2
    assert not game.game_over

def test_place_food_not_on_snake(monkeypatch, game):
    # Force snake to occupy many positions
    game.snake = [(0,0), (20,0), (40,0)]
    # Mock random to produce a specific coordinate that is on snake first, then free
    seq = [(0,0), (20,0), (60,0)]
    def fake_randrange(a, b=None):
        # return next x or y from seq
        val = seq.pop(0)[0] // BLOCK_SIZE
        return val
    monkeypatch.setattr('random.randrange', lambda a, b=None: seq.pop(0)[0] // BLOCK_SIZE)
    # Since we cannot easily control both x and y with same call, just test that result not in snake
    food = game.place_food()
    assert food not in game.snake
    assert 0 <= food[0] < WIDTH
    assert 0 <= food[1] < HEIGHT

def test_update_moves_snake_forward():
    g = Game()
    g.reset()
    initial_head = g.snake[0]
    g.update()
    new_head = g.snake[0]
    assert new_head == (initial_head[0] + BLOCK_SIZE, initial_head[1])
    # Tail should have moved (length stays 1)
    assert len(g.snake) == 1

def test_update_eats_food_and_grows(monkeypatch):
    g = Game()
    g.reset()
    # Place food directly in front of snake
    head_x, head_y = g.snake[0]
    g.food = (head_x + BLOCK_SIZE, head_y)
    g.update()
    assert g.score == 1
    # Snake should have length 2 now
    assert len(g.snake) == 2
    # New head is at food position
    assert g.snake[0] == g.food
    # Food should have moved to a new location not colliding with snake
    assert g.food not in g.snake

def test_update_wall_collision_sets_game_over():
    g = Game()
    g.reset()
    # Position snake near right wall moving right
    g.snake = [(WIDTH - BLOCK_SIZE, 0)]
    g.direction = (BLOCK_SIZE, 0)
    g.update()
    assert g.game_over is True

def test_update_self_collision_sets_game_over():
    g = Game()
    g.reset()
    # Create a snake shaped to collide with itself on next move
    g.snake = [(100,100), (80,100), (80,120), (100,120)]
    g.direction = (0, -BLOCK_SIZE)  # moving up into its own body at (100,100)
    g.update()
    assert g.game_over is True

def test_handle_events_keypress_changes_direction():
    g = Game()
    g.reset()
    # Simulate KEYDOWN event for LEFT key
    mock_event = mock.Mock()
    mock_event.type = mock_pygame.KEYDOWN
    mock_event.key = mock_pygame.K_LEFT
    mock_pygame.event.get.return_value = [mock_event]
    g.handle_events()
    assert g.direction == (-BLOCK_SIZE, 0)

def test_handle_events_prevent_reverse_direction():
    g = Game()
    g.reset()
    # Initially moving right
    # Simulate KEYDOWN for LEFT which should be ignored (reverse)
    mock_event = mock.Mock()
    mock_event.type = mock_pygame.KEYDOWN
    mock_event.key = mock_pygame.K_LEFT
    mock_pygame.event.get.return_value = [mock_event]
    g.handle_events()
    assert g.direction == (BLOCK_SIZE, 0)  # unchanged

def test_handle_events_quit_exits(monkeypatch):
    # Patch sys.exit to raise SystemExit for test capture
    monkeypatch.setattr('sys.exit', lambda: (_ for _ in ()).throw(SystemExit))
    g = Game()
    mock_event = mock.Mock()
    mock_event.type = mock_pygame.QUIT
    mock_pygame.event.get.return_value = [mock_event]
    with pytest.raises(SystemExit):
        g.handle_events()

def test_draw_calls_pygame_functions(monkeypatch):
    g = Game()
    g.reset()
    # Replace screen with mock
    mock_screen = mock.Mock()
    g.screen = mock_screen
    # Call draw
    g.draw()
    # Verify background fill, rect draws for food and snake, and flip
    mock_screen.fill.assert_called_once_with(mock_pygame.BLACK)
    assert mock_pygame.draw.rect.call_count >= 1  # at least food and head
    mock_pygame.display.flip.assert_called_once()