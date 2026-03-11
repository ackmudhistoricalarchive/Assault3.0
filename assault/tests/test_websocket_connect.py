import base64
import hashlib
import os
import socket
import struct
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA_DIR = ROOT / "area"
SRC_DIR = ROOT / "src"
ACK_BIN = SRC_DIR / "ack"


class WebSocketIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.port = 4124
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

    def _read_http_headers(self, sock: socket.socket, timeout: float = 5.0) -> tuple[str, bytes]:
        deadline = time.time() + timeout
        data = b""
        while time.time() < deadline:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data:
                break
        header_blob, _, remainder = data.partition(b"\r\n\r\n")
        return header_blob.decode("ascii", errors="ignore"), remainder

    def _recv_ws_text_until(self, sock: socket.socket, needle: str, timeout: float = 20.0, initial: bytes = b"") -> str:
        deadline = time.time() + timeout
        buf = ""
        pending = bytearray(initial)
        sock.settimeout(1.0)
        while time.time() < deadline:
            while len(pending) < 2:
                try:
                    pending.extend(sock.recv(4096))
                except socket.timeout:
                    break
            if len(pending) < 2:
                continue
            header = bytes(pending[:2])
            del pending[:2]
            if not header:
                break
            fin_opcode, length_byte = header[0], header[1]
            opcode = fin_opcode & 0x0F
            payload_len = length_byte & 0x7F
            if payload_len == 126:
                while len(pending) < 2:
                    pending.extend(sock.recv(4096))
                payload_len = struct.unpack("!H", bytes(pending[:2]))[0]
                del pending[:2]
            elif payload_len == 127:
                while len(pending) < 8:
                    pending.extend(sock.recv(4096))
                payload_len = struct.unpack("!Q", bytes(pending[:8]))[0]
                del pending[:8]
            masked = bool(length_byte & 0x80)
            if masked:
                while len(pending) < 4:
                    pending.extend(sock.recv(4096))
                mask = bytes(pending[:4])
                del pending[:4]
            else:
                mask = b""
            while len(pending) < payload_len:
                pending.extend(sock.recv(4096))
            payload = bytes(pending[:payload_len])
            del pending[:payload_len]
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            if opcode == 0x1:  # text
                buf += payload.decode(errors="ignore")
                if needle in buf:
                    return buf
            elif opcode == 0x8:
                break
            elif opcode == 0x9:
                self._send_ws_frame(sock, 0xA, payload)

        self.fail(f"Timed out waiting for {needle!r}. Buffer was:\n{buf}")

    def _send_ws_frame(self, sock: socket.socket, opcode: int, payload: bytes) -> None:
        first = 0x80 | (opcode & 0x0F)
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length <= 0xFFFF:
            header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
        masked_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        sock.sendall(header + mask + masked_payload)

    def test_websocket_handshake_and_greeting(self) -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
            req = (
                "GET / HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.sendall(req.encode("ascii"))

            headers, leftover = self._read_http_headers(sock)
            self.assertIn("101 Switching Protocols", headers)

            expected_accept = base64.b64encode(
                hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
            ).decode("ascii")
            self.assertIn(f"Sec-WebSocket-Accept: {expected_accept}", headers)

            self._recv_ws_text_until(sock, "your name, recruit", initial=leftover)

            self._send_ws_frame(sock, 0x8, b"")


if __name__ == "__main__":
    unittest.main()
