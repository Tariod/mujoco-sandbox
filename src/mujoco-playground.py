import mujoco
import mediapy as media
import numpy as np

xml = """
<mujoco>
  <worldbody>
    <body name="box_and_sphere" euler="0 0 -30">
      <joint name="swing" type="hinge" axis="0 1 0" pos="0 0 1" />
      <geom name="cord" type="cylinder" size=".02 1" mass="0" />
      <geom name="bob" type="sphere" pos="0 0 -1" mass="1" size=".1" />
    </body>
  </worldbody>
</mujoco>
"""
# xml = """
# <mujoco>
#   <worldbody>
#     <body name="box_and_sphere" euler="0 0 -30">
#       <joint name="swing" type="hinge" axis="1 -1 0" pos="-.2 -.2 -.2" />
#       <geom name="box" type="box" size=".2 .2 .2" />
#     </body>
#   </worldbody>
# </mujoco>
# """
model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

data.qpos = np.ones_like(data.qpos) * np.pi / 2

renderer = mujoco.Renderer(model)

scene_option = mujoco.MjvOption()

scene_option.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = True

duration = 2  # (seconds)
framerate = 60  # (Hz)

frames = []
while data.time < duration:
    mujoco.mj_step(model, data)

    if len(frames) < data.time * framerate:
        renderer.update_scene(data, scene_option=scene_option)
        pixels = renderer.render()
        frames.append(pixels)

# Simulate and display video.
media.write_video("./mujoco-playground.mp4", frames, fps=framerate)
