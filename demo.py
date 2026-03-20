"""
Hardware-Free Demo
Author: S. Sasmitha

Runs the complete sorting game using simulated inputs so you can try every
part of the system without a webcam, Arduino, or MySQL server.

    python demo.py                  # fully simulated, windowed
    python demo.py --duration 30    # run for 30 seconds then quit
    python demo.py --headless       # no window, just prints stats
    python demo.py --show-charts    # render analytics charts at the end
"""

import argparse
import math
import random
import time
import sys
import os

# ── Optional PyGame import ────────────────────────────────────────────────────
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from src.config import GameConfig, EMGConfig

CFG = GameConfig()

# ── Simulated subsystems ──────────────────────────────────────────────────────

class SimulatedGesture:
    """
    Moves a virtual hand in a smooth figure-of-eight path and toggles
    OPEN / CLOSED every ~2 seconds to simulate natural grab / release.
    """
    def __init__(self, w: int, h: int):
        self._w   = w
        self._h   = h
        self._t   = 0.0
        self._state_timer = 0.0
        self._state = "OPEN"
        self._toggle_interval = 2.0

    def get_hand_state(self):
        self._t += 0.03
        self._state_timer += 0.033  # ~30 FPS tick

        x = int(self._w / 2 + math.sin(self._t)       * (self._w * 0.30))
        y = int(self._h / 2 + math.sin(self._t * 2)   * (self._h * 0.20))

        if self._state_timer >= self._toggle_interval:
            self._state = "CLOSED" if self._state == "OPEN" else "OPEN"
            self._toggle_interval = random.uniform(1.5, 3.0)
            self._state_timer = 0.0

        return x, y, self._state

    def release(self): pass


class SimulatedVoice:
    def get_latest_command(self): return None
    def stop(self): pass


class SimulatedGlove:
    def set_state(self, state: str): pass
    def emergency_stop(self): pass
    def close(self): pass


class SimulatedDB:
    """In-memory stub — stores session data as plain Python dicts."""
    def __init__(self):
        self._sessions: list[dict] = []
        self._session_id = 0

    def ensure_player(self, name: str): pass

    def start_session(self, name: str) -> int:
        self._session_id += 1
        self._sessions.append({"id": self._session_id, "player": name,
                                "score": 0, "accuracy": 0.0,
                                "duration": 0, "ended": False})
        return self._session_id

    def end_session(self, sid: int, score: int,
                    accuracy: float, duration: int):
        for s in self._sessions:
            if s["id"] == sid:
                s.update(score=score, accuracy=accuracy,
                          duration=duration, ended=True)

    def get_adaptive_feedback(self, name: str) -> str:
        completed = [s for s in self._sessions if s["ended"]]
        if not completed:
            return "Welcome! Start playing to receive feedback."
        avg_acc = sum(s["accuracy"] for s in completed) / len(completed)
        if avg_acc < 0.50:
            return "Beginner: work on hand positioning."
        elif avg_acc < 0.75:
            return "Intermediate: work on pick-up/drop consistency."
        return "Advanced: excellent! Improve gesture-timing synchronisation."

    def close(self): pass

    def print_summary(self):
        print("\n" + "─" * 54)
        print("  SESSION SUMMARY (in-memory)")
        print("─" * 54)
        for s in self._sessions:
            status = "✓" if s["ended"] else "…"
            print(f"  [{status}] Session {s['id']:>2}  |  "
                  f"Player: {s['player']:<12}  |  "
                  f"Score: {s['score']:>4}  |  "
                  f"Accuracy: {s['accuracy']*100:5.1f}%  |  "
                  f"Duration: {s['duration']}s")
        print("─" * 54 + "\n")


# ── Minimal headless game loop ────────────────────────────────────────────────

