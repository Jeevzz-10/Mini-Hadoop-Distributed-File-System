"""
Namenode: Flask dashboard + TCP heartbeat + chunk coordination
Run:
    python3 namenode.py
Dashboard:
    http://<namenode-ip>:5000
"""

import os
import socket
import threading
import json
import time
import uuid
import tempfile
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify, redirect, url_for, flash

# -------------------------- #
# Configuration
# -------------------------- #
CHUNK_SIZE = 2 * 1024 * 1024   # 2 MB per chunk
HEARTBEAT_PORT = 6000          # TCP heartbeat port
DND_TCP_BASE = 7001            # Datanode TCP base ports: 7001, 7002, ...
HEARTBEAT_TIMEOUT = 10         # seconds before node marked DEAD
METADATA_FILE = Path("metadata.json")

# -------------------------- #
# Flask App
# -------------------------- #
app = Flask(__name__)
app.secret_key = "mini-hdfs-secret"
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024  # Allow up to 512 MB uploads

# -------------------------- #
# Metadata (persistent)
# -------------------------- #
if METADATA_FILE.exists():
    meta = json.loads(METADATA_FILE.read_text())
else:
    meta = {
        "files": {},
        "chunks": {},
        "datanodes": {
            "0": {"last_hb": 0, "host": "localhost", "tcp_port": DND_TCP_BASE},
            "1": {"last_hb": 0, "host": "localhost", "tcp_port": DND_TCP_BASE + 1}
        },
    }

meta_lock = threading.Lock()

# -------------------------- #
# TCP framing helpers
# -------------------------- #
def send_framed(sock, header: dict, payload: bytes):
    hdr = json.dumps(header).encode()
    sock.sendall(len(hdr).to_bytes(8, "big"))
    sock.sendall(hdr)
    sock.sendall(len(payload).to_bytes(8, "big"))
    if payload:
        sock.sendall(payload)

