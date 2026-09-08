# animflow

```
pip install animflow
```

## Come inside:
- Fully customizable way of displaying and storing animation:
  - Utilize custom animation *for drawing enjoyer*.
  - Utilize `{key}` *for pivoting enjoyer*.
  - Utilize zipping *for enterprising enjoyer*.

## Tutorial

First of all, make animations via `convert.py` file.

### Socket

Make an animflow socket server. Type into your terminal:

```bash
animflow --animation "Path/to/animation"
```

Then, on another python file.

```python
from animflow.parser import _test_connector

_test_connector()

# Basic example CLI for this:
# ---------------------------
# cmd: HELP
# cmd: SHOW
# cmd: SELECT {"animation_name": "(Your animation)"}
```

<br>

### Pure Python

```python
anim = Animation("Path/to/test.tar.xz")
anim.name = "animation_name" # Its name is currently `test`, we change it to `animation_name`.

displayer = Displayer()
displayer.add_animation(anim)

moving_label = QLabel()
moving_label.setText("This will be move instead")

# All kwargs below are optional.
kwargs = {
    "title" = "Never gonna give you up", # Window title, default is `animflow`
    "delay" = 300, # Delay in 300ms.
    "animation" = "animation_name", # Start with animation `animation_name`.
    "auto_shutdown" = True, # Will shutdown itself when the program is done.
    "container" = CustomQWidget(), # A class object from QWidget.
    "move_widget" = moving_label, # A class object with will be move instead of default window.
    "run_event_loop" = True, # Run the Qt event loop, meaning it will block the main thread
}
displayer.display(**kwargs)
```