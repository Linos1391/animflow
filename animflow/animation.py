"""Animation class."""
import json
from pathlib import Path
import tarfile
import tempfile

from PIL import Image, ImageSequence, ImageQt

from animflow import Constant

class Animation:
    """The animation. See `Displayer` for more details.

    Args:
        path (Path): Path to file.
        start (int, optional): Index where the animation start, can be negative.
        loop (bool, optional): To loop the animation or not, default is not to.
    """
    def __init__(self, path: Path, **kwargs) -> None:
        self.attributes: dict = {}
        self.name: str = ""
        self.images: list[ImageQt.ImageQt] = []
        self.location: list[tuple[str, str]] = []

        self.load(path, **kwargs)

    def load(self, path: Path, **kwargs) -> None:
        """Check file's integrity. Can be used to add more frame.

        Args:
            path (Path): Path to file.
            start (int, optional): Index where the animation start, can be negative.
            loop (bool, optional): To loop the animation or not, default is not to.
        """
        compatible_error_str: str = Constant.COMPATIBLE_ERROR.format(name=self.name)

        if not self.name:
            self.name = path.stem

        tmpdir = None
        if path.name.endswith(".tar.xz") and path.exists(): # Extracting if needed.
            tmpdir = tempfile.TemporaryDirectory()
            animation_path = Path(tmpdir.name) / self.name
            animation_path.mkdir(parents=True, exist_ok=True)
            with tarfile.open(path, mode="r:xz") as tar:
                tar.extractall(animation_path)
            path = animation_path
        elif not path.is_dir():
            raise OSError(compatible_error_str)

        # Check it.
        try:
            with open(path / Constant.JSON_FILE, "r", encoding="utf-8") as f:
                json_data: dict = json.load(f)
                f.close()
            images_data: list = json_data.pop("images")
        except (FileExistsError, KeyError) as err:
            raise OSError(compatible_error_str) from err
        self.attributes = json_data
        self.attributes.update(kwargs)

        images: dict[str, dict] = {}
        for frame in images_data:
            if not all((isinstance(frame.get("index"), int),
                        frame.get("file"), frame.get("location"))):
                raise OSError(compatible_error_str)

            self.location.append(frame.get("location"))
            try:
                self.images.append(ImageQt.ImageQt(
                                                images[frame.get("file")].pop(frame.get("index"))))
            except KeyError:
                try:
                    files = {k: v for k, v in enumerate(ImageSequence.all_frames(
                                                Image.open(path / frame.get("file"))))}
                    self.images.append(ImageQt.ImageQt(files.pop(frame.get("index"))))
                except (FileNotFoundError, KeyError) as err:
                    raise OSError(compatible_error_str) from err
                images.update({frame.get("file"): files})
                del files
        if tmpdir and path.name.endswith(".tar.xz"):
            tmpdir.cleanup()
