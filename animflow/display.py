"""Displayer functions."""
import warnings
from typing import Any

#pylint: disable=E0611:no-name-in-module
from PyQt6.QtCore import Qt, QTimer, QMetaType
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QApplication, QWidget
from PyQt6.QtDBus import QDBusInterface, QDBusConnection, QDBusMessage, QDBusArgument

from animflow import Animation, EvalUtils

class QWidgetForWayland(QWidget):
    """I use Wayland. I hate myself. This is made to not installing any extensions.

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

class GBusForWayland(QDBusInterface):
    """Made to be implemented with https://github.com/ickyicky/window-calls"""
    def __init__(self, path = "/org/gnome/Shell/Extensions/Windows",
                       interface = "org.gnome.Shell.Extensions.Windows"):
        super().__init__("org.gnome.Shell", path, interface, QDBusConnection.sessionBus())

        # self-check if the extension is enabled.
        try:
            self._call_method("List")
        except OSError as err:
            raise FileNotFoundError("Window Calls extension is not found.") from err

    def _call_method(self, method_name: str, *args) -> Any:
        """Call GBus with various function"""
        reply = self.call(method_name, *args)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            raise OSError(f"Error: {reply.errorMessage()}")

        arguments = reply.arguments()
        return EvalUtils.safe_json_eval(arguments[0]) if arguments else None

    def get_id(self, qt_id: str) -> str:
        """Sometime it's different so we need to make sure."""
        for window in self._call_method("List"):
            if window.get("title") == qt_id:
                return window.get("id")
        return ""

    def move(self, win_id: str, x: int, y: int):
        """I said move."""
        unsigned_win_id = QDBusArgument()
        unsigned_win_id.add(win_id, QMetaType.Type.UInt.value) # Yeah python sometimes sucks guys.
        self._call_method("Move", unsigned_win_id, x, y)

class Displayer():
    """The displayer.

    ```
    anim = Animation("Path/to/test.tar.xz")
    anim.name = "animation_name" # Its name is currently `test`, we change it to `animation_name`.

    displayer = Displayer()
    displayer.add_animation(anim)

    moving_label = QLabel()
    moving_label.setText("This will be move instead")

    kwargs = {
        "title" = "Never gonna give you up", # Window title, default is `animflow`/
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
        self._app = None
        self.container: QWidget
        self.wayland_id: str = ""

        self.animations: dict = {}
        self.index: int = 0
        self.loop: bool = False
        self.selected: str = ""

    def __str__(self) -> str:
        return f"Displayer(selected='{self.selected}', len(animations)={len(self.animations)}, ...)"

    def __repr__(self) -> str:
        return self.__str__()

    def select_animation(self, animation_name: str, start: int = 0, loop: bool = False) -> bool:
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
            if not start:
                start = animation.attributes.get("start", 0)
            if start < 0:
                start = len(animation.images) + start
            if start >= len(animation.images) or start < 0:
                return False
            self.index: int = start

            if loop:
                self.loop = loop
            else:
                self.loop: bool = animation.attributes.get("loop", False)

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

    def display(self, title: str = "animflow",
                      delay: float = 100,
                      animation_name: str = "",
                      auto_shutdown: bool = True,
                      container: QWidget | None = None,
                      move_widget: QWidget | None = None) -> int:
        """Doing its purpose. See `Displayer` for detail examples.

        Implement for Wayland: https://github.com/ickyicky/window-calls.
        See `GBusForWayland` for more information.

        Args:
            title (str, optional): The window title.
            delay (float, optional): Delay for the next frame in ms.
            animation_name (str, optional): Select another starting animation.
            auto_shutdown (bool, optional): Shutdown itself when animation is done. Default is True.
            container (QWidget | None, optional): Custom widget for container.
            move_widget (QWidget | None, optional): Different QWidget that will be move instead.
        """
        def _update(gbus: GBusForWayland | None):
            if move_widget is None:
                return
            self.index += 1
            animation: Animation = self.animations[self.selected]
            if self.loop and self.index == len(animation.images):
                self.index = 0
            try:
                x, y = animation.location[self.index]

                if gbus:
                    if move_widget and move_widget.windowTitle() == str(int(move_widget.winId())):
                        self.wayland_id = gbus.get_id(str(int(move_widget.winId())))
                        move_widget.setWindowTitle(title)
                    gbus.move(self.wayland_id,
                              *EvalUtils.location_format(x, y, animation.attributes))
                else:
                    move_widget.move(*EvalUtils.location_format(x, y, animation.attributes))

                label.setPixmap(QPixmap.fromImage(animation.images[self.index]))
                move_widget.adjustSize()
            except IndexError:
                timer.stop()
                if auto_shutdown:
                    label.close()
                    label.deleteLater()
                    if hasattr(self, "container") and self.container:
                        self.container.close()
                        self.container.deleteLater()

        if not self.animations:
            return 1
        if self.selected not in self.animations:
            self.selected = tuple(self.animations.keys())[0]
        self.select_animation(animation_name if animation_name else self.selected)

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        self._app = app

        label = QLabel(flags=Qt.WindowType.FramelessWindowHint)
        label.show()
        gbus = None
        if container and isinstance(container, QWidget):
            self.container = container
            label.setParent(container)
        elif QApplication.platformName().lower().startswith("wayland"): # Using wayland.
            try:
                gbus = GBusForWayland()
            except FileNotFoundError:
                gbus = None
                warnings.warn("Detected using Wayland, it is recommended to install "
                              "`Window Calls extension` for a more intuitive experience. "
                              "Link: https://github.com/ickyicky/window-calls.")
                self.container = QWidgetForWayland()
                label.setParent(self.container)
        if hasattr(self, "container"):
            self.container.show()

        animation: Animation = self.animations[self.selected]
        x, y = animation.location[self.index]

        if not move_widget:
            move_widget = label
        if gbus:
            move_widget.setWindowTitle(str(int(move_widget.winId())))

        label.setPixmap(QPixmap.fromImage(animation.images[self.index]))
        # Gbus wayland isn't updated yet. So we skip this here!
        move_widget.move(*EvalUtils.location_format(x, y, animation.attributes))
        move_widget.adjustSize()

        timer = QTimer()
        timer.timeout.connect(lambda gbus=gbus: _update(gbus))
        timer.start(100 if delay < 0 else int(delay))

        return app.exec()

def main():
    "Displaying"
    #pylint:disable=C0412:ungrouped-imports C0415:import-outside-toplevel
    from PyQt6.QtWidgets import QFileDialog
    from pathlib import Path

    _ = QApplication([])
    displayer = Displayer()

    file_paths, _ = QFileDialog.getOpenFileNames(caption="Select animations")
    if not file_paths:
        raise OSError("Please select files to display.")

    for file_path in file_paths:
        anim = Animation(Path(file_path))
        displayer.add_animation(anim)

    displayer.display()

if __name__ == "__main__":
    main()
