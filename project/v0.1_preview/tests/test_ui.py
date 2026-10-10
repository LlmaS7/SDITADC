"""Exercise actual Pygame event handling off-screen, including the task dialog."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import argparse
import unittest
from unittest.mock import patch
import pygame
import main
from config import DEFAULT_SEED, ROOT
from ui.task_panel import TaskPanel


class UITests(unittest.TestCase):
    def test_pause_single_step_add_upgrade_cancel_and_auto(self):
        captures = []
        panel = TaskPanel()
        frame = 0
        def events():
            nonlocal frame
            frame += 1
            keys = {5: pygame.K_SPACE, 15: pygame.K_n, 95: pygame.K_s}
            clicks = {25: (320, 92), 35: (450, 92), 45: (745, 533),
                      55: (910, 212), 65: (1050, 670), 75: (1220, 670), 85: (560, 92)}
            if frame in keys:
                return [pygame.event.Event(pygame.KEYDOWN, key=keys[frame])]
            if frame in clicks:
                return [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=clicks[frame])]
            if frame == 40:
                target = ROOT / "work" / "task_dialog.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(pygame.display.get_surface(), target)
            if frame >= 120:
                return [pygame.event.Event(pygame.QUIT)]
            return []
        args = argparse.Namespace(seed=DEFAULT_SEED, load=None, auto=False,
                                  screenshot=None, screenshot_tick=0)
        with patch.object(pygame.event, "get", side_effect=events), \
                patch("ui.task_panel.TaskPanel", return_value=panel), \
                patch.object(main, "save", side_effect=lambda s: captures.append(s.snapshot())):
            main.graphical(args)
        view = captures[-1]
        self.assertEqual(view.tick, 1)
        self.assertTrue(view.paused)
        self.assertEqual(len(view.tasks), 11)
        self.assertEqual(view.tasks[1].priority, 5)
        self.assertEqual(view.tasks[1].status, "cancelled")
        self.assertEqual([t.id for t in panel.tasks(view)], list(range(2, 12)))
        self.assertNotEqual(panel.selected, 1)
        self.assertTrue(view.auto)
        self.assertGreaterEqual(view.metrics["preemptions"], 1)
        self.assertEqual(view.metrics["collisions"], 0)


if __name__ == "__main__":
    unittest.main()
