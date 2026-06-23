import pygame
import random
from pygame.locals import *
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Pygame
pygame.init()

# Set up some constants
WIDTH, HEIGHT = 800, 600
BLOCK_SIZE = 20
FPS = 10

# Set up some colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)

class SnakeGame:
    def __init__(self):
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.reset_game()

    def reset_game(self):
        self.snake = [(200, 200), (220, 200), (240, 200)]
        self.direction = 'RIGHT'
        self.food = self.generate_food()
        self.score = 0

    def generate_food(self):
        while True:
            x = random.randint(0, WIDTH - BLOCK_SIZE) // BLOCK_SIZE * BLOCK_SIZE
            y = random.randint(0, HEIGHT - BLOCK_SIZE) // BLOCK_SIZE * BLOCK_SIZE
            food = (x, y)
            if food not in self.snake:
                return food

    def update_snake(self):
        head = self.snake[-1]
        if self.direction == 'RIGHT':
            new_head = (head[0] + BLOCK_SIZE, head[1])
        elif self.direction == 'LEFT':
            new_head = (head[0] - BLOCK_SIZE, head[1])
        elif self.direction == 'UP':
            new_head = (head[0], head[1] - BLOCK_SIZE)
        elif self.direction == 'DOWN':
            new_head = (head[0], head[1] + BLOCK_SIZE)

        self.snake.append(new_head)
        if self.food == new_head:
            self.score += 1
            self.food = self.generate_food()
        else:
            self.snake.pop(0)

    def check_collision(self):
        head = self.snake[-1]
        if (head[0] < 0 or head[0] >= WIDTH or
            head[1] < 0 or head[1] >= HEIGHT or
            head in self.snake[:-1]):
            return True
        return False

    def draw_game(self):
        self.display.fill(BLACK)
        for pos in self.snake:
            pygame.draw.rect(self.display, GREEN, (pos[0], pos[1], BLOCK_SIZE, BLOCK_SIZE))
        pygame.draw.rect(self.display, RED, (self.food[0], self.food[1], BLOCK_SIZE, BLOCK_SIZE))
        font = pygame.font.Font(None, 36)
        text = font.render(f'Score: {self.score}', True, WHITE)
        self.display.blit(text, (10, 10))
        pygame.display.update()

def init_game():
    game = SnakeGame()
    return game

def main():
    game = init_game()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_RIGHT and game.direction != 'LEFT':
                    game.direction = 'RIGHT'
                elif event.key == K_LEFT and game.direction != 'RIGHT':
                    game.direction = 'LEFT'
                elif event.key == K_UP and game.direction != 'DOWN':
                    game.direction = 'UP'
                elif event.key == K_DOWN and game.direction != 'UP':
                    game.direction = 'DOWN'
        game.update_snake()
        if game.check_collision():
            game.reset_game()
        game.draw_game()
        game.clock.tick(FPS)
    pygame.quit()

if __name__ == '__main__':
    main()