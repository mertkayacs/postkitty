"""Record YuNet face detections for demo media in postkitty's faces.json format.

Runs in GitHub Actions only (see .github/workflows/demo-detect.yml). Videos are sampled exactly like
engine/video/scan.py does (ffmpeg, 5 fps, 640 px wide) so the output can be dropped into a job cache.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
SAMPLE_FPS = 5.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect(detector, image: np.ndarray, sx: float, sy: float) -> list[dict]:
    detector.setInputSize((image.shape[1], image.shape[0]))
    _, found = detector.detect(image)
    faces = []
    for row in [] if found is None else found:
        x, y, w, h = (float(v) for v in row[:4])
        points = row[4:14].reshape(5, 2)
        faces.append({
            "x": x * sx, "y": y * sy, "w": w * sx, "h": h * sy, "score": float(row[14]),
            "landmarks": [[float(px) * sx, float(py) * sy] for px, py in points],
        })
    return faces


def probe(path: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate",
         "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout
    stream = json.loads(out)["streams"][0]
    num, den = stream["avg_frame_rate"].split("/")
    return int(stream["width"]), int(stream["height"]), float(num) / float(den or 1)


def video_doc(path: Path, detector) -> dict:
    width, height, fps = probe(path)
    sw = min(640, width)
    sh = max(2, round(height * sw / width / 2) * 2)
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path),
         "-vf", f"fps={SAMPLE_FPS},scale={sw}:{sh}", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"],
        stdout=subprocess.PIPE)
    frames, size, index = [], sw * sh * 3, 0
    while True:
        raw = proc.stdout.read(size)
        if len(raw) != size:
            break
        image = np.frombuffer(raw, dtype=np.uint8).reshape((sh, sw, 3))
        frames.append({"t": index / SAMPLE_FPS, "faces": detect(detector, image, width / sw, height / sh)})
        index += 1
    proc.wait()
    return {"width": width, "height": height, "fps": fps, "sample_fps": SAMPLE_FPS, "frames": frames}


def image_doc(path: Path, detector) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    height, width = image.shape[:2]
    scale = min(1.0, 1280 / max(width, height))
    small = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    sx, sy = width / small.shape[1], height / small.shape[0]
    return {"width": width, "height": height, "fps": None, "sample_fps": None,
            "frames": [{"t": 0.0, "faces": detect(detector, small, sx, sy)}]}


def main() -> None:
    media, out, model = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    out.mkdir(parents=True, exist_ok=True)
    detector = cv2.FaceDetectorYN.create(model, "", (320, 320), 0.6, 0.3, 5000)
    for path in sorted(media.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in VIDEO | IMAGE:
            continue
        doc = video_doc(path, detector) if suffix in VIDEO else image_doc(path, detector)
        digest = sha256(path)
        doc = {"schema": "postkitty.faces/1", "source_sha256": digest, "detector": "yunet-2023mar", **doc}
        text = json.dumps(doc, separators=(",", ":"))
        (out / f"{path.stem}.faces.json").write_text(text)
        (out / f"{digest}.json").write_text(text)
        counts = [len(frame["faces"]) for frame in doc["frames"]]
        print(f"{path.name}: {len(counts)} frames, faces per frame min {min(counts)} max {max(counts)} "
              f"mean {sum(counts) / len(counts):.2f}")


if __name__ == "__main__":
    main()
