import numpy as np
import random
import math
import zmq
import time
from scipy.spatial import distance
from tdw.output_data import IsOnNavMesh, Images
from PIL import Image
import io
import os
from threading import Thread
from tdw.controller import Controller
from typing import List, Tuple, Dict, Optional, Union
import socket
from contextlib import closing
from tdw.librarian import ModelRecord
from pathlib import Path
import boto3
from botocore.exceptions import ProfileNotFound, ClientError
from subprocess import check_output, Popen, call
import re
from psutil import pid_exists
import base64


class TDWUtils:
    """
    Utility functions for controllers.

    Usage:

    ```python
    from tdw.tdw_utils import TDWUtils
    ```
    """

    VECTOR3_ZERO = {"x": 0, "y": 0, "z": 0}

    @staticmethod
    def vector3_to_array(vector3: Dict[str, float]) -> np.array:
        """
        Convert a Vector3 object to a numpy array.

        :param vector3: The Vector3 object, e.g. `{"x": 0, "y": 0, "z": 0}`

        :return A numpy array.
        """

        return np.array([vector3["x"], vector3["y"], vector3["z"]])

    @staticmethod
    def array_to_vector3(arr: np.array) -> Dict[str, float]:
        """
        Convert a numpy array to a Vector3.

        :param arr: The numpy array.

        :return A Vector3, e.g. `{"x": 0, "y": 0, "z": 0}`
        """

        return {"x": float(arr[0]), "y": float(arr[1]), "z": float(arr[2])}

    @staticmethod
    def vector4_to_array(vector4: Dict[str, float]) -> np.array:
        """
        Convert a Vector4 to a numpy array.

        :param vector4: The Vector4 object, e.g. `{"x": 0, "y": 0, "z": 0, "w": 0}`

        :return A numpy array.
        """

        return np.array([vector4["x"], vector4["y"], vector4["z"], vector4["w"]])

    @staticmethod
    def array_to_vector4(arr: np.array) -> Dict[str, float]:
        """
        Convert a numpy array to a Vector4.

        :param arr: The numpy array.

        :return A Vector4, e.g. `{"x": 0, "y": 0, "z": 0, "w": 0}`
        """

        return {"x": arr[0], "y": arr[1], "z": arr[2], "w": arr[3]}

    @staticmethod
    def color_to_array(color: Dict[str, float]) -> np.array:
        """
        Convert a RGB Color to a numpy array.

        :param color: The Color object, e.g. `{"r": 0, "g": 0, "b": 0, "a": 1}`

        :return A numpy array.
        """

        return np.array([round(color["r"] * 255), round(color["g"] * 255), round(color["b"] * 255)])

    @staticmethod
    def array_to_color(arr: np.array) -> Dict[str, float]:
        """
        Convert a numpy array to a RGBA Color. If no A value is supplied it will default to 1.

        :param arr: The array.

        :return A Color, e.g. `{"r": 0, "g": 0, "b": 0, "a": 1}`
        """

        return {"r": arr[0], "g": arr[1], "b": arr[2], "a": 1 if len(arr) == 3 else arr[3]}

    @staticmethod
    def get_random_point_in_circle(center: np.array, radius: float) -> np.array:
        """
        Get a random point in a circle, defined by a center and radius.

        :param center: The center of the circle.
        :param radius: The radius of the circle.

        :return A numpy array. The y value (`arr[1]`) is always 0.
        """

        alpha = 2 * math.pi * random.random()
        r = radius * math.sqrt(random.random())
        x = r * math.cos(alpha) + center[0]
        z = r * math.sin(alpha) + center[2]

        return np.array([x, 0, z])

    @staticmethod
    def get_magnitude(vector3: Dict[str, float]) -> float:
        """
        Get the magnitude of a Vector3.

        :param vector3: The Vector3 object, e.g. `{"x": 0, "y": 0, "z": 0}`

        :return The vector magnitude.
        """

        return np.linalg.norm(TDWUtils.vector3_to_array(vector3))

    @staticmethod
    def extend_line(p0: np.array, p1: np.array, d: float, clamp_y=True) -> np.array:
        """
        Extend the line defined by p0 to p1 by distance d. Clamps the y value to 0.

        :param p0: The origin.
        :param p1: The second point.
        :param d: The distance of which the line is to be extended.
        :param clamp_y: Clamp the y value to 0.

        :return: The position at distance d.
        """

        if clamp_y:
            p0[1] = 0
            p1[1] = 0

        # Get the distance between the two points.
        d0 = distance.euclidean(p0, p1)
        # Get the total distance.
        d_total = d0 + d

        return p1 + ((p1 - p0) * d_total)

    @staticmethod
    def get_distance(vector3_0: Dict[str, float], vector3_1: Dict[str, float]) -> float:
        """
        Calculate the distance between two Vector3 (e.g. `{"x": 0, "y": 0, "z": 0}`) objects.

        :param vector3_0: The first Vector3.
        :param vector3_1: The second Vector3.

        :return The distance.
        """

        return distance.euclidean(TDWUtils.vector3_to_array(vector3_0), TDWUtils.vector3_to_array(vector3_1))

    @staticmethod
    def get_box(width: int, length: int) -> List[Dict[str, int]]:
        """
        Returns a list of x,y positions that can be used to create a box with the `create_exterior_walls` command.
        :param width: The width of the box.
        :param length: The length of the box.

        :return The box as represented by a list of `{"x": x, "y": y}` dictionaries.
        """

        box = []
        for x in range(width):
            for y in range(length):
                if x == 0 or x == width - 1 or y == 0 or y == length - 1:
                    box.append({"x": x, "y": y})
        return box

    @staticmethod
    def get_vector3(x, y, z) -> Dict[str, float]:
        """
        :param x: The x value.
        :param y: The y value.
        :param z: The z value.

        :return: A Vector3: {"x": x, "y", y, "z": z}
        """

        return {"x": x, "y": y, "z": z}

    @staticmethod
    def create_empty_room(width: int, length: int) -> dict:
        """
        :param width: The width of the room.
        :param length: The length of the room.

        :return: A `create_exterior_walls` command that creates a box with dimensions (width, length).
        """

        return {"$type": "create_exterior_walls", "walls": TDWUtils.get_box(width, length)}

    @staticmethod
    def create_room_from_image(filepath: str, exterior_color=(255, 0, 0), interior_color=(0, 0, 0)) -> List[dict]:
        """
        Load a .png file from the disk and use it to create a room. Each pixel on the image is a grid point.

        :param filepath: The absolute filepath to the image.
        :param exterior_color: The color on the image marking exterior walls (default=red).
        :param interior_color: The color on the image marking interior walls (default=black).

        :return: A list of commands: The first creates the exterior walls, and the second creates the interior walls.
        """

        exterior_walls = []
        interior_walls = []

        # Read the image.
        img = Image.open(filepath)
        pixels = img.load()
        col, row = img.size

        # Read each pixel as a grid point.
        for i in range(row):
            for j in range(col):
                pixel = pixels[i, j]
                if len(pixel) == 4:
                    pixel = (pixel[0], pixel[1], pixel[2])
                if pixel == exterior_color:
                    exterior_walls.append({"x": i, "y": col - j})
                elif pixel == interior_color:
                    interior_walls.append({"x": i, "y": col - j})

        return [{"$type": "create_exterior_walls",
                 "walls": exterior_walls},
                {"$type": "create_interior_walls",
                 "walls": interior_walls}]

    @staticmethod
    def save_images(images: Images, filename: str, output_directory="dist", resize_to=None, append_pass: bool = True) -> None:
        """
        Save each image in the Images object.
        The name of the image will be: pass_filename.extension, e.g.: `"0000"` -> `depth_0000.png`
        The images object includes the pass and extension information.

        :param images: The Images object. Contains each capture pass plus metadata.
        :param output_directory: The directory to write images to.
        :param filename: The filename of each image, minus the extension. The image pass will be appended as a prefix.
        :param resize_to: Specify a (width, height) tuple to resize the images to. This is slower than saving as-is.
        :param append_pass: If false, the image pass will _not_ be appended to the filename as a prefix, e.g.: `"0000"`: -> "`0000.jpg"`
        """

        if not os.path.isdir(output_directory):
            os.makedirs(output_directory)

        for i in range(images.get_num_passes()):
            if append_pass:
                fi = images.get_pass_mask(i)[1:] + "_" + filename + "." + images.get_extension(i)
            else:
                fi = filename + "." + images.get_extension(i)

            if resize_to:
                TDWUtils.get_pil_image(images, i).resize((resize_to[0], resize_to[1]), Image.LANCZOS)\
                    .save(os.path.join(output_directory, fi))
            else:
                with open(os.path.join(output_directory, fi), "wb") as f:
                    f.write(images.get_image(i))

    @staticmethod
    def zero_padding(integer: int, width=4) -> str:
        """
        :param integer: The integer being converted.
        :param width: The total number of digits in the string. If integer == 3 and width == 4, output is: "0003".

        :return A string representation of an integer padded with zeroes, e.g. converts `3` to `"0003"`.
        """

        return str(integer).zfill(width)

    @staticmethod
    def get_pil_image(images: Images, index: int) -> Image:
        """
        Converts Images output data to a PIL Image object.
        Use this function to read and analyze an image in memory.
        Do NOT use this function to save image data to disk; `save_image` is much faster.

        :param images: Images data from the build.
        :param index: The index of the image in Images.get_image

        :return A PIL image.
        """

        return Image.open(io.BytesIO(images.get_image(index)))

    @staticmethod
    def get_random_position_on_nav_mesh(c: Controller, width: float, length: float, x_e=0, z_e=0, bake=True, rng=random.uniform) -> Tuple[float, float, float]:
        """
        Returns a random position on a NavMesh.

        :param c: The controller.
        :param width: The width of the environment.
        :param length: The length of the environment.
        :param bake: If true, send bake_nav_mesh.
        :param rng: Random number generator.
        :param x_e: The x position of the environment.
        :param z_e: The z position of the environment.

        :return The coordinates as a tuple `(x, y, z)`
        """

        if bake:
            c.communicate({'$type': 'bake_nav_mesh'})

        # Try to find a valid position on the NavMesh.
        is_on = False
        x, y, z = (0, 0, 0)
        while not is_on:
            # Get a random position.
            x = rng(-width / 2, width / 2) + x_e
            z = rng(-length / 2, length / 2) + z_e
            resp = c.communicate(
                {'$type': 'send_is_on_nav_mesh',
                 'position': {'x': x, 'y': 0, 'z': z},
                 'max_distance': 4.0
                 })
            answer = IsOnNavMesh(resp[0])
            is_on = answer.get_is_on()
            x, y, z = answer.get_position()
        return x, y, z

    @staticmethod
    def set_visual_material(c: Controller, substructure: List[dict], object_id: int, material: str, quality="med") -> List[dict]:
        """
        :param c: The controller.
        :param substructure: The metadata substructure of the object.
        :param object_id: The ID of the object in the scene.
        :param material: The name of the new material.
        :param quality: The quality of the material.

        :return A list of commands to set ALL visual materials on an object to a single material.
        """

        commands = []
        for sub_object in substructure:
            for i in range(len(sub_object["materials"])):
                commands.extend([c.get_add_material(material, library="materials_" + quality + ".json"),
                                 {"$type": "set_visual_material",
                                  "id": object_id,
                                  "material_name": material,
                                  "object_name": sub_object["name"],
                                  "material_index": i}])
        return commands

    @staticmethod
    def get_depth_values(image: np.array) -> np.array:
        """
        Get the depth values of each pixel in a _depth image pass.
        The far plane is hardcoded as 100. The near plane is hardcoded as 0.1.
        (This is due to how the depth shader is implemented.)

        :param image: The image pass as a numpy array.

        :return An array of depth values.
        """

        # Convert the image to a 2D image array.
        image = np.array(Image.open(io.BytesIO(image)))

        depth = np.array((image[:, :, 0] * 256 * 256 + image[:, :, 1] * 256 + image[:, :, 2]) /
                         (256 * 256 * 256) * 100.1)
        return depth

    @staticmethod
    def create_avatar(avatar_type="A_Img_Caps_Kinematic", avatar_id="a", position=None, look_at=None) -> List[dict]:
        """
        This is a wrapper for `create_avatar` and, optionally, `teleport_avatar_to` and `look_at_position`.

        :param avatar_type: The type of avatar.
        :param avatar_id: The avatar ID.
        :param position: The position of the avatar. If this is None, the avatar won't teleport.
        :param look_at: If this isn't None, the avatar will look at this position.

        :return A list of commands to create theavatar.
        """

        # Create the avatar.
        commands = [{"$type": "create_avatar",
                     "type": avatar_type,
                     "id": avatar_id}]

        # Teleport the avatar.
        if position:
            commands.append({"$type": "teleport_avatar_to",
                             "avatar_id": avatar_id,
                             "position": position})
        if look_at:
            commands.append({"$type": "look_at_position",
                             "avatar_id": avatar_id,
                             "position": look_at})
        return commands

    @staticmethod
    def _send_start_build(socket, controller_address: str) -> dict:
        """
        This sends a command to the launch_binaries daemon running on a remote node
        to start a binary connected to the given controller address.

        :param socket: The zmq socket.
        :param controller_address: The host name or ip address of node running the controller.

        :return Build info dictionary containing build port.
        """
        request = {"type": "start_build",
                   "controller_address": controller_address}
        socket.send_json(request)
        build_info = socket.recv_json()
        return build_info

    @staticmethod
    def _send_keep_alive(socket, build_info: dict) -> dict:
        """
        This sends a command to the launch_binaries daemon running on a remote node
        to mark a given binary as still alive, preventing garbage collection.

        :param socket: The zmq socket.
        :param build_info: A diciontary containing the build_port.

        :return a heartbeat indicating build is still alive.
        """

        build_port = build_info["build_port"]
        request = {"type": "keep_alive", "build_port": build_port}
        socket.send_json(request)
        heartbeat = socket.recv_json()
        return heartbeat

    @staticmethod
    def _send_kill_build(socket, build_info: dict) -> dict:
        """
        This sends a command to the launch_binaries daemon running on a remote node to terminate a given binary.

        :param socket: The zmq socket.
        :param build_info: A diciontary containing the build_port.

        :return A kill_status indicating build has been succesfully terminated.
        """

        build_port = build_info["build_port"]
        request = {"type": "kill_build", "build_port": build_port}
        socket.send_json(request)
        kill_status = socket.recv_json()
        return kill_status

    @staticmethod
    def _keep_alive_thread(socket, build_info: dict) -> None:
        """
        This is a wrapper around the keep alive command to be executed in a separate thread.

        :param socket: The zmq socket.
        :param build_info: A diciontary containing the build_port.
        """
        while True:
            TDWUtils._send_keep_alive(socket, build_info)
            time.sleep(60)

    @staticmethod
    def launch_build(listener_port: int, build_address: str, controller_address: str) -> dict:
        """
        Connect to a remote binary_manager daemon and launch an instance of a TDW build.

        Returns the necessary information for a local controller to connect.
        Use this function to automatically launching binaries on remote (or local) nodes, and to
        automatically shut down the build after controller is finished. Call in the constructor
        of a controller and pass the build_port returned in build_info to the parent Controller class.

        :param listener_port: The port launch_binaries is listening on.
        :param build_address: Remote IP or hostname of node running launch_binaries.
        :param controller_address: IP or hostname of node running controller.

        :return The build_info dictionary containing build_port.
        """

        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://" + build_address + ":%s" % listener_port)
        build_info = TDWUtils._send_start_build(socket, controller_address)
        thread = Thread(target=TDWUtils._keep_alive_thread,
                        args=(socket, build_info))
        thread.setDaemon(True)
        thread.start()
        return build_info

    @staticmethod
    def get_unity_args(arg_dict: dict) -> List[str]:
        """
        :param arg_dict: A dictionary of arguments. Key=The argument prefix (e.g. port) Value=Argument value.

        :return The formatted command line string that is accepted by unity arg parser.
        """

        formatted_args = []
        for key, value in arg_dict.items():
            prefix = "-" + key + "="
            if type(value) == list:
                prefix += ",".join([str(v) for v in value])
            else:
                prefix += str(value)
            formatted_args += [prefix]
        return formatted_args

    @staticmethod
    def find_free_port() -> int:
        """
        :return a free port.
        """

        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", 0))
            return int(s.getsockname()[1])

    @staticmethod
    def euler_to_quaternion(euler: Tuple[float, float, float]) -> List[float]:
        """
        Convert Euler angles to a quaternion.

        :param euler: The Euler angles vector.
        """

        roll, pitch, yaw = euler
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)

        w = cy * cp * cr + sy * sp * sr
        x = cy * cp * sr - sy * sp * cr
        y = sy * cp * sr + cy * sp * cr
        z = sy * cp * cr - cy * sp * sr
        return [x, y, z, w]

    @staticmethod
    def get_unit_scale(record: ModelRecord) -> float:
        """
        :param record: The model record.

        :return The scale factor required to scale a model to 1 meter "unit scale".
        """

        bounds = record.bounds

        # Get the "unit scale" of the object.
        s = 1 / max(
            bounds['top']['y'] - bounds['bottom']['y'],
            bounds['front']['z'] - bounds['back']['z'],
            bounds['right']['x'] - bounds['left']['x'])
        return s

    @staticmethod
    def validate_amazon_s3() -> bool:
        """
        Validate that your local Amazon S3 credentials are set up correctly.

        :return True if everything is OK.
        """

        config_path = Path.home().joinpath(".aws/config")
        new_config_path = not config_path.exists()
        # Generate a valid config file.
        if new_config_path:
            config_path.write_text("[default]\nregion = us-east-1\noutput = json")
            print(f"Generated a new config file: {config_path.resolve()}")

        try:
            session = boto3.Session(profile_name="tdw")
            s3 = session.resource("s3")
            tdw_private = False
            for bucket in s3.buckets.all():
                if bucket.name == "tdw-private":
                    tdw_private = True
            if not tdw_private:
                print("ERROR! Could not access bucket tdw-private. Make sure you have the right permissions.")
                return False
            return True
        except ProfileNotFound:
            print(f"ERROR! Your AWS credentials file is not set up correctly.")
            print("Your AWS credentials must have a [tdw] profile with valid keys.")
            return False
        except ClientError:
            print("Error! Bad S3 credentials.")
            return False

    @staticmethod
    def get_base64_flex_particle_forces(forces: list) -> str:
        """
        :param forces: The forces (see Flex documentation for how to arrange this array).

        :return: An array of Flex particle forces encoded in base64.
        """

        forces = np.array(forces, dtype=np.float32)
        return base64.b64encode(forces).decode()


