import json
import os
import shutil
import socket
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, filedialog

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import serial
    from serial.tools import list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import cv2
    HAS_CV2 = True
    try:
        if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass
except ImportError:
    HAS_CV2 = False

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except ImportError:
    HAS_PYZBAR = False

try:
    import pypdfium2 as pdfium
    HAS_PDFIUM = True
except ImportError:
    HAS_PDFIUM = False

DATA_FILE = "store_data.json"
RECEIPTS_DIR = "receipts"
IMAGES_DIR = "product_images"
SIMPLEICONS_DIR = "simpleicons"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


@dataclass
class Product:
    code: str
    barcode: str
    name: str
    icon: str
    description: str
    price: int
    unit_qty: Optional[str] = None
    unit_price: Optional[int] = None
    image_path: Optional[str] = None


@dataclass
class CustomFee:
    name: str
    amount: int


@dataclass
class Settings:
    register_name: str = "Kassza #01"
    language: str = "hu"
    touch_mode: bool = False
    cash_drawer_connected: bool = False
    scanner_connected: bool = False
    card_terminal_connected: bool = False
    scanner_mode: str = "USB-HID (Wireless/Wired)"
    scanner_port: str = "AUTO / USB-HID"
    terminal_mode: str = "SIM / AUTO"
    terminal_port: str = "COM3 / LAN"
    terminal_timeout: float = 15.0
    custom_fee_name: str = ""
    custom_fee_amount: int = 0