def recv_n(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf

def recv_framed(conn):
    hdr_len = int.from_bytes(recv_n(conn, 8), "big")
    hdr = json.loads(recv_n(conn, hdr_len))
    payload_len = int.from_bytes(recv_n(conn, 8), "big")
    payload = recv_n(conn, payload_len) if payload_len > 0 else b""
    return hdr, payload

# -------------------------- #
# Heartbeat (TCP listener)
# -------------------------- #
def heartbeat_listener_tcp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", HEARTBEAT_PORT))
    sock.listen(5)
    print(f"[Namenode] Heartbeat TCP listener on port {HEARTBEAT_PORT}")

    while True:
        try:
            conn, addr = sock.accept()
            with conn:
                data = conn.recv(4096)
                if not data:
                    continue
                msg = json.loads(data.decode().strip())
                node_id = str(msg.get("node_id"))
                host = addr[0]
                tcp_port = DND_TCP_BASE + int(node_id[-1])
                ts = time.time()

                with meta_lock:
                    meta["datanodes"].setdefault(node_id, {})
                    meta["datanodes"][node_id].update({
                        "last_hb": ts,
                        "host": host,
                        "tcp_port": tcp_port
                    })
                    METADATA_FILE.write_text(json.dumps(meta, indent=2))
                print(f"[Namenode] 💓 Heartbeat from datanode {node_id} ({host})")
        except Exception as e:
            print("[Namenode] heartbeat TCP error:", e)

# -------------------------- #
# Chunk storage helpers
# -------------------------- #
def store_chunk_to_node(chunk_id, chunk_bytes, node_id, filename):
    dn = meta["datanodes"].get(str(node_id))
    if not dn:
        return False
    try:
        with socket.create_connection((dn["host"], dn["tcp_port"]), timeout=30) as s:
            send_framed(s, {"cmd": "STORE", "chunk_id": chunk_id, "filename": filename}, chunk_bytes)
            hdr, _ = recv_framed(s)
            return hdr.get("status") == "OK"
    except Exception as e:
        print(f"[Namenode] ❌ store error → node {node_id}: {e}")
        return False

def retrieve_chunk_from_node(chunk_id, node_id):
    dn = meta["datanodes"].get(str(node_id))
    if not dn:
        return None
    try:
        with socket.create_connection((dn["host"], dn["tcp_port"]), timeout=30) as s:
            send_framed(s, {"cmd": "RETRIEVE", "chunk_id": chunk_id}, b"")
            hdr, payload = recv_framed(s)
            if hdr.get("status") == "OK":
                return payload
    except Exception as e:
        print(f"[Namenode] ❌ retrieve error node {node_id}: {e}")
    return None

# -------------------------- #
# Upload / Download
# -------------------------- #
@app.route("/upload", methods=["POST"])
def upload():
    uploaded = request.files.get("file")
    if not uploaded:
        flash("⚠ No file selected. Please choose a file before uploading.", "error")
        return redirect(url_for("index"))

    fname = uploaded.filename
    data = uploaded.read()
    chunks = []

    print(f"\n[Namenode] 📤 Upload initiated for '{fname}' ({len(data)} bytes)")
    idx = 0
    chunk_count = 0

    while idx < len(data):
        chunk_bytes = data[idx: idx + CHUNK_SIZE]
        chunk_id = str(uuid.uuid4())
        chunks.append(chunk_id)
        chunk_count += 1
        print(f"\n[Namenode] 🧩 Processing chunk {chunk_count} (ID={chunk_id[:8]}, size={len(chunk_bytes)} bytes)")

        successes = []
        for node_id in ("0", "1"):
            print(f"[Namenode] → Attempting to send chunk {chunk_id[:8]} to Datanode {node_id}...")
            if store_chunk_to_node(chunk_id, chunk_bytes, node_id, fname):
                print(f"[Namenode] ✅ Chunk {chunk_id[:8]} successfully stored in Datanode {node_id}")
                successes.append(node_id)
            else:
                print(f"[Namenode] ❌ Failed to store chunk {chunk_id[:8]} in Datanode {node_id}")

        with meta_lock:
            meta["chunks"][chunk_id] = successes
        idx += CHUNK_SIZE

    with meta_lock:
        meta["files"][fname] = chunks
        METADATA_FILE.write_text(json.dumps(meta, indent=2))

    print(f"\n[Namenode] ✅ Upload completed for '{fname}'")
    print(f"[Namenode] 📦 {len(chunks)} chunks successfully distributed across datanodes.\n")

    flash(f"✅ File '{fname}' uploaded successfully!", "success")
    return redirect(url_for("index"))

@app.route("/download/<path:filename>")
def download(filename):
    with meta_lock:
        file_chunks = meta["files"].get(filename)
        if not file_chunks:
            return "file not found", 404

    print(f"\n[Namenode] 📥 Download requested for '{filename}'")
    assembled = bytearray()

    for cid in file_chunks:
        payload = None
        node_list = meta["chunks"].get(cid, [])
        print(f"[Namenode] 🔎 Retrieving chunk {cid[:8]} from nodes: {node_list}")

        for n in node_list:
            payload = retrieve_chunk_from_node(cid, n)
            if payload:
                print(f"[Namenode] ✅ Chunk {cid[:8]} successfully retrieved from node {n}")
                break
            else:
                print(f"[Namenode] ⚠ Chunk {cid[:8]} not found on node {n}")

        if not payload:
            print(f"[Namenode] ❌ Missing chunk {cid[:8]} — cannot assemble file.")
            return f"missing chunk {cid}", 500

        assembled.extend(payload)

    print(f"[Namenode] 📦 Successfully reassembled '{filename}' ({len(assembled)} bytes)")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(assembled)
        tmp_path = tmp.name

    return send_file(tmp_path, as_attachment=True, download_name=os.path.basename(filename))

# -------------------------- #
# Dashboard (Flask)
# -------------------------- #
@app.route("/")
def index():
    with meta_lock:
        now = time.time()
        nodes = {}
        for nid, info in meta["datanodes"].items():
            last = info.get("last_hb", 0)
            status = "ALIVE" if now - last < HEARTBEAT_TIMEOUT else "DEAD"
            nodes[nid] = {
                "status": status,
                "last_heartbeat": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)) if last > 0 else "never",
                "tcp_port": info.get("tcp_port"),
                "host": info.get("host")
            }
    return render_template("index.html", datanodes=nodes, files=meta["files"], chunks=meta["chunks"])

# -------------------------- #
# Periodic metadata save
# -------------------------- #
def periodic_persist():
    while True:
        time.sleep(5)
        with meta_lock:
            METADATA_FILE.write_text(json.dumps(meta, indent=2))

# -------------------------- #
# Main entrypoint
# -------------------------- #
if __name__ == "__main__":
    os.makedirs("storage/d0", exist_ok=True)
    os.makedirs("storage/d1", exist_ok=True)

    threading.Thread(target=heartbeat_listener_tcp, daemon=True).start()
    threading.Thread(target=periodic_persist, daemon=True).start()

    print("[Namenode] Flask dashboard running on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
