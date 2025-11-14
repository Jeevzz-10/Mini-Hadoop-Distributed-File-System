import socket
import threading
import os
import json
import time
import sys

CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB
HEARTBEAT_INTERVAL = 5
NAMENODE_PORT = 6000  # TCP heartbeat port


# -------------------------------------------------------------
# Helper to read exactly N bytes (fixes partial recv issues)
# -------------------------------------------------------------
def recv_n(sock, n):
    """Read exactly n bytes from the socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"Socket closed before reading {n} bytes (got {len(buf)})")
        buf += chunk
    return buf


# -------------------------------------------------------------
# Heartbeat sender
# -------------------------------------------------------------
def send_heartbeat(datanode_id, namenode_host, namenode_port):
    print(f"[{datanode_id}] 💓 Starting TCP heartbeat to {namenode_host}:{namenode_port}")
    while True:
        try:
            with socket.create_connection((namenode_host, namenode_port), timeout=5) as s:
                msg = json.dumps({"node_id": datanode_id}).encode("utf-8")
                s.sendall(msg)
            print(f"[{datanode_id}] ✅ Heartbeat sent successfully")
        except Exception as e:
            print(f"[{datanode_id}] ⚠ Heartbeat error: {e}")
        time.sleep(HEARTBEAT_INTERVAL)


# -------------------------------------------------------------
# Handle STORE / RETRIEVE requests from Namenode
# -------------------------------------------------------------
def handle_client_connection(conn, addr, storage_dir, datanode_id):
    try:
        hdr_len = int.from_bytes(recv_n(conn, 8), "big")
        hdr = json.loads(recv_n(conn, hdr_len))
        payload_len = int.from_bytes(recv_n(conn, 8), "big")
        payload = recv_n(conn, payload_len) if payload_len > 0 else b""

        cmd = hdr.get("cmd")
        if not cmd:
            print(f"[{datanode_id}] ❌ Invalid command from {addr}")
            return

        # ---------------- STORE ----------------
        if cmd == "STORE":
            chunk_id = hdr["chunk_id"]
            abs_path = os.path.abspath(os.path.join(storage_dir, chunk_id))

            print(f"[{datanode_id}] 📦 Receiving chunk {chunk_id} ({len(payload)} bytes)")
            print(f"[{datanode_id}] 💾 Saving to {abs_path}")

            os.makedirs(storage_dir, exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(payload)

            written_size = os.path.getsize(abs_path)
            print(f"[{datanode_id}] ✅ Stored chunk {chunk_id} ({written_size} bytes)")

            resp = json.dumps({"status": "OK"}).encode()
            conn.sendall(len(resp).to_bytes(8, "big") + resp + (0).to_bytes(8, "big"))

        # ---------------- RETRIEVE ----------------
        elif cmd == "RETRIEVE":
            chunk_id = hdr["chunk_id"]
            abs_path = os.path.abspath(os.path.join(storage_dir, chunk_id))

            if os.path.exists(abs_path):
                with open(abs_path, "rb") as f:
                    data = f.read()
                resp = json.dumps({"status": "OK"}).encode()
                conn.sendall(len(resp).to_bytes(8, "big") + resp + len(data).to_bytes(8, "big") + data)
                print(f"[{datanode_id}] 📤 Sent chunk {chunk_id} ({len(data)} bytes)")
            else:
                resp = json.dumps({"status": "NOT_FOUND"}).encode()
                conn.sendall(len(resp).to_bytes(8, "big") + resp + (0).to_bytes(8, "big"))
                print(f"[{datanode_id}] ❌ Chunk not found: {abs_path}")

        else:
            print(f"[{datanode_id}] ❌ Unknown command: {cmd}")

    except Exception as e:
        print(f"[{datanode_id}] ❌ Error handling client {addr}: {e}")

    finally:
        conn.close()


# -------------------------------------------------------------
# Main entrypoint
# -------------------------------------------------------------
def main(datanode_id, datanode_port, storage_dir, namenode_host):
    os.makedirs(storage_dir, exist_ok=True)
    abs_storage_path = os.path.abspath(storage_dir)

    print("=" * 60)
    print(f"🟢 DATANODE {datanode_id} STARTED")
    print("=" * 60)
    print(f"📁 Storage Directory: {abs_storage_path}")
    print(f"🌐 Namenode Host: {namenode_host}:{NAMENODE_PORT}")
    print(f"🔌 Listening for chunk ops on port: {datanode_port}")
    print("=" * 60)

    # Start heartbeat thread
    threading.Thread(
        target=send_heartbeat,
        args=(datanode_id, namenode_host, NAMENODE_PORT),
        daemon=True
    ).start()

    # Start TCP listener for chunk operations
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", datanode_port))
    s.listen(5)

    while True:
        conn, addr = s.accept()
        threading.Thread(
            target=handle_client_connection,
            args=(conn, addr, storage_dir, datanode_id),
            daemon=True
        ).start()


# -------------------------------------------------------------
# Command line entry
# -------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        print("Usage: python datanode.py <id> <port> <storage_dir> [namenode_host]")
        print("Example: python datanode.py 0 7001 storage/d0 172.28.204.229")
        print("Example: python datanode.py 1 7002 storage/d1 172.28.204.229")
        sys.exit(1)

    datanode_id = sys.argv[1]
    datanode_port = int(sys.argv[2])
    storage_dir = sys.argv[3]
    namenode_host = sys.argv[4] if len(sys.argv) == 5 else "127.0.0.1"

    main(datanode_id, datanode_port, storage_dir, namenode_host)
