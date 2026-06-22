import pygame
import random
import sys
from constants import (
    WIDTH,
    HEIGHT,
    BLOCK_SIZE,
    FPS,
    WHITE,
    BLACK,
    RED,
    GREEN,
    DARK_GREEN,
    BLUE,
    FONT_SMALL,
    FONT_LARGE,
)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Game")
        self.clock = pygame.time.Clock()
        self.reset()

    def reset(self):
        # Start snake in middle
        start_x = WIDTH // 2 - (WIDTH // 2) % BLOCK_SIZE
        start_y = HEIGHT // 2 - (HEIGHT // 2) % BLOCK_SIZE
        self.snake = [(start_x, start_y)]
        self.direction = (BLOCK_SIZE, 0)  # moving right initially
        self.score = 0
        self.food = self.place_food()
        self.game_over = False

    def place_food(self):
        while True:
            x = random.randrange(0, WIDTH // BLOCK_SIZE) * BLOCK_SIZE
            y = random.randrange(0, HEIGHT // BLOCK_SIZE) * BLOCK_SIZE
            if (x, y) not in self.snake:
                return (x, y)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_UP and self.direction != (0, BLOCK_SIZE):
                    self.direction = (0, -BLOCK_SIZE)
                elif event.key == pygame.K_DOWN and self.direction != (0, -BLOCK_SIZE):
                    self.direction = (0, BLOCK_SIZE)
                elif event.key == pygame.K_LEFT and self.direction != (BLOCK_SIZE, 0):
                    self.direction = (-BLOCK_SIZE, 0)
                elif event.key == pygame.K_RIGHT and self.direction != (-BLOCK_SIZE, 0):
                    self.direction = (BLOCK_SIZE, 0)

    def update(self):
        if self.game_over:
            return

        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Wall collision
        if (
            new_head[0] < 0
            or new_head[0] >= WIDTH
            or new_head[1] < 0
            or new_head[1] >= HEIGHT
        ):
            self.game_over = True
            return

        # Self collision
        if new_head in self.snake:
            self.game_over = True
            return

        # Move snake
        self.snake.insert(0, new_head)

        # Food collision
        if new_head == self.food:
            self.score += 1
            self.food = self.place_food()
        else:
            self.snake.pop()  # remove tail

    def draw(self):
        self.screen.fill(BLACK)

        # Draw food
        pygame.draw.rect(
            self.screen, RED, (*self.food, BLOCK_SIZE, BLOCK_SIZE)
        )

        # Draw snake
        for i, segment in enumerate(self.snake):
            color = DARK_GREEN if i == 0 else GREEN
            pygame.draw.rect(
                self.screen, color, (*segment, BLOCK_SIZE, BLOCK_SIZE)
            )

        # Draw score
        score_surf = FONT_SMALL.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_surf, (10, 10))

        if self.game_over:
            over_surf = FONT_LARGE.render("Game Over! Press R to Restart", True, BLUE)
            rect = over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            self.screen.blit(over_surf, rect)

        pygame.display.flip()

    def run(self):
        while True:
            self.handle_events()
            if not self.game_over:
                self.update()
            else:
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    self.reset()
            self.draw()
            self.clock.tick(FPS)


def main():
    Game().run()


if __name__ == "__main__":
    main()