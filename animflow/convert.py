"""Converter function."""
import json
import tarfile
import tempfile
import os
from collections.abc import Generator

import imgcompare
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

        frames = self._convert_image_or_sequences(path)
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

    def save_map(self, name: str, parent_path: str = '', archive: bool = True, **kwargs)\
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
            images[0].save(os.path.join(animation_path, f"{save_index}.webp"),
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
        with open(os.path.join(animation_path, Constant.JSON_FILE),
                  mode="w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=4)
            f.close()

        if archive:
            tarpath: str = os.path.join(parent_path, f"{name}.tar.xz")
            if os.path.exists(tarpath):
                yield FileExistsError(tarpath)

            with tarfile.open((tarpath), "w:xz") as tar:
                tar.add(os.path.join(animation_path, Constant.JSON_FILE), Constant.JSON_FILE)
                for index in range(len(compressed_hashmap)):
                    gif_name: str = Constant.GIF_FILE.format(index=index)
                    tar.add(os.path.join(animation_path, gif_name), gif_name)
                if tmpdir:
                    tmpdir.cleanup()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QFileDialog #pylint:disable=E0611:no-name-in-module

    _ = QApplication([])

    converter = Converter()

    file_paths, _tmp = QFileDialog.getOpenFileNames(caption="Select Animations")
    if not file_paths:
        raise OSError("Please select files to convert.")

    for file_path in file_paths:
        converter.insert_map(file_path)

    parent, filename = os.path.split(QFileDialog.getSaveFileName(caption="Save File As")[0])
    if not (parent and filename):
        raise OSError("Please select a file name to save as.")

    for result in converter.save_map(os.path.splitext(filename)[0], parent, archive=True):
        if isinstance(result, FileExistsError):
            if input(f"{result} exists. Overwrite? [y/N] ").lower() != "y":
                break
