import sys
import os
import requests

def upload(path, namenode_ip):
    base = f"http://{namenode_ip}:5000"
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f)}
        r = requests.post(f"{base}/upload", files=files)
        try:
            print("Upload Response:", r.json())
        except Exception:
            print("Response:", r.status_code, r.text)

def download(filename, namenode_ip, outpath=None):
    base = f"http://{namenode_ip}:5000"
    url = f"{base}/download/{filename}"

    print(f"⬇  Downloading {filename} from {namenode_ip} ...")
    r = requests.get(url)

    if r.status_code == 200:
        # Use original filename by default
        if outpath is None:
            outpath = os.path.basename(filename)

        # Avoid overwriting existing file
        if os.path.exists(outpath):
            base, ext = os.path.splitext(outpath)
            outpath = f"{base}_copy{ext}"

        with open(outpath, "wb") as f:
            f.write(r.content)

        print(f"Downloaded successfully as '{outpath}'")
    else:
        print(f"Download failed: {r.status_code}, {r.text}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python3 client.py upload <path/to/file> <namenode_ip>")
        print("  python3 client.py download <filename> <namenode_ip>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "upload":
        upload(sys.argv[2], sys.argv[3])
    elif cmd == "download":
        download(sys.argv[2], sys.argv[3])
    else:
        print("Unknown command")
