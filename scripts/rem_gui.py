import gymnasium as gym
import numpy as np
from matplotlib import pyplot as plt
from tqdm import tqdm
import pygame
from ocatari.core import OCAtari, UPSCALE_FACTOR
from gymnasium.error import NameNotFound

"""
This script can be used to identify any RAM positions that
influence the color of a specific pixel. This can be used to
identify the values that belong to a GameObject.
"""


import pygame
from ocatari.core import OCAtari, DEVICE
import numpy as np
import torch
import cv2
import random


get_bin = lambda x: format(x, 'b').zfill(8)



RAM_RENDER_WIDTH = 1000
RAM_N_COLS = 8
RAM_CELL_WIDTH = 115
RAM_CELL_HEIGHT = 45


class Renderer:
    window: pygame.Surface
    clock: pygame.time.Clock
    env: gym.Env

    def __init__(self, env_name: str):
        try:
            self.env = OCAtari(env_name, mode="revised", hud=True, render_mode="rgb_array",
                            render_oc_overlay=True, frameskip=1)
        except NameNotFound:
            self.env = gym.make(env_name, render_mode="rgb_array", frameskip=1)
        self.env.reset(seed=42)[0]
        self.current_frame = self.env.render()
        self._init_pygame(self.current_frame)
        self.paused = False

        self.current_keys_down = set()
        self.current_mouse_pos = None
        self.keys2actions = self.env.unwrapped.get_keys_to_action()

        self.ram_grid_anchor_left = self.env_render_shape[0] + 28
        self.ram_grid_anchor_top = 28

        self.active_cell_idx = None
        self.candidate_cell_ids = []
        self.current_active_cell_input : str = ""

    def _init_pygame(self, sample_image):
        pygame.init()
        pygame.display.set_caption("OCAtari Environment")
        self.env_render_shape = sample_image.shape[:2]
        window_size = (self.env_render_shape[0] + RAM_RENDER_WIDTH, self.env_render_shape[1])
        self.window = pygame.display.set_mode(window_size)
        self.clock = pygame.time.Clock()
        self.ram_cell_id_font = pygame.font.SysFont('Pixel12x10', 16)
        self.ram_cell_value_font = pygame.font.SysFont('Pixel12x10', 30)

    def run(self):
        self.running = True
        while self.running:
            self._handle_user_input()
            if not self.paused:
                action = self._get_action()
                tuple = self.env.step(action)
                rew = tuple[1]
                if rew != 0:
                    print(rew)
                self.current_frame = self.env.render().copy()
            self._render()
        pygame.quit()

    def _get_action(self):
        pressed_keys = list(self.current_keys_down)
        pressed_keys.sort()
        pressed_keys = tuple(pressed_keys)
        if pressed_keys in self.keys2actions.keys():
            return self.keys2actions[pressed_keys]
        else:
            return 0  # NOOP

    def _handle_user_input(self):
        self.current_mouse_pos = np.asarray(pygame.mouse.get_pos())

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:  # window close button clicked
                self.running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # left mouse button pressed
                    x = self.current_mouse_pos[0] // UPSCALE_FACTOR
                    y = self.current_mouse_pos[1] // UPSCALE_FACTOR
                    if x < 160:
                        self.find_causative_ram(x, y)
                    else:
                        self.active_cell_idx = self._get_cell_under_mouse()
                        self.current_active_cell_input = ""
                elif event.button == 4:  # mousewheel up
                    cell_idx = self._get_cell_under_mouse()
                    if cell_idx is not None:
                        self._increment_ram_value_at(cell_idx)
                elif event.button == 5:  # mousewheel down
                    cell_idx = self._get_cell_under_mouse()
                    if cell_idx is not None:
                        self._decrement_ram_value_at(cell_idx)

            elif event.type == pygame.KEYDOWN:  # keyboard key pressed
                if event.key == pygame.K_p:  # 'P': pause/resume
                    self.paused = not self.paused

                if event.key == pygame.K_r:  # 'R': reset
                    self.env.reset()

                elif event.key == pygame.K_ESCAPE and self.active_cell_idx is not None:
                    self._unselect_active_cell()

                elif (event.key,) in self.keys2actions.keys():  # env action
                    self.current_keys_down.add(event.key)

                elif pygame.K_0 <= event.key <= pygame.K_9:  # enter digit
                    char = str(event.key - pygame.K_0)
                    if self.active_cell_idx is not None:
                        self.current_active_cell_input += char

                elif pygame.K_KP1 <= event.key <= pygame.K_KP0:  # enter digit
                    char = str((event.key - pygame.K_KP1 + 1) % 10)
                    if self.active_cell_idx is not None:
                        self.current_active_cell_input += char

                elif event.key == pygame.K_BACKSPACE:  # remove character
                    if self.active_cell_idx is not None:
                        self.current_active_cell_input = self.current_active_cell_input[:-1]

                elif event.key == pygame.K_RETURN:
                    if self.active_cell_idx is not None:
                        if len(self.current_active_cell_input) > 0:
                            new_cell_value = int(self.current_active_cell_input)
                            if new_cell_value < 256:
                                self._set_ram_value_at(self.active_cell_idx, new_cell_value)
                        self._unselect_active_cell()

            elif event.type == pygame.KEYUP:  # keyboard key released
                if (event.key,) in self.keys2actions.keys():
                    self.current_keys_down.remove(event.key)

    def _render(self, frame = None):
        self.window.fill((0,0,0))  # clear the entire window
        self._render_atari(frame)
        self._render_ram()
        self._render_hover()
        pygame.display.flip()
        pygame.event.pump()

    def _render_atari(self, frame = None):
        if frame is None:
            frame = self.current_frame
        frame_surface = pygame.Surface(self.env_render_shape)
        pygame.pixelcopy.array_to_surface(frame_surface, frame)
        self.window.blit(frame_surface, (0, 0))
        self.clock.tick(60)

    def _render_ram(self):
        ale = self.env.unwrapped.ale
        ram = ale.getRAM()

        for i, value in enumerate(ram):
            self._render_ram_cell(i, value)

    def _get_ram_value_at(self, idx: int):
        ale = self.env.unwrapped.ale
        ram = ale.getRAM()
        return ram[idx]

    def _set_ram_value_at(self, idx: int, value: int):
        ale = self.env.unwrapped.ale
        ale.setRAM(idx, value)
        # self.current_frame = self.env.render()
        # self._render()

    def _set_ram(self, values):
        ale = self.env.unwrapped.ale
        for k, value in enumerate(values):
            ale.setRAM(k, value)

    def _increment_ram_value_at(self, idx: int):
        value = self._get_ram_value_at(idx)
        self._set_ram_value_at(idx, min(value + 1, 255))

    def _decrement_ram_value_at(self, idx: int):
        value = self._get_ram_value_at(idx)
        self._set_ram_value_at(idx, max(value - 1, 0))

    def _render_ram_cell(self, cell_idx, value):
        is_active = cell_idx == self.active_cell_idx
        is_candidate = cell_idx in self.candidate_cell_ids

        x, y, w, h = self._get_ram_cell_rect(cell_idx)

        # Render cell background
        if is_active:
            color = (70, 70, 30)
        elif is_candidate:
            color = (15, 45, 100)
        else:
            color = (20, 20, 20)
        pygame.draw.rect(self.window, color, [x, y, w, h])

        # Render cell ID label
        if is_active:
            color = (150, 150, 30)
        elif is_candidate:
            color = (20, 60, 200)
        else:
            color = (50, 50, 50)
        text = self.ram_cell_id_font.render(str(cell_idx), True, color, None)
        text_rect = text.get_rect()
        text_rect.topleft = (x + 2, y + 2)
        self.window.blit(text, text_rect)

        # Render cell value label
        if is_active:
            value = self.current_active_cell_input
        if value is not None:
            if is_active:
                color = (255, 255, 50)
            elif is_candidate:
                color = (30, 90, 255)
            else:
                color = (200, 200, 200)
            text = self.ram_cell_value_font.render(str(value), True, color, None)
            # text = self.ram_cell_value_font.render(get_bin(value), True, color, None)
            text_rect = text.get_rect()
            text_rect.bottomright = (x + w - 2, y + h - 2)
            self.window.blit(text, text_rect)

    def _get_ram_cell_rect(self, idx: int):
        row = idx // RAM_N_COLS
        col = idx % RAM_N_COLS
        x = self.ram_grid_anchor_left + col * 120
        y = self.ram_grid_anchor_top + row * 50
        w = RAM_CELL_WIDTH
        h = RAM_CELL_HEIGHT
        return x, y, w, h

    def _render_hover(self):
        cell_idx = self._get_cell_under_mouse()
        if cell_idx is not None and cell_idx != self.active_cell_idx:
            x, y, w, h = self._get_ram_cell_rect(cell_idx)
            hover_surface = pygame.Surface((w, h))
            hover_surface.set_alpha(60)
            hover_surface.set_colorkey((0, 0, 0))
            pygame.draw.rect(hover_surface, (255, 255, 255), [0, 0, w, h])
            self.window.blit(hover_surface, (x, y))

    def _get_cell_under_mouse(self):
        x, y = self.current_mouse_pos
        if x > self.ram_grid_anchor_left and y > self.ram_grid_anchor_top:
            col = (x - self.ram_grid_anchor_left) // 120
            row = (y - self.ram_grid_anchor_top) // 50
            if col < RAM_N_COLS and row < 16:
                return row * RAM_N_COLS + col
        return None

    def _unselect_active_cell(self):
        self.active_cell_idx = None
        self.current_active_cell_input = ""

    def find_causative_ram(self, x, y):
        """
        Goes over the entire RAM, manipulating it to observe possible changes
        in the current observation. Prints the RAM entry positions that are responsible
        for changes at pixel x, y.
        """
        ale = self.env.unwrapped.ale
        sys_state = ale.cloneSystemState()
        ram = ale.getRAM().copy()
        self.env.step(0)
        original_pixel = ale.getScreenRGB()[y, x]
        self._set_ram(ram)  # restore original RAM

        self.candidate_cell_ids = []
        for i in tqdm(range(len(ram))):
            self.active_cell_idx = i
            for altered_value in [0]:  # adding values != 0 causes Atari to crash
                self.current_active_cell_input = str(altered_value)
                ale.setRAM(i, altered_value)
                self.env.step(0)
                new_frame = ale.getScreenRGB()
                self._render()
                new_pixel = new_frame[y, x]
                self._set_ram(ram)  # restore original RAM
                ale.restoreSystemState(sys_state)
                if np.any(new_pixel != original_pixel):
                    self.candidate_cell_ids.append(i)
                    break

        self._unselect_active_cell()
        self._render()


if __name__ == "__main__":
    # renderer = Renderer("Pong")
    # renderer = Renderer("DemonAttack")
    renderer = Renderer("ALE/Pacman-v5")
    renderer.run()
