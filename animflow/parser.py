"""Parser for CLI development."""
import argparse
import sys
import json
import struct
import socket
from queue import Queue
from threading import Event, Thread

#pylint: disable=E0611:no-name-in-module
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from animflow import Animation, Displayer

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8184

class CommandMap:
    """Map for all cli socket command."""
    HELP = "HELP"
    LOAD = "LOAD"
    SHOW = "SHOW"
    SELECT = "SELECT"
    DISPLAY = "DISPLAY"
    STOP_DISPLAY = "STOP_DISPLAY"

    @staticmethod
    def get_help_desc(cmd: str, desc: str, **kwargs):
        """Help description for each command."""
        return f"{desc} | {str({"cmd": cmd, **kwargs})}"

    @classmethod
    def get_help(cls) -> dict:
        """Get help mapping."""
        help_map: dict = {
            cls.HELP: {"desc": "Show help."},
            cls.LOAD: {"desc": "Add more animation.", "animation": "[str] (Path/to/file)"},
            cls.SHOW: {"desc": "Show added animation."},
            cls.SELECT: {"desc": "Select animation to play.", "animation_name": "[str]"},
            cls.DISPLAY: {"desc": "Display the animation."},
            cls.STOP_DISPLAY: {"desc": "Stop the displayer."}
        }
        return {cmd: cls.get_help_desc(cmd, **kwargs) for cmd, kwargs in help_map.items()}

class SocketParser:
    """Parser that maintain the socket connection."""
    @staticmethod
    def get_parse_args(argv: list[str]):
        """Get the parse args via python parser."""
        parser = argparse.ArgumentParser(description="Serve a socket for easy use and manage")
        parser.add_argument(
            "--host", default=DEFAULT_HOST,
            help=f"Host to serve the server. Default is {DEFAULT_HOST}"
        )
        parser.add_argument(
            "--port", default=DEFAULT_PORT, type=int,
            help=f"Port for the server to operate on. Default is {DEFAULT_PORT}"
        )
        parser.add_argument(
            "--animation", default="",
            help="The path to animation file or folder, separate each with `,`"
        )
        return parser.parse_args(argv)

    @staticmethod
    def send_json(sock: socket.socket, data: dict) -> None:
        """Send a dict as json with a 4-byte length prefix."""
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack(">I", len(payload))  # 4-byte big-endian length
        sock.sendall(header + payload)

    @classmethod
    def send_command(cls, sock: socket.socket, cmd: str, **kwargs):
        """Best way to send command."""
        cls.send_json(sock, data={
            "cmd": cmd,
            **kwargs
        })

    @classmethod
    def recv_json(cls, sock: socket.socket) -> dict:
        """Receive a length-prefixed json message."""
        raw_len = cls.recv_n(sock, 4)
        if not raw_len:
            return {} # connection closed
        msg_len = struct.unpack(">I", raw_len)[0]
        raw_payload = cls.recv_n(sock, msg_len)
        if not raw_payload:
            return {} # connection is real bad (closed)
        return json.loads(raw_payload.decode("utf-8"))

    @staticmethod
    def recv_n(sock: socket.socket, n: int) -> bytes:
        """Read exactly n bytes."""
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return b""
            buf += chunk
        return buf

    @classmethod
    def main(cls):
        """The main function."""
        parse_args = cls.get_parse_args(sys.argv[1:])
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        QApplication.setQuitOnLastWindowClosed(False)

        displayer = Displayer()
        if parse_args.animation:
            for animation_path in parse_args.animation.split(","):
                for anim in Animation.load_recur(animation_path):
                    displayer.add_animation(anim)
        requests = Queue()

        def socket_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.bind((parse_args.host, parse_args.port))
                server.listen()
                print(f"Listening via {parse_args.host}:{parse_args.port}")

                conn, addr = server.accept()

                with conn:
                    print(f"Successfully connected by {addr}")
                    while True:
                        recv_data = cls.recv_json(conn)
                        if not recv_data:
                            requests.put(None)
                            break
                        response_ready = Event()
                        response = {}
                        requests.put((recv_data, response, response_ready))
                        response_ready.wait()
                        cls.send_json(conn, response)

        socket_thread = Thread(target=socket_server, daemon=True)
        socket_thread.start()

        def process_request():
            try:
                request = requests.get_nowait()
            except Exception: #pylint:disable=W0718:broad-exception-caught
                return
            if request is None:
                displayer.stop_display()
                app.quit()
                return

            recv_data, response, response_ready = request
            try:
                cmd = recv_data.pop("cmd", "").upper()
                match cmd:
                    case CommandMap.HELP:
                        response.update(CommandMap.get_help())

                    case CommandMap.LOAD:
                        animation = recv_data.pop("animation")
                        for anim in Animation.load_recur(animation):
                            displayer.add_animation(anim, **recv_data)

                    case CommandMap.SHOW:
                        response["animations"] = displayer.show_animation()

                    case CommandMap.SELECT:
                        displayer.select_animation(**recv_data)

                    case CommandMap.DISPLAY:
                        if displayer.is_stopped:
                            displayer.display(run_event_loop=False)
                        else:
                            response["error"] = "Only one per process is permissible."

                    case CommandMap.STOP_DISPLAY:
                        if not displayer.is_stopped:
                            displayer.stop_display()
                        else:
                            response["error"] = "There is no displayer to stop."

                    case _:
                        response["error"] = (f"Unknown command: {cmd}. "
                                              "Please see help by sending: {'cmd': 'HELP'}")
                if not response.get("error"):
                    response["error"] = None # Has no error
            except Exception as err: #pylint:disable=W0718:broad-exception-caught
                response["error"] = str(err)
            response_ready.set()

        timer = QTimer()
        timer.timeout.connect(process_request)
        timer.start(10)
        app.exec()
        print("Successfully disconnect, shutdown the server.")

def _test_connector(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Minimal connector for testing with socket. Run this file from a terminal, 
    then make a `temp.py` that run this function only.

    ## Stdin Examples.
    
    cmd: HELP

    cmd: LOAD {"animation": "Path/to/file/or/folder"}

    cmd: SHOW
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.connect((host, port))

        while True:
            args = input("\ncmd: ").split(maxsplit=1)
            SocketParser.send_json(client, data={
                "cmd": args[0]
            } if len(args) == 1 else {
                "cmd": args[0],
                **json.loads(args[1])
            })

            result = SocketParser.recv_json(client)
            if result:
                print(result)
            else:
                print("Lose connection. Abort.")
                break

if __name__ == "__main__":
    SocketParser.main()
