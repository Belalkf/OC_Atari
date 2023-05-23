# appends parent path to syspath to make ocatari importable
# like it would have been installed as a package
import sys
import random
import matplotlib.pyplot as plt
sys.path.insert(0, '../../') # noqa

from ocatari.core import OCAtari
from ocatari.vision.utils import mark_bb, make_darker
from ocatari.utils import load_agent, parser

game_name = "Qbert"
MODE = "vision"
MODE = "revised"
HUD = True
env = OCAtari(game_name, mode=MODE, hud=HUD, render_mode='rgb_array')
observation, info = env.reset()

prevRam = None

opts = parser.parse_args()

if opts.path:
    agent = load_agent(opts, env.action_space.n)

for i in range(10000):
    # for j in range(5):
    #     env._env.unwrapped.ale.setRAM(75+j, 3)

    env._env.unwrapped.ale.setRAM(36, 1)
    if opts.path is not None:
        action = agent.draw_action(env.dqn_obs)
    else:
        if i < 95:
            action = 3  # random.randint(0, 5)
        else:
            action = 0
    obs, reward, terminated, truncated, info = env.step(action)
    ram = env._env.unwrapped.ale.getRAM()
    if i % 10 == 0 and i > 50:
        # print(env.objects)
        print(ram[105])
        # print(ram[75:80])
        # if prevRam is not None:
        #     for i in range(len(ram)):
        #         if ram[i] != prevRam[i]:
        #             pad = "           "
        #             for u in range(4 - len(str(i))):
        #                 pad += " "
        #             print(str(i) + pad + "value:" + str(ram[i]) + pad + " was previously " + str(prevRam[i]))
        # print("------------------------------------------")
        # prevRam = ram
        for obj in env.objects:
            x, y = obj.xy
            if x < 160 and y < 210:
                opos = obj.xywh
                ocol = obj.rgb
                sur_col = make_darker(ocol)
                mark_bb(obs, opos, color=sur_col)
        plt.imshow(obs)
        plt.show()
    if terminated or truncated:
        observation, info = env.reset()
env.close()