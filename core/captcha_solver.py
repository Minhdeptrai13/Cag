"""
Captcha solver for Garena login system
Uses ddddocr with computer vision fallback (OpenCV & PIL preprocessing)
"""
import io
import re
import threading
import uuid
from collections import Counter
import requests

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None
    ImageFilter = None

try:
    import ddddocr
except ImportError:
    ddddocr = None

_ocr_instances = {}
_ocr_lock = threading.Lock()


def get_ocr(beta: bool = False):
    """Get or lazily initialize cached ddddocr instance."""
    if ddddocr is None:
        return None
    key = "beta" if beta else "standard"
    if key not in _ocr_instances:
        with _ocr_lock:
            if key not in _ocr_instances:
                try:
                    _ocr_instances[key] = ddddocr.DdddOcr(show_ad=False, beta=beta)
                except Exception:
                    return None
    return _ocr_instances.get(key)


def solve_garena_captcha(proxy_dict=None) -> tuple[str, str]:
    """
    Generate key, download captcha image from Garena, and solve it.
    Returns: (captcha_key, captcha_code)
    """
    if ddddocr is None:
        return "", ""

    captcha_key = str(uuid.uuid4()).replace("-", "")
    url = f"http://captcha.garena.com/image?key={captcha_key}"

    try:
        resp = requests.get(url, proxies=proxy_dict, timeout=6, verify=False)
        if resp.status_code != 200 or not resp.content:
            return "", ""

        content = resp.content

        # High-accuracy OpenCV ensemble if available
        if cv2 is not None and np is not None:
            try:
                nparr = np.frombuffer(content, np.uint8)
                img_color = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img_color = cv2.resize(img_color, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

                ocr = get_ocr(beta=True) or get_ocr(beta=False)
                if ocr:
                    results = []
                    # 1. Raw color
                    _, buf1 = cv2.imencode(".png", img_color)
                    r1 = ocr.classification(buf1.tobytes())
                    if r1:
                        results.append(re.sub(r"[^A-Z0-9]", "", r1.upper()))

                    # 2. HSV mask for blue/dark text
                    hsv = cv2.cvtColor(img_color, cv2.COLOR_BGR2HSV)
                    mask = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
                    final2 = cv2.bitwise_not(mask)
                    _, buf2 = cv2.imencode(".png", final2)
                    r2 = ocr.classification(buf2.tobytes())
                    if r2:
                        results.append(re.sub(r"[^A-Z0-9]", "", r2.upper()))

                    # 3. Adaptive Gaussian Threshold
                    blur = cv2.GaussianBlur(img_gray, (3, 3), 0)
                    thresh3 = cv2.adaptiveThreshold(
                        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 6
                    )
                    final3 = cv2.bitwise_not(thresh3)
                    _, buf3 = cv2.imencode(".png", final3)
                    r3 = ocr.classification(buf3.tobytes())
                    if r3:
                        results.append(re.sub(r"[^A-Z0-9]", "", r3.upper()))

                    valid = [r for r in results if len(r) >= 5]
                    if valid:
                        res = Counter(valid).most_common(1)[0][0]
                        return captcha_key, res
                    elif results:
                        res = Counter(results).most_common(1)[0][0]
                        return captcha_key, res
            except Exception:
                pass

        # PIL Preprocessing fallback
        if Image is not None:
            try:
                img = Image.open(io.BytesIO(content)).convert("L")
                img = img.filter(ImageFilter.MedianFilter(size=3))
                img = img.point(lambda p: 0 if p < 140 else 255)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                content = buf.getvalue()
            except Exception:
                pass

        ocr = get_ocr(beta=False)
        if ocr:
            res = ocr.classification(content)
            res = re.sub(r"[^A-Z0-9]", "", res.upper()) if res else ""
            return captcha_key, res

        return "", ""
    except Exception:
        return "", ""
