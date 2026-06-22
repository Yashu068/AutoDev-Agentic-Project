import pygame

# Screen dimensions
WIDTH = 640
HEIGHT = 480

# Size of each snake block (in pixels)
BLOCK_SIZE = 20

# Frames per second
FPS = 10

# Colors (R, G, B)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
GREEN = (0, 200, 0)
DARK_GREEN = (0, 155, 0)
BLUE = (0, 0, 255)

# Initialize pygame's font module (optional, for score display)
pygame.font.init()
FONT_SMALL = pygame.font.SysFont('arial', 18)
FONT_LARGE = pygame.font.SysFont('arial', 36)