class HardwareManager:
    """Kezeli a vonalkódolvasót (USB-HID, COM, Kamera, Kép/PDF) és a bankkártya-terminált."""

    def __init__(self, settings: Settings, on_barcode_scanned: Optional[Callable[[str], None]] = None):
        self.settings = settings
        self.on_barcode_scanned = on_barcode_scanned
        self._serial_stop = threading.Event()
        self._serial_thread: Optional[threading.Thread] = None
        self._cv_detector = None
        if HAS_CV2 and hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
            try:
                self._cv_detector = cv2.barcode.BarcodeDetector()
            except Exception:
                self._cv_detector = None

    @staticmethod
    def available_com_ports() -> List[str]:
        if not HAS_SERIAL:
            return []
        return [p.device for p in list_ports.comports()]

    @staticmethod
    def _camera_backends() -> List[int]:
        if HAS_CV2 and os.name == "nt":
            return [cv2.CAP_MSMF, cv2.CAP_ANY, cv2.CAP_DSHOW]
        if HAS_CV2:
            return [cv2.CAP_ANY]
        return []

    @classmethod
    def detect_cameras(cls, max_index: int = 8) -> List[str]:
        if not HAS_CV2:
            return []

        found: List[str] = []
        backends = cls._camera_backends()

        for idx in range(max_index):
            for backend in backends:
                cap = None
                try:
                    cap = cv2.VideoCapture(idx, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(idx)
                    if cap is not None and cap.isOpened():
                        ret = False
                        frame = None
                        for _ in range(4):
                            ret, frame = cap.read()
                            if ret and frame is not None and frame.size > 0:
                                break
                            time.sleep(0.05)
                        if ret and frame is not None and frame.size > 0:
                            found.append(f"{idx} (Kamera #{idx})")
                            break
                except Exception:
                    pass
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass

        return found

    def _open_camera(self, cam_idx: int):
        if not HAS_CV2:
            return None
        for backend in self._camera_backends():
            cap = None
            try:
                cap = cv2.VideoCapture(cam_idx, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(cam_idx)
                if cap is not None and cap.isOpened():
                    for _ in range(6):
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            return cap
                        time.sleep(0.05)
                    return cap
            except Exception:
                pass
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return None

    def start_scanner_listener(self) -> Tuple[bool, str]:
        self.stop_scanner_listener()
        if not self.settings.scanner_connected:
            return False, "Vonalkódolvasó kikapcsolva."

        if self.settings.scanner_mode.startswith("SERIAL"):
            if not HAS_SERIAL:
                return False, "Nincs telepítve a 'pyserial' csomag (pip install pyserial)."
            port = self.settings.scanner_port.strip()
            if not port or "AUTO" in port.upper() or port.isdigit():
                ports = self.available_com_ports()
                if not ports:
                    return False, "Nem található elérhető COM port."
                port = ports[0]

            self._serial_stop.clear()
            self._serial_thread = threading.Thread(
                target=self._serial_reader_loop, args=(port,), daemon=True
            )
            self._serial_thread.start()
            return True, f"Soros vonalkódolvasó figyelve: {port}"

        if self.settings.scanner_mode.startswith("CAMERA"):
            if not HAS_CV2:
                return False, "Kamera módhoz telepítsd az 'opencv-python' csomagot."
            return True, f"Kamera vonalkódolvasó készen áll (index: {self._get_camera_index()})"

        return True, f"USB-HID (vezetékes/vezeték nélküli) aktív ({self.settings.scanner_port})"

    def stop_scanner_listener(self) -> None:
        self._serial_stop.set()
        if self._serial_thread and self._serial_thread.is_alive():
            self._serial_thread.join(timeout=0.5)
        self._serial_thread = None

    def _get_camera_index(self) -> int:
        raw = (self.settings.scanner_port or "0").strip()
        if raw.isdigit():
            return int(raw)
        for token in raw.replace("/", " ").split():
            if token.isdigit():
                return int(token)
        return 0

    def _decode_single_variant(self, img_gray_or_bgr) -> Optional[str]:
        if HAS_PYZBAR:
            try:
                decoded = pyzbar.decode(img_gray_or_bgr)
                for obj in decoded:
                    val = obj.data.decode("utf-8", errors="ignore").strip()
                    if val:
                        return val
            except Exception:
                pass

        if self._cv_detector is not None:
            try:
                ok, decoded_info, _, _ = self._cv_detector.detectAndDecode(img_gray_or_bgr)
                if ok and decoded_info:
                    for info in decoded_info:
                        if info and info.strip():
                            return info.strip()
            except Exception:
                pass

        return None

    def _decode_frame(self, frame) -> Optional[str]:
        val = self._decode_single_variant(frame)
        if val:
            return val

        if not HAS_CV2:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        val = self._decode_single_variant(gray)
        if val:
            return val

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        val = self._decode_single_variant(enhanced)
        if val:
            return val

        enlarged = cv2.resize(enhanced, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        return self._decode_single_variant(enlarged)

    def scan_from_image_or_pdf(self, parent: tk.Misc) -> Optional[str]:
        path = filedialog.askopenfilename(
            parent=parent,
            title="Vonalkód beolvasása képből vagy PDF-ből",
            filetypes=[
                ("Kép és PDF fájlok", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.pdf"),
                ("PDF fájlok", "*.pdf"),
                ("Képfájlok", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
            ],
        )
        if not path:
            return None

        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            if not HAS_PDFIUM or not HAS_CV2:
                return None
            try:
                pdf = pdfium.PdfDocument(path)
                for page_idx in range(len(pdf)):
                    page = pdf[page_idx]
                    bitmap = page.render(scale=2.5)
                    pil_img = bitmap.to_pil()
                    import numpy as np
                    frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    code = self._decode_frame(frame)
                    if code:
                        return code
            except Exception:
                return None
            return None

        if HAS_CV2:
            frame = cv2.imread(path)
            if frame is not None and frame.size > 0:
                return self._decode_frame(frame)

        return None

    def scan_with_camera_modal(self, parent: tk.Misc, title: str = "Vonalkód beolvasása kamerával") -> Optional[str]:
        if not HAS_CV2:
            return None
        if not HAS_PYZBAR and self._cv_detector is None:
            return None

        cam_idx = self._get_camera_index()
        cap = self._open_camera(cam_idx)
        if cap is None:
            return None

        result: dict[str, Optional[str]] = {"code": None}
        photo_holder: dict[str, Optional[tk.PhotoImage]] = {"img": None}

        win = tk.Toplevel(parent)
        win.title(title)
        win.geometry("680x520")
        win.transient(parent)
        win.grab_set()

        ttk.Label(
            win,
            text="Tartsd a vonalkódot a kamera elé — sikeres olvasásnál automatikusan bezárul.",
            font=("Arial", 10, "bold"),
        ).pack(pady=(10, 6))

        video_label = ttk.Label(win)
        video_label.pack(expand=True)

        status_var = tk.StringVar(value=f"Kamera #{cam_idx} aktív — vonalkód keresése...")
        ttk.Label(win, textvariable=status_var).pack(pady=4)

        closed = {"flag": False}

        def close_cam():
            if closed["flag"]:
                return
            closed["flag"] = True
            try:
                cap.release()
            except Exception:
                pass
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass

        btn_bar = ttk.Frame(win)
        btn_bar.pack(pady=(0, 10))
        ttk.Button(btn_bar, text="📄 Kép / PDF betöltés", command=lambda: _pick_file_and_close()).pack(side="left", padx=6)
        ttk.Button(btn_bar, text="Mégse", command=close_cam).pack(side="left", padx=6)

        def _pick_file_and_close():
            code = self.scan_from_image_or_pdf(win)
            if code:
                result["code"] = code
                status_var.set(f"Beolvasva: {code}")
                win.after(120, close_cam)

        win.protocol("WM_DELETE_WINDOW", close_cam)

        def update_frame():
            if closed["flag"]:
                return
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                code = self._decode_frame(frame)
                if code:
                    result["code"] = code
                    status_var.set(f"Beolvasva: {code}")
                    win.after(150, close_cam)
                    return

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if HAS_PIL:
                    pil_img = Image.fromarray(rgb)
                    pil_img.thumbnail((620, 400), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                else:
                    _, buf = cv2.imencode(".png", cv2.resize(frame, (600, 380)))
                    tk_img = tk.PhotoImage(data=buf.tobytes())

                photo_holder["img"] = tk_img
                video_label.configure(image=tk_img)

            if not closed["flag"]:
                win.after(35, update_frame)

        update_frame()
        parent.wait_window(win)
        return result["code"]

    def _serial_reader_loop(self, port: str) -> None:
        try:
            with serial.Serial(port=port, baudrate=9600, timeout=0.2) as ser:
                buf = bytearray()
                while not self._serial_stop.is_set():
                    chunk = ser.read(64)
                    if not chunk:
                        continue
                    for b in chunk:
                        if b in (10, 13):
                            code = buf.decode("utf-8", errors="ignore").strip()
                            buf.clear()
                            if code and self.on_barcode_scanned:
                                self.on_barcode_scanned(code)
                        else:
                            buf.append(b)
        except Exception as exc:
            if self.on_barcode_scanned:
                self.on_barcode_scanned(f"__ERR__:{port}: {exc}")

    def test_scanner(self) -> Tuple[bool, str]:
        if not self.settings.scanner_connected:
            return False, "A vonalkódolvasó nincs bekapcsolva."

        if self.settings.scanner_mode.startswith("CAMERA"):
            if not HAS_CV2:
                return False, "Az 'opencv-python' csomag hiányzik."
            if not HAS_PYZBAR and self._cv_detector is None:
                return False, "Telepítsd a 'pyzbar' csomagot a vonalkód-dekódoláshoz."
            idx = self._get_camera_index()
            cap = self._open_camera(idx)
            if cap is not None:
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    return True, f"Kamera #{idx} sikeresen megnyitható és képet ad."
                return True, f"Kamera #{idx} megnyitva (ellenőrizd a képkockát)."
            return False, f"Nem sikerült megnyitni a #{idx} indexű kamerát."

        if self.settings.scanner_mode.startswith("SERIAL"):
            if not HAS_SERIAL:
                return False, "A 'pyserial' csomag hiányzik."
            port = self.settings.scanner_port.strip()
            try:
                with serial.Serial(port=port, baudrate=9600, timeout=1.0):
                    return True, f"Soros vonalkódolvasó elérhető a {port} porton."
            except Exception as exc:
                return False, f"Nem sikerült megnyitni a {port} portot: {exc}"

        return True, f"USB-HID olvasó készen áll ({self.settings.scanner_port})."

    def process_card_payment(self, amount: int, receipt_num: int) -> Tuple[bool, str]:
        if not self.settings.card_terminal_connected:
            return False, "A bankkártya-terminál nincs csatlakoztatva."

        mode = self.settings.terminal_mode
        target = self.settings.terminal_port.strip()

        if mode.startswith("TCP"):
            host, port = self._parse_host_port(target, default_port=2000)
            if not host:
                return False, f"Érvénytelen TCP/LAN cím: {target}"
            try:
                payload = json.dumps({
                    "cmd": "SALE",
                    "amount": amount,
                    "currency": "HUF",
                    "receipt_no": receipt_num,
                }).encode("utf-8")
                with socket.create_connection((host, port), timeout=min(self.settings.terminal_timeout, 5.0)) as sock:
                    sock.sendall(payload + b"\n")
                    resp = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                return True, f"LAN terminál jóváhagyva ({host}:{port}) | Válasz: {resp or 'APPROVED'}"
            except Exception as exc:
                return False, f"LAN terminál hiba ({host}:{port}): {exc}"

        if mode.startswith("SERIAL"):
            if not HAS_SERIAL:
                return False, "A 'pyserial' csomag hiányzik a soros terminálhoz."
            port = target.split("/")[0].strip()
            try:
                with serial.Serial(port=port, baudrate=9600, timeout=2.0) as ser:
                    cmd = f"SALE:{amount}:HUF:{receipt_num}\n".encode("utf-8")
                    ser.write(cmd)
                    raw_resp = ser.readline().decode("utf-8", errors="ignore").strip()
                if "DECLIN" in raw_resp.upper() or "ERR" in raw_resp.upper():
                    return False, f"Terminál elutasította: {raw_resp}"
                auth = raw_resp or f"AUTH-{int(time.time()) % 1000000:06d}"
                return True, f"Soros terminál ({port}) OK | Auth: {auth}"
            except Exception as exc:
                return False, f"Soros terminál hiba ({port}): {exc}"

        auth_code = f"SIM-{int(time.time()) % 1000000:06d}"
        return True, f"Terminál jóváhagyva ({target}) | {amount} Ft | Auth: {auth_code}"

    @staticmethod
    def _parse_host_port(addr: str, default_port: int = 2000) -> Tuple[Optional[str], int]:
        cleaned = addr.replace("tcp://", "").strip()
        if ":" in cleaned:
            host, p_str = cleaned.rsplit(":", 1)
            try:
                return host.strip(), int(p_str.strip())
            except ValueError:
                return None, default_port
        if cleaned:
            return cleaned, default_port
        return None, default_port


class StoreManager:
    def __init__(
        self,
        filepath: str = DATA_FILE,
        receipts_dir: str = RECEIPTS_DIR,
        images_dir: str = IMAGES_DIR,
        simpleicons_dir: str = SIMPLEICONS_DIR,
        on_barcode_scanned: Optional[Callable[[str], None]] = None,
    ):
        self.filepath = filepath
        self.receipts_dir = receipts_dir
        self.images_dir = images_dir
        self.simpleicons_dir = simpleicons_dir
        self.settings = Settings()
        self.products: List[Product] = []
        self.next_receipt_number: int = 1
        self.load()
        self.hardware = HardwareManager(self.settings, on_barcode_scanned=on_barcode_scanned)

    def get_simpleicons_dir(self) -> Optional[str]:
        candidates = [
            self.simpleicons_dir,
            os.path.join(os.path.dirname(os.path.abspath(self.filepath)), self.simpleicons_dir),
            "/simpleicons",
        ]
        for path in candidates:
            if path and os.path.isdir(path):
                return path
        return None

    def list_simpleicons(self) -> List[str]:
        folder = self.get_simpleicons_dir()
        if not folder:
            return []
        files: List[str] = []
        for fname in sorted(os.listdir(folder), key=lambda s: s.lower()):
            full = os.path.join(folder, fname)
            if os.path.isfile(full) and fname.lower().endswith(IMAGE_EXTENSIONS):
                files.append(full)
        return files

    def get_configured_custom_fee(self) -> Optional[CustomFee]:
        name = (self.settings.custom_fee_name or "").strip().lstrip("+").strip()
        amount = int(self.settings.custom_fee_amount or 0)
        if name and amount > 0:
            return CustomFee(name=name, amount=amount)
        return None

    def _default_products(self) -> List[Product]:
        return [
            Product("T001", "5990001001", "Ásványvíz", "💧", "Szénsavmentes 1.5L", 250, "6 pack", 1350, None),
            Product("T002", "5990001002", "Kenyér", "🍞", "Fehér kenyér 1 kg", 690, None, None, None),
            Product("T003", "5990001003", "Kávé", "☕", "Pörkölt szemes kávé", 3490, "250g", 1190, None),
            Product("T004", "5990001004", "Csokoládé", "🍫", "Étcsokoládé tábla", 590, None, None, None),
        ]

    def load(self) -> None:
        if not os.path.exists(self.filepath):
            self.products = self._default_products()
            self.next_receipt_number = 1
            self.save()
            return

        with open(self.filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.next_receipt_number = max(1, int(raw.get("next_receipt_number", 1)))
        s_raw = raw.get("settings", {})
        self.settings = Settings(
            register_name=s_raw.get("register_name", "Kassza #01"),
            language=s_raw.get("language", "hu"),
            touch_mode=bool(s_raw.get("touch_mode", False)),
            cash_drawer_connected=bool(s_raw.get("cash_drawer_connected", False)),
            scanner_connected=bool(s_raw.get("scanner_connected", False)),
            card_terminal_connected=bool(s_raw.get("card_terminal_connected", False)),
            scanner_mode=s_raw.get("scanner_mode", "USB-HID (Wireless/Wired)"),
            scanner_port=s_raw.get("scanner_port", "AUTO / USB-HID"),
            terminal_mode=s_raw.get("terminal_mode", "SIM / AUTO"),
            terminal_port=s_raw.get("terminal_port", "COM3 / LAN"),
            terminal_timeout=float(s_raw.get("terminal_timeout", 15.0)),
            custom_fee_name=s_raw.get("custom_fee_name", ""),
            custom_fee_amount=int(s_raw.get("custom_fee_amount", 0) or 0),
        )

        p_list = raw.get("products", [])
        self.products = [Product(**item) for item in p_list]

    def save(self) -> None:
        payload = {
            "next_receipt_number": self.next_receipt_number,
            "settings": asdict(self.settings),
            "products": [asdict(p) for p in self.products],
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def import_product_image(self, source_path: str, code: str) -> str:
        os.makedirs(self.images_dir, exist_ok=True)
        _, ext = os.path.splitext(source_path)
        ext = ext.lower() or ".png"
        safe_code = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in code.strip() or "item")
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest_path = os.path.join(self.images_dir, f"{safe_code}_{ts}{ext}")
        shutil.copy2(source_path, dest_path)
        return dest_path

    def load_tk_image(self, image_path: Optional[str], size: Tuple[int, int] = (48, 48)) -> Optional[tk.PhotoImage]:
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            if HAS_PIL:
                img = Image.open(image_path).convert("RGBA")
                img.thumbnail(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            img = tk.PhotoImage(file=image_path)
            w, h = img.width(), img.height()
            max_w, max_h = size
            scale = max(1, (w + max_w - 1) // max_w, (h + max_h - 1) // max_h)
            if scale > 1:
                img = img.subsample(scale, scale)
            return img
        except Exception:
            return None

    def add_product(self, product: Product) -> None:
        self.products.append(product)
        self.save()

    def find_product(self, query: str) -> Optional[Product]:
        q = query.strip().lower()
        if not q:
            return None
        for p in self.products:
            if p.code.strip().lower() == q or p.barcode.strip().lower() == q:
                return p
        return None

    def build_receipt(
        self,
        items: List[tuple[Product, int, int]],
        payment_method: str,
        receipt_number: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        terminal_info: Optional[str] = None,
        custom_fees: Optional[List[CustomFee]] = None,
    ) -> str:
        dt = timestamp or datetime.now()
        now = dt.strftime("%Y-%m-%d %H:%M:%S")
        num_str = f"{receipt_number:06d}" if receipt_number is not None else "------"
        fees = custom_fees or []
        total = sum(line_total for _, _, line_total in items) + sum(f.amount for f in fees)

        lines = [
            "=" * 34,
            f"  {self.settings.register_name}",
            f"  Nyugtaszám: #{num_str}",
            f"  Dátum: {now}",
            "-" * 34,
        ]
        for prod, qty, line_total in items:
            lines.append(f"{prod.icon} {prod.name} ({prod.code}) x{qty}")
            lines.append(f"    {line_total} Ft")
        for fee in fees:
            lines.append(f"+ {fee.name} díj")
            lines.append(f"    {fee.amount} Ft")
        lines.extend([
            "-" * 34,
            f"FIZETÉSI MÓD: {payment_method}",
            f"VÉGÖSSZEG:     {total} Ft",
            f"KASSZA FIÓK:  {'NYITVA' if self.settings.cash_drawer_connected else 'NINCS CSATLAKOZTATVA'}",
            f"TERMINÁL:     {terminal_info or ('OK' if self.settings.card_terminal_connected else 'NINCS CSATLAKOZTATVA')}",
            "=" * 34,
        ])
        return "\n".join(lines)

    def save_receipt(
        self,
        items: List[tuple[Product, int, int]],
        payment_method: str,
        terminal_info: Optional[str] = None,
        custom_fees: Optional[List[CustomFee]] = None,
    ) -> Tuple[str, str, int]:
        os.makedirs(self.receipts_dir, exist_ok=True)
        receipt_num = self.next_receipt_number
        dt = datetime.now()
        receipt_text = self.build_receipt(
            items=items,
            payment_method=payment_method,
            receipt_number=receipt_num,
            timestamp=dt,
            terminal_info=terminal_info,
            custom_fees=custom_fees,
        )

        filename = f"nyugta_{receipt_num:06d}_{dt.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(self.receipts_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(receipt_text + "\n")

        self.next_receipt_number += 1
        self.save()

        return receipt_text, filepath, receipt_num