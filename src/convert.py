"""Converter function."""
import json
import tarfile
import tempfile
import os
from collections.abc import Generator

from PIL import Image, ImageSequence

class Converter:
    """The converter."""

    def __init__(self) -> None:
        self.attributes: dict = {}
        self.images: list[Image.Image] = []
        self.location: dict[int, tuple[str, str]] = {}

    # So many errors, so many frames. Maybe convert your video to gif via 3rd parties?
    #
    # def _convert_video(self, path: str) -> bool:
    #     """Convert video into native map data."""
    #     file = cv2.VideoCapture(path) #pylint: disable=E1101:no-member

    #     if file.isOpened():
    #         while True:
    #             ret, frame = file.read()
    #             if not ret:
    #                 break
    #             self.images.append(Image.fromarray(frame).convert("RGB"))
    #         file.release()
    #         return True
    #     else:
    #         return False

    def _convert_image_or_sequences(self, path: str) -> bool:
        """Convert image or image sequences into native map data."""
        try:
            file = Image.open(path)
            self.images += ImageSequence.all_frames(file, func=lambda img: img.convert("RGB"))
            return True
        except (SyntaxError, OSError):
            return False

    def set_location(self, index: int, x: str, y: str):
        """Set a location on a specific frame.

        Static location.
        ```
        converter.set_location(0, "100", "100")
        ```

        Dynamic location.
        ```
        converter.attributes.update({
            "cur_x": 100,
            "cur_y": 200,
        })
        converter.set_location(0, "{cur_x} + 100", "{cur_y} + 100")
        ```

        Args:
            index (int): Frame's index.
            x (str): x location.
            y (str): y location.
        """
        self.location.update({index: (x, y)})

    def add_map(self, path: str) -> None:
        """Add the file data to the converter. Only support images and gif.
        See `save_map()` for example.

        Args:
            path (str): path to file.
        """

        if not self._convert_image_or_sequences(path):
            raise OSError("Unable to read file.")

    def save_map(self, name: str, parent_path: str = '', archive: bool = True, **kwargs)\
            -> Generator[FileExistsError | None]:
        """Save the image map. 

        ```
        converter = Converter()
        converter.add_map("Path/to/file.gif")

        for result in converter.save_map("test", "Path/to/directory"):
            if isinstance(result, FileExistsError):
                if input(f"{result} exists. Overwrite? [y/N] ").lower() != "y":
                    break
        ```


        Args:
            name (str): Name of the animation.
            parent_path (str): Path that lead to saved animation.
            archive (bool): To archive everything as `tar.xz`.
            **kwargs

        Yields:
            Generator[OSError | None]: Yield `FileExistsError` if error occurred, `None` if success.
        """
        name = name.split(".")[0]
        tmpdir = None
        if archive:
            tmpdir = tempfile.TemporaryDirectory()
            animation_path: str = os.path.join(tmpdir.name, name)
            os.makedirs(parent_path, exist_ok=True)
            os.makedirs(animation_path, exist_ok=True)
        else:
            animation_path: str = os.path.join(parent_path, name)
            try:
                os.makedirs(animation_path)
            except OSError:
                yield FileExistsError(animation_path)

        data: list = []
        save_index: int = 0 # the index for gif name.
        same_index: int = 0 # index for images that saved as gif together.
        previous_dimension: tuple = self.images[0].size

        for cur_index, img in enumerate(self.images):
            if img.size == previous_dimension:
                data.append({
                    "index": same_index,
                    "file": f"{save_index}.webp",
                    "location": self.location.get(cur_index, ("0", "0"))
                })
                same_index += 1

            else:
                # Different! Save the previous as gif!
                _start: int = cur_index-same_index
                self.images[_start].save( os.path.join(animation_path, f"{save_index}.webp"),
                        save_all=True, quality=90, append_images=self.images[_start+1:cur_index])

                previous_dimension = self.images[cur_index].size
                same_index = 1
                save_index += 1
                data.append({
                    "index": 0,
                    "file": f"{save_index}.webp",
                    "location": self.location.get(cur_index, ("0", "0"))
                })
        _start: int = len(self.images)-same_index
        self.images[_start].save( os.path.join(animation_path, f"{save_index}.webp"),
                                save_all=True, quality=90, append_images=self.images[_start+1:])

        attributes = self.attributes
        attributes.update({"images": data}, **kwargs)
        with open(os.path.join(animation_path, f"{name}.json"), mode="w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=4)
            f.close()

        if archive:
            #cspell:ignore tarpath
            tarpath: str = os.path.join(parent_path, f"{name}.tar.xz")
            if os.path.exists(tarpath):
                yield FileExistsError(tarpath)

            with tarfile.open((tarpath), "w:xz") as tar:
                tar.add(os.path.join(animation_path, f"{name}.json"), f"{name}.json")
                for index in range(save_index+1):
                    tar.add(os.path.join(animation_path, f"{index}.webp"), f"{index}.webp")
                if tmpdir:
                    tmpdir.cleanup()

if __name__ == "__main__":
    converter = Converter()
    converter.add_map("/home/linos1391/Downloads/giphy.gif")

    for result in converter.save_map("test", "/home/linos1391/Downloads/animflow", archive=True):
        if isinstance(result, FileExistsError):
            if input(f"{result} exists. Overwrite? [y/N] ").lower() != "y":
                break