class HeadlessDemo:
    """Runs game logic at full speed without any window."""

    def __init__(self, player: str, duration_sec: float):
        self.player      = player
        self.duration    = duration_sec
        self.gesture     = SimulatedGesture(CFG.screen_width, CFG.screen_height)
        self.db          = SimulatedDB()
        self.score       = 0
        self.lives       = CFG.lives_start
        self.hits        = 0
        self.misses      = 0
        self.spawn_rate  = 1.0
        self._objects: list[dict] = []
        self._baskets    = [
            {"x": 0,                         "y": CFG.screen_height - 90,
             "w": CFG.screen_width // 3,      "h": 80, "name": "apple"},
            {"x": CFG.screen_width // 3,      "y": CFG.screen_height - 90,
             "w": CFG.screen_width // 3,      "h": 80, "name": "grape"},
            {"x": (CFG.screen_width // 3) * 2,"y": CFG.screen_height - 90,
             "w": CFG.screen_width // 3,      "h": 80, "name": "orange"},
        ]
        self._last_spawn = time.time()
        self._held: dict | None = None

    def _spawn(self):
        names = ["apple", "grape", "orange"]
        name  = random.choice(names)
        self._objects.append({
            "name": name, "basket": names.index(name),
            "x": random.randint(50, CFG.screen_width - 50),
            "y": 0.0, "speed": 2 * self.spawn_rate,
            "w": 40,  "h": 40,
        })

    def _aabb(self, ax, ay, aw, ah, bx, by, bw, bh) -> bool:
        return (abs(ax - bx) < (aw + bw) / 2 and
                abs(ay - by) < (ah + bh) / 2)

    def run(self):
        self.db.ensure_player(self.player)
        sid   = self.db.start_session(self.player)
        start = time.time()
        frame = 0

        print(f"\n  Demo starting — player: {self.player}  "
              f"duration: {self.duration}s  (headless)\n")

        while time.time() - start < self.duration and self.lives > 0:
            hx, hy, hstate = self.gesture.get_hand_state()
            now = time.time()

            # Spawn
            interval = 3.0 / self.spawn_rate
            if now - self._last_spawn >= interval:
                self._spawn()
                self._last_spawn = now

            # Grab
            if hstate == "CLOSED" and self._held is None:
                for obj in self._objects:
                    if self._aabb(hx, hy, 60, 60,
                                  obj["x"], obj["y"], obj["w"], obj["h"]):
                        self._held = obj
                        break

            # Drop
            if hstate == "OPEN" and self._held is not None:
                obj = self._held
                self._held = None
                dropped = False
                for i, b in enumerate(self._baskets):
                    if self._aabb(obj["x"], obj["y"], obj["w"], obj["h"],
                                  b["x"] + b["w"] // 2, b["y"] + b["h"] // 2,
                                  b["w"], b["h"]):
                        if obj["basket"] == i:
                            self.score += CFG.points_correct
                            self.hits  += 1
                        else:
                            self.lives  -= 1
                            self.misses += 1
                        if obj in self._objects:
                            self._objects.remove(obj)
                        dropped = True
                        break
                if not dropped and obj not in self._objects:
                    self._objects.append(obj)

            # Move held object with hand
            if self._held:
                self._held["x"] = hx
                self._held["y"] = hy

            # Update falling objects
            for obj in self._objects[:]:
                if obj is self._held:
                    continue
                obj["y"] += obj["speed"]
                if obj["y"] > CFG.screen_height:
                    self._objects.remove(obj)
                    self.misses += 1
                    self.lives  -= 1

            # Print progress every second
            if frame % 30 == 0:
                elapsed = time.time() - start
                acc = self.hits / (self.hits + self.misses) \
                      if (self.hits + self.misses) > 0 else 0
                print(f"  t={elapsed:5.1f}s  score={self.score:>4}  "
                      f"lives={self.lives}  acc={acc*100:5.1f}%  "
                      f"hand={hstate:<6}  objects={len(self._objects)}")
            frame += 1
            time.sleep(1 / 30)

        duration = int(time.time() - start)
        accuracy = self.hits / (self.hits + self.misses) \
                   if (self.hits + self.misses) > 0 else 0.0
        self.db.end_session(sid, self.score, accuracy, duration)

        print(f"\n  ── Game over ──")
        print(f"  Final score : {self.score}")
        print(f"  Accuracy    : {accuracy*100:.1f}%")
        print(f"  Duration    : {duration}s")
        print(f"  Feedback    : {self.db.get_adaptive_feedback(self.player)}")
        self.db.print_summary()


# ── PyGame windowed demo ──────────────────────────────────────────────────────

class WindowedDemo:
    """Full-window demo with simulated gesture input, no webcam needed."""

    FRUIT_COLOURS = {
        "apple":  (220, 50,  50),
        "grape":  (80,  50,  200),
        "orange": (255, 160, 20),
    }
    BASKET_COLOURS = [
        (220, 50,  50),
        (80,  50,  200),
        (255, 160, 20),
    ]
    NAMES = ["apple", "grape", "orange"]

    def __init__(self, player: str, duration_sec: float):
        pygame.init()
        self.screen  = pygame.display.set_mode(
            (CFG.screen_width, CFG.screen_height)
        )
        pygame.display.set_caption(
            "Hand Rehabilitation Game — Simulated Demo"
        )
        self.clock   = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("Arial", 26, bold=True)
        self.font_sm = pygame.font.SysFont("Arial", 15)

        self.player   = player
        self.duration = duration_sec
        self.gesture  = SimulatedGesture(CFG.screen_width, CFG.screen_height)
        self.db       = SimulatedDB()

        self.score   = 0
        self.lives   = CFG.lives_start
        self.hits    = 0
        self.misses  = 0
        self.spawn_rate  = 1.0
        self._objects: list[dict] = []
        self._held: dict | None   = None
        self._last_spawn = time.time()
        self._start_time = time.time()
        self._particles: list[dict] = []

        bw = CFG.screen_width  // 3
        bh = 80
        by = CFG.screen_height - bh - 10
        self._baskets = [
            pygame.Rect(0,      by, bw, bh),
            pygame.Rect(bw,     by, bw, bh),
            pygame.Rect(bw * 2, by, bw, bh),
        ]

    def _spawn(self):
        name = random.choice(self.NAMES)
        self._objects.append({
            "name":   name,
            "basket": self.NAMES.index(name),
            "rect":   pygame.Rect(
                random.randint(50, CFG.screen_width - 50), 0, 40, 40
            ),
            "speed": 2.5 * self.spawn_rate,
            "color": self.FRUIT_COLOURS[name],
        })

    def _emit_particles(self, x: int, y: int, color):
        for _ in range(12):
            self._particles.append({
                "x": x, "y": y,
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(-5, -1),
                "life": 1.0,
                "color": color,
            })

    def _update_particles(self):
        for p in self._particles[:]:
            p["x"]    += p["vx"]
            p["y"]    += p["vy"]
            p["vy"]   += 0.15
            p["life"] -= 0.04
            if p["life"] <= 0:
                self._particles.remove(p)

    def _draw_particles(self):
        for p in self._particles:
            alpha = int(p["life"] * 220)
            r, g, b = p["color"]
            pygame.draw.circle(
                self.screen, (r, g, b),
                (int(p["x"]), int(p["y"])), 4
            )

    def run(self):
        self.db.ensure_player(self.player)
        sid      = self.db.start_session(self.player)
        running  = True

        while running:
            dt = self.clock.tick(CFG.fps) / 1000.0
            elapsed = time.time() - self._start_time

            # Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            # Timeout
            if elapsed >= self.duration:
                running = False
            if self.lives <= 0:
                running = False

            # Input
            hx, hy, hstate = self.gesture.get_hand_state()
            glove_rect = pygame.Rect(hx - 30, hy - 30, 60, 60)

            # Spawn
            now = time.time()
            if now - self._last_spawn >= 3.0 / self.spawn_rate:
                self._spawn()
                self._last_spawn = now

            # Grab
            if hstate == "CLOSED" and self._held is None:
                for obj in self._objects:
                    if glove_rect.colliderect(obj["rect"]):
                        self._held = obj
                        break

            # Drop
            if hstate == "OPEN" and self._held is not None:
                obj = self._held
                self._held = None
                for i, basket in enumerate(self._baskets):
                    if obj["rect"].colliderect(basket):
                        if obj["basket"] == i:
                            self.score += CFG.points_correct
                            self.hits  += 1
                            self._emit_particles(
                                obj["rect"].centerx,
                                obj["rect"].centery,
                                obj["color"]
                            )
                        else:
                            self.lives  -= 1
                            self.misses += 1
                        if obj in self._objects:
                            self._objects.remove(obj)
                        break

            # Update objects
            if self._held:
                self._held["rect"].center = (hx, hy)
            for obj in self._objects[:]:
                if obj is self._held:
                    continue
                obj["rect"].y += obj["speed"]
                if obj["rect"].y > CFG.screen_height:
                    self._objects.remove(obj)
                    self.misses += 1
                    self.lives  -= 1

            self._update_particles()

            # Draw
            self.screen.fill(CFG.color_bg)

            # Baskets
            labels = ["Apple", "Grape", "Orange"]
            for i, (basket, col) in enumerate(
                    zip(self._baskets, self.BASKET_COLOURS)):
                pygame.draw.rect(self.screen, col, basket, 3)
                lbl = self.font_sm.render(labels[i], True, col)
                self.screen.blit(lbl, (basket.x + 6, basket.y + 6))

            # Objects
            for obj in self._objects:
                pygame.draw.ellipse(self.screen, obj["color"], obj["rect"])
                t = self.font_sm.render(obj["name"][:3], True, (255,255,255))
                self.screen.blit(t, (obj["rect"].x, obj["rect"].y - 14))

            # Particles
            self._draw_particles()

            # Virtual glove
            gc = CFG.color_green if hstate == "OPEN" else CFG.color_red
            pygame.draw.rect(self.screen, gc, glove_rect, 2)
            gs = self.font_sm.render(hstate, True, gc)
            self.screen.blit(gs, (hx - 20, hy - 28))

            # HUD
            hud = [
                f"Score: {self.score}",
                f"Lives: {self.lives}",
                f"Mode:  DEMO (simulated)",
                f"Time:  {elapsed:.0f} / {self.duration:.0f}s",
            ]
            for j, line in enumerate(hud):
                surf = self.font_lg.render(line, True, CFG.color_black)
                self.screen.blit(surf, (10, 10 + j * 30))

            # Mode label
            ml = self.font_sm.render("Input: SIMULATED", True, CFG.color_black)
            self.screen.blit(ml,
                (CFG.screen_width - ml.get_width() - 10, 10))

            pygame.display.flip()

        duration = int(time.time() - self._start_time)
        accuracy = self.hits / (self.hits + self.misses) \
                   if (self.hits + self.misses) > 0 else 0.0
        self.db.end_session(sid, self.score, accuracy, duration)

        # End screen
        self.screen.fill((15, 20, 35))
        lines = [
            ("DEMO COMPLETE", (56, 189, 248), 36),
            (f"Score     : {self.score}",     (255,255,255), 24),
            (f"Accuracy  : {accuracy*100:.1f}%", (52,211,153), 24),
            (f"Duration  : {duration}s",       (255,255,255), 24),
            (self.db.get_adaptive_feedback(self.player), (148,163,184), 18),
            ("Press ESC or close window to exit", (100,116,139), 16),
        ]
        y = 220
        for text, color, size in lines:
            f = pygame.font.SysFont("Arial", size, bold=(size > 20))
            s = f.render(text, True, color)
            self.screen.blit(s, (CFG.screen_width // 2 - s.get_width() // 2, y))
            y += size + 14
        pygame.display.flip()

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN):
                    waiting = False
            self.clock.tick(30)

        pygame.quit()
        self.db.print_summary()


# ── Analytics chart rendering ─────────────────────────────────────────────────

def show_demo_charts():
    """Render the analytics dashboard with demo data."""
    try:
        import matplotlib
        matplotlib.use("TkAgg" if sys.platform != "linux" else "Agg")
        from src.analytics_dashboard import build_dashboard, _demo_data
        import src.analytics_dashboard as dash
        dash.fetch_history = lambda name: _demo_data(name)
        build_dashboard("Demo Player", save_path=None)
    except Exception as e:
        print(f"[demo] Chart rendering skipped: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hardware-free demo of the Hand Rehabilitation System"
    )
    parser.add_argument("--player",   type=str,  default="DemoPlayer",
                        help="Player name")
    parser.add_argument("--duration", type=float, default=45.0,
                        help="Demo duration in seconds (default 45)")
    parser.add_argument("--headless", action="store_true",
                        help="Run without a window (just prints stats)")
    parser.add_argument("--show-charts", action="store_true",
                        help="Show analytics charts after the game")
    args = parser.parse_args()

    if args.headless or not PYGAME_AVAILABLE:
        demo = HeadlessDemo(args.player, args.duration)
        demo.run()
    else:
        demo = WindowedDemo(args.player, args.duration)
        demo.run()

    if args.show_charts:
        show_demo_charts()
