import pygame
import sys
from game import init_game

def main():
    pygame.init()
    game = init_game()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT and game.direction != 'LEFT':
                    game.direction = 'RIGHT'
                elif event.key == pygame.K_LEFT and game.direction != 'RIGHT':
                    game.direction = 'LEFT'
                elif event.key == pygame.K_UP and game.direction != 'DOWN':
                    game.direction = 'UP'
                elif event.key == pygame.K_DOWN and game.direction != 'UP':
                    game.direction = 'DOWN'
        game.update_snake()
        if game.check_collision():
            game.reset_game()
        game.draw_game()
        game.clock.tick(10)
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()