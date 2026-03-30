"""Animation class."""
import json
import os
import tarfile
import tempfile

from PIL import Image, ImageSequence, ImageQt

class Animation:
    """The animation. See `Displayer` for more details.

    Args:
        path (str): Path to file.
        start (int, optional): Index where the animation start, can be negative.
        loop (bool, optional): To loop the animation or not, default is not to.
    """
    def __init__(self, path: str, **kwargs) -> None:
        self.attributes: dict = {}
        self.name: str = ""
        self.images: list[ImageQt.ImageQt] = []
        self.location: list[tuple[str, str]] = []

        self.load(path, **kwargs)

    def load(self, path: str, **kwargs) -> None:
        """Check file's integrity. Can be used to add more frame.

        Args:
            path (str): Path to file.
            start (int, optional): Index where the animation start, can be negative.
            loop (bool, optional): To loop the animation or not, default is not to.
        """
        _, filename = os.path.split(path)
        if not self.name:
            self.name = filename.split(".")[0]

        tmpdir = None
        if filename.endswith(".tar.xz") and os.path.exists(path): # Extracting if needed.
            tmpdir = tempfile.TemporaryDirectory()
            animation_path = os.path.join(tmpdir.name, self.name)
            os.makedirs(animation_path)
            with tarfile.open(path, mode="r:xz") as tar:
                tar.extractall(animation_path)
            path = animation_path
        elif not os.path.isdir(path):
            raise OSError(f"Animation {self.name} isn't compatible.")

        # Check it.
        with open(os.path.join(path, f"{self.name}.json"), "r", encoding="utf-8") as f:
            json_data: dict = json.load(f)
            f.close()

        try:
            images_data: list = json_data.pop("images")
        except KeyError as err:
            raise OSError(f"Animation {self.name} isn't compatible.") from err
        self.attributes = json_data
        self.attributes.update(kwargs)

        images: dict[str, dict] = {}
        for frame in images_data:
            if not all((isinstance(frame.get("index"), int),
                        frame.get("file"), frame.get("location"))):
                raise OSError(f"Animation {self.name} isn't compatible.")

            self.location.append(frame.get("location"))
            try:
                self.images.append(ImageQt.ImageQt(
                                                images[frame.get("file")].pop(frame.get("index"))))
            except KeyError:
                try:
                    files = {k: v for k, v in enumerate(ImageSequence.all_frames(
                                                Image.open(os.path.join(path, frame.get("file")))))}
                    self.images.append(ImageQt.ImageQt(files.pop(frame.get("index"))))
                except (FileNotFoundError, KeyError) as err:
                    raise OSError(f"Animation {self.name} isn't compatible.") from err
                images.update({frame.get("file"): files})
                del files
        if tmpdir and filename.endswith(".tar.xz"):
            tmpdir.cleanup()
