import tkinter as tk
from tkinter import ttk, messagebox
from store import StoreManager


class SettingsTab(ttk.Frame):
    def __init__(self, parent, store: StoreManager, on_settings_applied):
        super().__init__(parent, padding=16)
        self.store = store
        self.on_settings_applied = on_settings_applied
        self._build_ui()
        self._load_from_store()
        self._on_scanner_mode_changed()

    def _build_ui(self):
        hw = ttk.LabelFrame(self, text="Eszközök csatlakoztatása (Vonalkódolvasó / Kamera / Terminál / Kassza)", padding=12)
        hw.pack(fill="x", pady=(0, 12))

        self.drawer_var = tk.BooleanVar()
        ttk.Checkbutton(hw, text="Kassza (kasszafiók) csatlakoztatva", variable=self.drawer_var).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=4
        )

        self.scanner_var = tk.BooleanVar()
        ttk.Checkbutton(hw, text="Vonalkódolvasó csatlakoztatva", variable=self.scanner_var).grid(
            row=1, column=0, sticky="w", pady=4
        )
        ttk.Label(hw, text="Mód:").grid(row=1, column=1, sticky="e", padx=4)
        self.scanner_mode_var = tk.StringVar()
        self.scanner_mode_combo = ttk.Combobox(
            hw,
            textvariable=self.scanner_mode_var,
            values=["USB-HID (Wireless/Wired)", "SERIAL (COM)", "CAMERA"],
            state="readonly",
            width=24,
        )
        self.scanner_mode_combo.grid(row=1, column=2, padx=4)
        self.scanner_mode_combo.bind("<<ComboboxSelected>>", lambda e: self._on_scanner_mode_changed())

        self.scanner_target_label_var = tk.StringVar(value="Port / Kamera # (0,1...):")
        ttk.Label(hw, textvariable=self.scanner_target_label_var).grid(row=1, column=3, sticky="e", padx=4)

        self.scanner_port_var = tk.StringVar()
        self.scanner_port_combo = ttk.Combobox(
            hw,
            textvariable=self.scanner_port_var,
            values=["AUTO / USB-HID"],
            state="normal",
            width=22,
        )
        self.scanner_port_combo.grid(row=1, column=4, padx=4)

        self.refresh_cam_btn = ttk.Button(hw, text="🔄 Kamerák", command=self.refresh_cameras)
        self.refresh_cam_btn.grid(row=1, column=5, padx=(4, 0))
        self.refresh_cam_btn.grid_remove()

        self.terminal_var = tk.BooleanVar()
        ttk.Checkbutton(hw, text="Bankkártya-terminál csatlakoztatva", variable=self.terminal_var).grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Label(hw, text="Mód:").grid(row=2, column=1, sticky="e", padx=4)
        self.terminal_mode_var = tk.StringVar()
        ttk.Combobox(
            hw,
            textvariable=self.terminal_mode_var,
            values=["SIM / AUTO", "SERIAL (COM)", "TCP / LAN"],
            state="readonly",
            width=24,
        ).grid(row=2, column=2, padx=4)

        ttk.Label(hw, text="Port/IP:").grid(row=2, column=3, sticky="e", padx=4)
        self.terminal_port_var = tk.StringVar()
        ttk.Entry(hw, textvariable=self.terminal_port_var, width=24).grid(row=2, column=4, padx=4)

        ttk.Button(hw, text="Eszközök tesztelése", command=self.test_devices).grid(
            row=3, column=0, columnspan=6, sticky="w", pady=(8, 0)
        )

        general = ttk.LabelFrame(self, text="Kassza és felület beállítások", padding=12)
        general.pack(fill="x", pady=(0, 12))

        ttk.Label(general, text="Kassza neve:").grid(row=0, column=0, sticky="w", pady=6)
        self.reg_name_var = tk.StringVar()
        ttk.Entry(general, textvariable=self.reg_name_var, width=28).grid(row=0, column=1, sticky="w", padx=8)

        ttk.Label(general, text="Nyelv:").grid(row=1, column=0, sticky="w", pady=6)
        self.lang_var = tk.StringVar()
        ttk.Combobox(general, textvariable=self.lang_var, values=["hu", "en"], state="readonly", width=10).grid(
            row=1, column=1, sticky="w", padx=8
        )

        self.touch_var = tk.BooleanVar()
        ttk.Checkbutton(
            general,
            text="Érintőképernyő mód (nagyobb gombok és sorok touch-hoz)",
            variable=self.touch_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

        ttk.Label(general, text="Egyedi díj neve (+<név>):").grid(row=3, column=0, sticky="w", pady=6)
        self.fee_name_var = tk.StringVar()
        ttk.Entry(general, textvariable=self.fee_name_var, width=24).grid(row=3, column=1, sticky="w", padx=8)

        ttk.Label(general, text="Egyedi díj ára (Ft):").grid(row=3, column=2, sticky="e", pady=6, padx=(12, 4))
        self.fee_amount_var = tk.StringVar()
        ttk.Entry(general, textvariable=self.fee_amount_var, width=12).grid(row=3, column=3, sticky="w", padx=4)

        ttk.Button(self, text="Beállítások mentése és alkalmazása", command=self.save_settings).pack(anchor="e")

    def _on_scanner_mode_changed(self):
        mode = self.scanner_mode_var.get()
        if mode == "CAMERA":
            self.scanner_target_label_var.set("Kamera:")
            self.refresh_cam_btn.grid()
            self.refresh_cameras(select_if_empty=True)
        elif mode == "SERIAL (COM)":
            self.scanner_target_label_var.set("COM port:")
            self.refresh_cam_btn.grid_remove()
            ports = self.store.hardware.available_com_ports()
            self.scanner_port_combo.configure(values=ports or ["COM3"])
        else:
            self.scanner_target_label_var.set("Port / mód:")
            self.refresh_cam_btn.grid_remove()
            self.scanner_port_combo.configure(values=["AUTO / USB-HID"])
            if not self.scanner_port_var.get().strip() or self.scanner_port_var.get().strip().isdigit():
                self.scanner_port_var.set("AUTO / USB-HID")

    def refresh_cameras(self, select_if_empty: bool = False):
        cams = self.store.hardware.detect_cameras()
        if cams:
            self.scanner_port_combo.configure(values=cams)
            current = self.scanner_port_var.get().strip()
            if select_if_empty or not current or current == "AUTO / USB-HID":
                self.scanner_port_var.set(cams[0])
        else:
            self.scanner_port_combo.configure(values=["0 (Kamera #0)", "1 (Kamera #1)"])
            if select_if_empty and (not self.scanner_port_var.get().strip() or self.scanner_port_var.get().strip() == "AUTO / USB-HID"):
                self.scanner_port_var.set("0 (Kamera #0)")

    def _load_from_store(self):
        s = self.store.settings
        self.drawer_var.set(s.cash_drawer_connected)
        self.scanner_var.set(s.scanner_connected)
        self.scanner_mode_var.set(s.scanner_mode)
        self.scanner_port_var.set(s.scanner_port)
        self.terminal_var.set(s.card_terminal_connected)
        self.terminal_mode_var.set(s.terminal_mode)
        self.terminal_port_var.set(s.terminal_port)
        self.reg_name_var.set(s.register_name)
        self.lang_var.set(s.language)
        self.touch_var.set(s.touch_mode)
        self.fee_name_var.set(s.custom_fee_name)
        self.fee_amount_var.set(str(s.custom_fee_amount) if s.custom_fee_amount else "")

    def test_devices(self):
        prev_s = (
            self.store.settings.scanner_connected,
            self.store.settings.scanner_mode,
            self.store.settings.scanner_port,
            self.store.settings.card_terminal_connected,
            self.store.settings.terminal_mode,
            self.store.settings.terminal_port,
        )
        self.store.settings.scanner_connected = self.scanner_var.get()
        self.store.settings.scanner_mode = self.scanner_mode_var.get()
        self.store.settings.scanner_port = self.scanner_port_var.get().strip()
        self.store.settings.card_terminal_connected = self.terminal_var.get()
        self.store.settings.terminal_mode = self.terminal_mode_var.get()
        self.store.settings.terminal_port = self.terminal_port_var.get().strip()

        sc_ok, sc_msg = self.store.hardware.test_scanner()
        term_ok, term_msg = self.store.hardware.process_card_payment(100, 0)

        (
            self.store.settings.scanner_connected,
            self.store.settings.scanner_mode,
            self.store.settings.scanner_port,
            self.store.settings.card_terminal_connected,
            self.store.settings.terminal_mode,
            self.store.settings.terminal_port,
        ) = prev_s

        msg = (
            f"Kassza: {'CSATLAKOZTATVA' if self.drawer_var.get() else 'Nincs kapcsolat'}\n"
            f"Olvasó ({'OK' if sc_ok else 'HIBA'}): {sc_msg}\n"
            f"Terminál teszt ({'OK' if term_ok else 'HIBA'}): {term_msg}"
        )
        messagebox.showinfo("Eszközteszt", msg)

    def save_settings(self):
        raw_fee_name = self.fee_name_var.get().strip().lstrip("+").strip()
        raw_fee_amt = self.fee_amount_var.get().strip()

        if raw_fee_amt == "":
            fee_amount = 0
        else:
            try:
                fee_amount = int(raw_fee_amt)
                if fee_amount < 0:
                    messagebox.showwarning("Hibás egyedi díj ár", "Az egyedi díj ára nem lehet negatív.")
                    return
            except ValueError:
                messagebox.showwarning("Hibás egyedi díj ár", "Az egyedi díj árának egész számnak kell lennie.")
                return

        if raw_fee_name and fee_amount <= 0:
            messagebox.showwarning("Hiányzó egyedi díj ár", "Adj meg 0-nál nagyobb árat az egyedi díjhoz.")
            return

        s = self.store.settings
        s.cash_drawer_connected = self.drawer_var.get()
        s.scanner_connected = self.scanner_var.get()
        s.scanner_mode = self.scanner_mode_var.get()
        s.scanner_port = self.scanner_port_var.get().strip() or ("0 (Kamera #0)" if s.scanner_mode == "CAMERA" else "AUTO / USB-HID")
        s.card_terminal_connected = self.terminal_var.get()
        s.terminal_mode = self.terminal_mode_var.get()
        s.terminal_port = self.terminal_port_var.get().strip() or "COM3 / LAN"
        s.register_name = self.reg_name_var.get().strip() or "Kassza #01"
        s.language = self.lang_var.get()
        s.touch_mode = self.touch_var.get()
        s.custom_fee_name = raw_fee_name
        s.custom_fee_amount = fee_amount

        self.store.save()
        self.on_settings_applied()
        messagebox.showinfo("Mentve", "A beállítások elmentve és érvényesítve.")