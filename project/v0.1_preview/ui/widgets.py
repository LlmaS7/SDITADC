from pathlib import Path
import pygame

BG = (17, 24, 39)
CARD = (28, 39, 57)
TEXT = (230, 238, 248)
MUTED = (153, 173, 196)
ACCENT = (91, 193, 231)
RED = (253, 109, 113)


class Fonts:
    def __init__(self):
        candidates = [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]
        path = next((str(p) for p in candidates if p.exists()), None)
        self.small = pygame.font.Font(path, 13)
        self.body = pygame.font.Font(path, 15)
        self.medium = pygame.font.Font(path, 18)
        self.title = pygame.font.Font(path, 25)


def text(surface, font, value, pos, color=TEXT, width=None):
    value = str(value)
    if width is not None:
        while value and font.size(value)[0] > width:
            value = value[:-2] + "…" if not value.endswith("…") else value[:-2] + "…"
    surface.blit(font.render(value, True, color), pos)


def button(surface, fonts, rect, label, active=False, danger=False, disabled=False):
    rect = pygame.Rect(rect)
    color = (38, 97, 116) if active else (48, 62, 82)
    if danger:
        color = (120, 55, 66)
    if disabled:
        color = (35, 44, 58)
    pygame.draw.rect(surface, color, rect, border_radius=7)
    pygame.draw.rect(surface, (65, 83, 107), rect, 1, border_radius=7)
    label_surface = fonts.body.render(label, True, MUTED if disabled else TEXT)
    surface.blit(label_surface, label_surface.get_rect(center=rect.center))
    return rect

