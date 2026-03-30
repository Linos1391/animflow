"""Displayer functions."""
import warnings
import ast
import operator

#pylint: disable=E0611:no-name-in-module
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QApplication, QWidget

try:
    from animation import Animation
except ImportError:
    from .animation import Animation

class QWidgetForWayland(QWidget):
    """I use Wayland. I hate myself.

    Wayland until I catch u mfs. Why GNOME fedora? Why? For security? Now secure ur house mfs.

    ```
    displayer = Displayer()
    displayer.add_animation(anim)
    displayer.display(container=QWidgetForWayland())
    ```
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        #pylint: disable=C0301:line-too-long
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setGeometry(app.primaryScreen().geometry()) # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]

class Displayer():
    """The displayer.

    ```
    anim = Animation("Path/to/test.tar.xz")
    anim.name = "animation_name" # Its name is currently `test`, we change it to `animation_name`.

    displayer = Displayer()
    displayer.add_animation(anim)

    moving_label = QLabel()
    moving_label.setText("This will be move")

    kwargs = {
        "delay" = 300, # Delay in 300ms.
        "animation" = "animation_name", # Start with animation `animation_name`.
        "auto_shutdown" = True, # Will shutdown itself when the program is done.
        "container" = CustomQWidget(), # A class object from QWidget.
        "move_widget" = moving_label, # A class object with will be move instead of default window.
    }
    displayer.display(**kwargs)
    ```
    """
    def __init__(self) -> None:
        self.container: QWidget | None = None
        self._app = None

        self.animations: dict = {}
        self.index: int = 0
        self.loop: bool = False
        self.selected: str = ""

    @staticmethod
    def _safe_math_eval(expr, **kwargs) -> int:
        """I do not trust you guys. I will not trust you guys.
        Add to `**kwargs` yourself and rethink the consequences.
        """
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            **kwargs
        }

        def eval_node(node) -> int | float:
            if isinstance(node, ast.BinOp):  # Binary operations
                left = eval_node(node.left)
                right = eval_node(node.right)
                op_func = operators.get(type(node.op))
                if op_func:
                    return op_func(left, right)
                else:
                    raise TypeError(f"Unsupported operator: {type(node.op)}")
            elif isinstance(node, ast.UnaryOp):  # Unary operations
                operand = eval_node(node.operand)
                op_func = operators.get(type(node.op))
                if op_func:
                    return op_func(operand)
                else:
                    raise TypeError(f"Unsupported unary operator: {type(node.op)}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):  # Numbers
                return node.value
            else:
                raise TypeError(f"Unsupported node type: {type(node).__name__}")

        tree = ast.parse(expr, mode='eval')
        return int(eval_node(tree.body))

    def select_animation(self, animation_name: str, **kwargs) -> bool:
        """Select animation to display in real time.
        Tips: Use debugger to find error if False returned.

        Args:
            animation_name (str): The name.
            start (int, optional): Index where the animation start, can be negative.
            loop (bool, optional): To loop the animation or not, default is not to.

        Returns:
            bool: Found animation and select successfully.
        """
        animation: None | Animation = self.animations.get(animation_name)
        if isinstance(animation, Animation):
            attributes = animation.attributes
            attributes.update(kwargs)

            start: int = attributes.get("start", 0)
            if start < 0:
                start = len(animation.images) + start
            if start >= len(animation.images) or start < 0:
                return False

            self.index: int = start
            self.loop: bool = attributes.get("loop", False)
            self.selected = animation_name
            return True
        return False

    def add_animation(self, animation: Animation, replace: bool = False) -> None:
        """Add animation to the displayer.

        Args:
            animation (Animation): The animation.
            replace (bool): To replace the current animation.
        """
        if not replace and animation.name in self.animations:
            warnings.warn(f"Animation {animation.name} exists. It will be renamed automatically.")
            sub_index = animation.name.rfind("_")

            if sub_index == -1 or animation.name.endswith("_"):
                animation.name += "_0"
            else:
                try:
                    order = int(animation.name[sub_index+1:])
                except TypeError:
                    animation.name += "_0"
                else:
                    animation.name += f"_{order}"
        self.animations.update({animation.name: animation})
        if self.selected not in self.animations:
            self.select_animation(animation.name)

    def display(self, **kwargs) -> int:
        """Doing its purpose. See `Displayer` for detail examples.

        Args:
            delay (float, optional): Delay for the next frame in ms.
            animation (str, optional): Select another starting animation.
            auto_shutdown (bool, optional): Shutdown itself when animation is done. Default is True.
            container (QWidget, optional): Custom widget for container.
            move_widget (QWidget, optional): QWidget that will be move.
        """
        def _update():
            self.index += 1
            animation: Animation = self.animations[self.selected]
            if self.loop and self.index == len(animation.images):
                self.index = 0
            try:
                x, y = animation.location[self.index]
                kwargs.get("move_widget", label).move(
                                self._safe_math_eval(x.format_map(animation.attributes)),
                                self._safe_math_eval(y.format_map(animation.attributes)))
                label.setPixmap(QPixmap.fromImage(animation.images[self.index]))
                label.adjustSize()
            except IndexError:
                timer.stop()
                if kwargs.get("auto_shutdown", True) and isinstance(self.container, QWidget):
                    self.container.close() # pyright: ignore[reportOptionalMemberAccess]
                    self.container.deleteLater() # pyright: ignore[reportOptionalMemberAccess]
                    self.container = None

        if not self.animations:
            return 1
        if self.selected not in self.animations:
            self.selected = tuple(self.animations.keys())[0]
        self.select_animation(kwargs.get("animation", self.selected))

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        self._app = app
        self.container = kwargs.get("container", QWidget())
        if not isinstance(self.container, QWidget):
            return 1

        label = QLabel(self.container)
        animation: Animation = self.animations[self.selected]
        x, y = animation.location[self.index]
        label.move(self._safe_math_eval(x.format_map(animation.attributes)),
                   self._safe_math_eval(y.format_map(animation.attributes)))
        label.setPixmap(QPixmap.fromImage(animation.images[self.index]))
        label.adjustSize()
        label.show()
        self.container.show()

        timer = QTimer()
        timer.timeout.connect(_update)
        timer.start(kwargs.get('delay', 100))  # Update every 1 second

        return app.exec()

if __name__ == "__main__":
    anim = Animation("/home/linos1391/Downloads/animflow/test.tar.xz")

    _ = QApplication([])

    displayer = Displayer()
    displayer.add_animation(anim)
    displayer.display(container=QWidgetForWayland())
