import sys
sys.path.insert(0, ".")
import pytest
from unittest.mock import patch, MagicMock
from game import SnakeGame, init_game
import pygame

@pytest.fixture
def game():
    return SnakeGame()

def test_init_game():
    game = init_game()
    assert isinstance(game, SnakeGame)

def test_snake_game_init(game):
    assert game.snake == [(200, 200), (220, 200), (240, 200)]
    assert game.direction == 'RIGHT'
    assert game.score == 0

def test_generate_food(game):
    food = game.generate_food()
    assert isinstance(food, tuple)
    assert len(food) == 2
    assert 0 <= food[0] < game.display.get_width()
    assert 0 <= food[1] < game.display.get_height()

def test_generate_food_not_in_snake(game):
    food = game.generate_food()
    assert food not in game.snake

def test_update_snake(game):
    game.direction = 'RIGHT'
    game.update_snake()
    assert game.snake[-1][0] == 260

def test_update_snake_eat_food(game):
    game.food = (260, 200)
    game.update_snake()
    assert game.score == 1
    assert game.food != (260, 200)

def test_check_collision(game):
    game.snake = [(0, 0), (20, 0), (40, 0)]
    game.direction = 'LEFT'
    game.update_snake()
    assert game.check_collision()

def test_check_collision_with_self(game):
    game.snake = [(200, 200), (220, 200), (200, 200)]
    assert game.check_collision()

def test_draw_game(game):
    with patch('pygame.display.update') as mock_update:
        game.draw_game()
        mock_update.assert_called_once()

def test_draw_game_score(game):
    game.score = 10
    with patch('pygame.font.Font.render') as mock_render:
        game.draw_game()
        mock_render.assert_called_with(f'Score: {game.score}', True, (255, 255, 255))

def test_main():
    with patch('pygame.init') as mock_init:
        with patch('pygame.display.set_mode') as mock_set_mode:
            with patch('game.SnakeGame') as mock_game:
                from main import main
                main()
                mock_init.assert_called_once()
                mock_set_mode.assert_called_once()
                mock_game.assert_called_once()

def test_main_game_loop():
    with patch('pygame.event.get') as mock_get:
        with patch('game.SnakeGame') as mock_game:
            from main import main
            main()
            mock_get.assert_called()

def test_main_game_loop_update_snake():
    with patch('pygame.event.get') as mock_get:
        with patch('game.SnakeGame.update_snake') as mock_update_snake:
            with patch('game.SnakeGame') as mock_game:
                from main import main
                main()
                mock_update_snake.assert_called()

def test_main_game_loop_draw_game():
    with patch('pygame.event.get') as mock_get:
        with patch('game.SnakeGame.draw_game') as mock_draw_game:
            with patch('game.SnakeGame') as mock_game:
                from main import main
                main()
                mock_draw_game.assert_called()