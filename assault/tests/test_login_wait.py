import socket
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA_DIR = ROOT / "area"
SRC_DIR = ROOT / "src"
ACK_BIN = SRC_DIR / "ack"


class LoginIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.port = 4123
        self.player_name = "Codexx"
        self.player_password = "itestpass"

        self.server = subprocess.Popen(
            [str(ACK_BIN), str(self.port)],
            cwd=str(AREA_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._wait_for_port()

    def tearDown(self) -> None:
        if self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)
        if self.server.stdout is not None:
            self.server.stdout.close()
        player_file = AREA_DIR / "player" / self.player_name[0].lower() / self.player_name
        if player_file.exists():
            player_file.unlink()

    def _wait_for_port(self, timeout: float = 20.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                try:
                    sock.connect(("127.0.0.1", self.port))
                    return
                except OSError:
                    time.sleep(0.2)
        self.fail(f"MUD server did not start on port {self.port}")

    def _recv_until(self, sock: socket.socket, needle: str, timeout: float = 25.0) -> None:
        deadline = time.time() + timeout
        buf = ""
        sock.settimeout(1.0)
        while time.time() < deadline:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            buf += data.decode(errors="ignore")
            if needle in buf:
                return
        self.fail(f"Timed out waiting for {needle!r}. Buffer was:\n{buf}")

    def test_login_and_wait_eight_seconds(self) -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            self._recv_until(sock, "your name, recruit")
            sock.sendall((self.player_name + "\n").encode())

            self._recv_until(sock, "Did I get that right")
            sock.sendall(b"y\n")

            self._recv_until(sock, "desired password")
            sock.sendall((self.player_password + "\n").encode())

            self._recv_until(sock, "retype your password")
            sock.sendall((self.player_password + "\n").encode())

            self._recv_until(sock, "(Y)es, (N)o, (M)ap colors only")
            sock.sendall(b"n\n")

            self._recv_until(sock, "Are you (M)ale or (F)emale")
            sock.sendall(b"m\n")

            self._recv_until(sock, "Which would you like to have")
            sock.sendall(b"Gold\n")

            self._recv_until(sock, "Please select: Normal or Basic play mode")
            sock.sendall(b"Normal\n")

            self._recv_until(sock, "Pick your class")
            sock.sendall(b"Engineer\n")

            self._recv_until(sock, "Are you allowed to have any more characters")
            sock.sendall(b"n\n")

            self._recv_until(sock, "Useful Commands")
            time.sleep(8)
            sock.sendall(b"quit\n")


if __name__ == "__main__":
    unittest.main()