class AudioUtils:
    """
    Utility class for recording audio in TDW using [fmedia](https://stsaz.github.io/fmedia/).

    Usage:

    ```python
    from tdw.tdw_utils import AudioUtils
    from tdw.controller import Controller

    c = Controller()

    initialize_trial()  # Your code here.

    # Begin recording audio. Automatically stop recording at 10 seconds.
    AudioUtils.start(output_path="path/to/file.wav", until=(0, 10))

    do_trial()  # Your code here.

    # Stop recording.
    AudioUtils.stop()
    ```
    """

    # The process ID of the audio recorder.
    RECORDER_PID: Optional[int] = None
    # The audio capture device.
    DEVICE: Optional[str] = None

    @staticmethod
    def get_system_audio_device() -> str:
        """
        :return: The audio device that can be used to capture system audio.
        """

        devices = check_output(["fmedia", "--list-dev"]).decode("utf-8").split("Capture:")[1]
        dev_search = re.search("device #(.*): Stereo Mix", devices, flags=re.MULTILINE)
        assert dev_search is not None, "No suitable audio capture device found:\n" + devices
        return dev_search.group(1)

    @staticmethod
    def start(output_path: Union[str, Path], until: Optional[Tuple[int, int]] = None) -> None:
        """
        Start recording audio.

        :param output_path: The path to the output file.
        :param until: If not None, fmedia will record until `minutes:seconds`. The value must be a tuple of 2 integers. If None, fmedia will record until you send `AudioUtils.stop()`.
        """

        if isinstance(output_path, str):
            p = Path(output_path).resolve()
        else:
            p = output_path

        # Create the directory.
        if not p.parent.exists():
            p.parent.mkdir(parents=True)

        # Set the capture device.
        if AudioUtils.DEVICE is None:
            AudioUtils.DEVICE = AudioUtils.get_system_audio_device()
        fmedia_call = ["fmedia",
                       "--record",
                       f"--dev-capture={AudioUtils.DEVICE}",
                       f"--out={str(p.resolve())}",
                       "--globcmd=listen"]
        # Automatically stop recording.
        if until is not None:
            fmedia_call.append(f"--until={TDWUtils.zero_padding(until[0], 2)}:{TDWUtils.zero_padding(until[1], 2)}")
        with open(os.devnull, "w+") as f:
            AudioUtils.RECORDER_PID = Popen(fmedia_call,
                                            stderr=f).pid

    @staticmethod
    def stop() -> None:
        """
        Stop recording audio (if any fmedia process is running).
        """

        if AudioUtils.RECORDER_PID is not None:
            with open(os.devnull, "w+") as f:
                call(['fmedia', '--globcmd=quit'], stderr=f, stdout=f)
            AudioUtils.RECORDER_PID = None

    @staticmethod
    def is_recording() -> bool:
        """
        :return: True if the fmedia recording process still exists.
        """

        return AudioUtils.RECORDER_PID is not None and pid_exists(AudioUtils.RECORDER_PID)
