"""Converter function."""
import json
import tarfile
import tempfile
from pathlib import Path
import os
from collections.abc import Generator

import imgcompare
import cv2
from PIL import Image, ImageSequence

from animflow import EvalUtils, Constant

class Converter:
    """The converter."""

    def __init__(self) -> None:
        self.attributes: dict = {}
        self.frames: list[dict] = []
        # [
        #     {"image": Image.Image | int,
        #      "location": (str, str)},
        #     ...
        # ]

    def reset(self):
        """For a brand new start."""
        self.attributes = {}
        self.frames = []

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
        try:
            self.frames[index].update({"location": (x, y)})
        except IndexError as err:
            raise IndexError(f"Index receive is {index} when the maximum index "
                             f"is {len(self.frames)}") from err

    def get_location(self, index: int, dynamic: bool = False):
        """Get a location on a specific frame.

        Args:
            index (int): The index of the frame.
            dynamic (bool, optional): Static (pure `str`) or dynamic (converted `int`) version.
        """
        try:
            location: list[str] = self.frames[index].get("location", ("0", "0"))
            if dynamic:
                return EvalUtils.location_format(location[0], location[1], self.attributes)
            return location

        except IndexError as err:
            raise IndexError(f"Index receive is {index} when the maximum index "
                             f"is {len(self.frames)}") from err

    def _convert_video(self, path: str, ) -> list[Image.Image]:
        """Convert video into native map data."""
        #pylint: disable=E1101:no-member
        file = cv2.VideoCapture(path)

        frames: list[Image.Image]= []
        while file.isOpened():
            ret, frame = file.read()
            if not ret:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(frame))
        file.release()

        if frames:
            return frames
        else:
            raise OSError("Unable to read file.")

    def _convert_image_or_sequences(self, path: str) -> list[Image.Image]:
        """Convert image or image sequences into native map data."""
        try:
            file = Image.open(path)
            return ImageSequence.all_frames(file, func=lambda img: img.convert("RGB"))
        except (SyntaxError, OSError) as err:
            raise OSError("Unable to read file.") from err

    def insert_map(self, path: str, index: int = -1) -> None:
        """Add the file data to the converter. Only support images and gif.

        **Notice:** Unlike normal list insert, the index -1 is the end of list, 
        and -2 is the end before the last element.

        
        See `save_map()` for example.

        Args:
            path (str): path to file.
            index (int): index to insert into.
        """
        use_append: bool = index == -1
        if index < -1:
            index += 1

        try:
            frames = self._convert_image_or_sequences(path)
        except OSError:
            frames = self._convert_video(path)

        for frame in frames:
            if use_append:
                self.frames.append({"image": frame})
            else:
                self.frames.insert(index, {"image": frame})
                if index >= 0:
                    index += 1

    def move_map(self, index_from: int, index_to: int):
        """Move map from one index and insert as another index.

        Args:
            index_1 (int): _description_
            index_2 (int): _description_
        """
        self.frames.insert(index_to, self.frames.pop(index_from))

    def save_map(self, name: str, parent_path: Path = Path.cwd(), archive: bool = True, **kwargs)\
            -> Generator[FileExistsError | None]:
        """Save the image map. Fuck memory and time management for compile time, we focus runtime.

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
            parent_path (Path | None): Path that lead to saved animation.
            archive (bool): To archive everything as `tar.xz`.
            **kwargs

        Yields:
            Generator[OSError | None]: Yield `FileExistsError` if error occurred, `None` if success.
        """
        name, _ = os.path.splitext(name)
        tmpdir = None
        if archive:
            tmpdir = tempfile.TemporaryDirectory()
            animation_path: Path = Path(tmpdir.name) / name
            animation_path.mkdir(parents=True, exist_ok=True)
            parent_path.mkdir(parents=True, exist_ok=True)
        else:
            animation_path: Path = parent_path / name
            try:
                animation_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                yield FileExistsError(animation_path)

        # ___Compress_process___
        hashmap: dict = {}
        compressed_frames: list[dict] = []
        for _i, frame in enumerate(self.frames):
            image: Image.Image | None = frame.get("image")
            if not isinstance(image, Image.Image):
                raise ValueError(f"Frame index {_i} lacks image data. Consider remaking the map.")

            size_tag: str = "|".join(map(str, image.size))
            same_size: list[Image.Image] | None = hashmap.get(size_tag)
            if same_size is None:
                hashmap.update({size_tag: [image]})
                compressed_frames.append({"size_tag": size_tag,
                                          "index": 0})
            else:
                matched: bool = False
                for index, img in enumerate(same_size):
                    if imgcompare.is_equal(img, image, 0.02):
                        compressed_frames.append({"size_tag": size_tag,
                                                  "index": index})
                        matched = True
                        break
                if not matched:
                    hashmap[size_tag].append(image)
                    compressed_frames.append({"size_tag": size_tag,
                                              "index": len(hashmap[size_tag]) - 1})

        # ___Save_the_files___
        compressed_hashmap: dict = {}
        for save_index, (size_tag, images) in enumerate(hashmap.items()):
            img_kwargs: dict = {}
            if len(images) > 1:
                img_kwargs = {"save_all": True, "append_images": images[1:]}
            compressed_hashmap.update({size_tag: f"{save_index}.webp"})
            images[0].save(animation_path / f"{save_index}.webp",
                           quality=90, **img_kwargs)
        del hashmap

        data: list = []
        for current_index, frame in enumerate(compressed_frames):
            data.append({
                "index": frame.get("index"),
                "file": compressed_hashmap.get(frame.get("size_tag")),
                "location": self.get_location(current_index)
            })

        attributes: dict = self.attributes
        attributes.update({"images": data}, **kwargs)
        with open(animation_path / Constant.JSON_FILE,
                  mode="w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=4)
            f.close()

        if archive:
            tarpath: Path = parent_path / f"{name}.tar.xz"
            if tarpath.exists():
                yield FileExistsError(tarpath)

            with tarfile.open((tarpath), "w:xz") as tar:
                tar.add(animation_path / Constant.JSON_FILE, Constant.JSON_FILE)
                for index in range(len(compressed_hashmap)):
                    gif_name: str = Constant.GIF_FILE.format(index=index)
                    tar.add(animation_path / gif_name, gif_name)
                if tmpdir:
                    tmpdir.cleanup()

def main(individually: bool = False):
    """Converting"""
    #pylint:disable=C0412:ungrouped-imports C0415:import-outside-toplevel E0611:no-name-in-module
    from PyQt6.QtWidgets import QApplication, QFileDialog

    _ = QApplication([])

    converter = Converter()

    file_paths, _tmp = QFileDialog.getOpenFileNames(caption="Select Animations")
    if not file_paths:
        raise OSError("Please select files to convert.")

    save_path = QFileDialog.getSaveFileName(caption="Save File/Folder As")[0]
    if not save_path:
        raise OSError("Please select a file name to save as.")
    save_path = Path(save_path)

    if individually:
        for file_path in file_paths:
            converter.reset()
            converter.insert_map(file_path)

            for result in converter.save_map(Path(file_path).stem, save_path, archive=True):
                if isinstance(result, FileExistsError):
                    if input(f"{result} exists. Overwrite? [y/N] ").lower() != "y":
                        break

    else:
        for file_path in file_paths:
            converter.insert_map(file_path)

        for result in converter.save_map(save_path.stem, save_path.parent, archive=True):
            if isinstance(result, FileExistsError):
                if input(f"{result} exists. Overwrite? [y/N] ").lower() != "y":
                    break

if __name__ == "__main__":
    main(True)
