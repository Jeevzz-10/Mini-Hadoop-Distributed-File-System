# 🧠 Mini-HDFS — Distributed File Storage System  
*A Simplified Python Implementation of Hadoop HDFS*

---

## 📜 Overview  
**Mini-HDFS** is a lightweight, Python-based distributed file storage system inspired by Hadoop’s HDFS.  
It allows users to upload and download files across multiple **Datanodes**, with a central **Namenode** handling metadata, replication, and coordination.  

It provides:  
- A **Flask Web Dashboard** for file and node monitoring.  
- **Command-line client** for uploading and downloading files.  
- **Heartbeat-based fault detection** and chunk replication.

---

## ⚙️ Core Components  

| Component | Description |
|------------|-------------|
| 🧭 **Namenode** | Manages metadata, handles uploads/downloads, coordinates Datanodes |
| 💾 **Datanode** | Stores file chunks, responds to chunk requests, sends heartbeats |
| 🧑‍💻 **Client** | Uploads and downloads files via REST API (HTTP) |

---

## 🧩 Features  

✅ File upload & download (via CLI or Web)  
✅ 2 MB chunking + automatic replication  
✅ TCP heartbeat monitoring (fault detection)  
✅ Flask dashboard for real-time visualization  
✅ Portable — works across Linux, Windows, and ZeroTier-linked devices  
✅ Safe download (auto-renames existing files)

---

## 🖥️ Architecture  

```
               +----------------------+
               |      Client (CLI)    |
               | Upload / Download    |
               +----------+-----------+
                          |
                     HTTP (5000)
                          |
               +----------------------+
               |     Namenode (Flask) |
               | Metadata + Routing   |
               | http://<namenode_ip>:5000 |
               +-----------+-----------+
                           |
         +-----------------+-----------------+
         |                                   |
 (TCP 7001)|                                   |(TCP 7002)
         ↓                                   ↓
 +------------------+             +------------------+
 | Datanode 0       |             | Datanode 1       |
 | storage/d0       |             | storage/d1       |
 +------------------+             +------------------+
```

---

## 🧰 Tech Stack

| Layer | Technology |
|--------|-------------|
| Backend | Python 3.x |
| Web | Flask, HTML, CSS (Jinja2 templates) |
| Networking | TCP Sockets |
| Communication | HTTP (Client ↔ Namenode), TCP (Namenode ↔ Datanode) |

---

## ⚙️ Installation

### 🧾 Requirements
- Python 3.8+
- Install dependencies:
  ```bash
  pip install flask requests
  ```

---

## 🚀 Running the System  

### **1️⃣ Start the Namenode**

On the **Namenode machine**:
```bash
python3 namenode.py
```

📍 Default ports:
- Web Dashboard → `http://0.0.0.0:5000`
- TCP Heartbeat → `6000`

---

### **2️⃣ Start Each Datanode**

On **each Datanode machine**:
```bash
python3 datanode.py <id> <port> <storage_dir> <namenode_ip>
```

**Example:**
```bash
python3 datanode.py 0 7001 storage/d0 192.168.X.X
python3 datanode.py 1 7002 storage/d1 192.168.X.X
```

✅ Expected output:
```
🟢 DATANODE 0 STARTED
💓 Heartbeat sent successfully
📦 Stored chunk ...
```

---

### **3️⃣ Upload Files**

#### 🖥️ Option A — Web Dashboard  
Open:  
```
http://<namenode_ip>:5000
```
Select your file → **Upload**

#### 💻 Option B — Client CLI  
```bash
python3 client.py upload <path/to/file> <namenode_ip>
```

**Example:**
```bash
python3 client.py upload example.txt 192.168.X.X
```

---

### **4️⃣ Download Files**

#### CLI:
```bash
python3 client.py download <filename> <namenode_ip>
```

✅ Example:
```
⬇  Downloading example.txt from 192.168.X.X ...
✅ Downloaded successfully as 'example.txt'
```

---

## 🧩 Dashboard

📍 URL: `http://<namenode_ip>:5000`  

Displays:
- Datanode Status (Alive / Dead + Last Heartbeat)  
- File Metadata (Filename, Chunk IDs)  
- Chunk Locations (Which Datanodes hold each chunk)  
- File Upload / Download controls  

---

## 🧠 How It Works

1️⃣ **Upload Process**
- File → split into 2 MB chunks.  
- Each chunk is replicated to multiple Datanodes.  
- Namenode records metadata (`files` and `chunks`).

2️⃣ **Heartbeat**
- Datanodes send heartbeats every 5 seconds.  
- Namenode marks nodes as ALIVE / DEAD.

3️⃣ **Download Process**
- Namenode retrieves chunks from available Datanodes.  
- Missing chunks are recovered from replicas.  
- Reassembled file is sent to client.

---

## 📦 Example Metadata (`metadata.json`)

```json
{
  "files": {
    "example.txt": [
      "c1a93a8a-4d12-4fbc-9c81-7d2234b92e87",
      "d45c789e-1ad1-441f-8e36-7f234b9f9123"
    ]
  },
  "chunks": {
    "c1a93a8a-4d12-4fbc-9c81-7d2234b92e87": ["0", "1"],
    "d45c789e-1ad1-441f-8e36-7f234b9f9123": ["1"]
  },
  "datanodes": {
    "0": {"host": "172.28.204.101", "tcp_port": 7001, "last_hb": 1731112025},
    "1": {"host": "172.28.204.102", "tcp_port": 7002, "last_hb": 1731112028}
  }
}
```

---

## 👨‍💻 Team Setup

| Role | Machine | Command |
|------|----------|----------|
| **Namenode** | Device A | `python3 namenode.py` |
| **Datanode 0** | Device B | `python3 datanode.py 0 7001 storage/d0 <namenode_ip>` |
| **Datanode 1** | Device C | `python3 datanode.py 1 7002 storage/d1 <namenode_ip>` |
| **Client** | Device D | `python3 client.py upload <file> <namenode_ip>` |

---

## 🧾 Folder Structure

```
Mini-HDFS/
│
├── namenode.py
├── datanode.py
├── client.py
├── metadata.json
├── templates/
│   └── index.html
└── README.md
```

---

## ⚠️ Notes

- All devices must be on the same network (LAN or ZeroTier).  
- Keep ports `5000`, `6000`, `7001`, `7002` open.  
- File downloads auto-rename duplicates to avoid overwrite.  
- Max upload size: 512 MB (by default).  

---

## 🧩 Example Commands

```bash
# Namenode
python3 namenode.py

# Datanodes
python3 datanode.py 0 7001 storage/d0 <namenode_ip>
python3 datanode.py 1 7002 storage/d1 <namenode_ip>

# Client
python3 client.py upload test.txt <namenode_ip>
python3 client.py download test.txt <namenode_ip>
```

---

## 🧠 Future Enhancements

🔸 Dynamic datanode registration  
🔸 Configurable replication factor  
🔸 Web-based deletion & recovery  
🔸 Performance metrics  

### 💡 Repository Info  
📦 Place the following files in your repository:
```
namenode.py
datanode.py
client.py
templates/index.html
README.md
metadata.json
```

Then commit and push:
```bash
git add .
git commit -m "Initial Mini-HDFS Project Upload"
git push -u origin main
```
