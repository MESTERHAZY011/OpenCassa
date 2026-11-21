import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from store import StoreManager, Product


class ProductsTab(ttk.Frame):
    def __init__(self, parent, store: StoreManager, on_products_changed):
        super().__init__(parent, padding=12)
        self.store = store
        self.on_products_changed = on_products_changed
        self.style = ttk.Style(self)
        self.selected_image_path: str | None = None
        self.preview_photo: tk.PhotoImage | None = None
        self._waiting_for_device_scan = False
        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        form = ttk.LabelFrame(self, text="Új termék hozzáadása", padding=12)
        form.pack(fill="x", pady=(0, 12))

        ttk.Label(form, text="Név*:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=22).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(form, text="Ikon:").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.icon_var = tk.StringVar(value="📦")
        ttk.Entry(form, textvariable=self.icon_var, width=8).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(form, text="Termékkód*:").grid(row=0, column=4, sticky="w", padx=4, pady=4)
        self.code_var = tk.StringVar()
        self.code_var.trace_add("write", self._sanitize_code_var)
        self.code_entry = ttk.Entry(form, textvariable=self.code_var, width=14)
        self.code_entry.grid(row=0, column=5, padx=4, pady=4)
        self.code_entry.bind("<asterisk>", lambda e: "break")
        self.code_entry.bind("<Key-asterisk>", lambda e: "break")

        ttk.Label(form, text="Vonalkód (opt.):").grid(row=0, column=6, sticky="w", padx=4, pady=4)
        bc_box = ttk.Frame(form)
        bc_box.grid(row=0, column=7, padx=4, pady=4, sticky="w")

        self.barcode_var = tk.StringVar()
        self.barcode_entry = ttk.Entry(bc_box, textvariable=self.barcode_var, width=16, state="readonly")
        self.barcode_entry.pack(side="left")

        ttk.Button(bc_box, text="📷/🔍 Beolvas", command=self.trigger_barcode_scan).pack(side="left", padx=(4, 0))

        ttk.Label(form, text="Leírás:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.desc_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.desc_var, width=22).grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(form, text="Ár (Ft)*:").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.price_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.price_var, width=10).grid(row=1, column=3, padx=4, pady=4)

        ttk.Label(form, text="Mennyiség (opt.):").grid(row=1, column=4, sticky="w", padx=4, pady=4)
        self.unit_qty_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.unit_qty_var, width=14).grid(row=1, column=5, padx=4, pady=4)

        ttk.Label(form, text="Menny. ár (Ft):").grid(row=1, column=6, sticky="w", padx=4, pady=4)
        self.unit_price_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.unit_price_var, width=12).grid(row=1, column=7, padx=4, pady=4)

        img_row = ttk.Frame(form)
        img_row.grid(row=2, column=0, columnspan=8, sticky="we", pady=(8, 0))

        ttk.Button(img_row, text="Kép kiválasztása...", command=self.choose_image).pack(side="left")
        ttk.Button(img_row, text="Kép törlése", command=self.clear_image).pack(side="left", padx=(6, 12))

        self.img_label_var = tk.StringVar(value="Nincs kép kiválasztva")
        ttk.Label(img_row, textvariable=self.img_label_var).pack(side="left", padx=(0, 12))

        self.preview_box = ttk.Label(img_row)
        self.preview_box.pack(side="left")

        self.scan_hint_var = tk.StringVar(value="Vonalkód nem kötelező | '*' tilos a termékkódban.")
        ttk.Label(img_row, textvariable=self.scan_hint_var, font=("Arial", 9, "italic")).pack(side="left", padx=12)

        ttk.Button(img_row, text="+ Termék mentése", command=self.add_product).pack(side="right")

        cols = ("image", "code", "barcode", "name", "price", "alt_price", "description")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=13)
        headers = {
            "image": "Kép / Ikon",
            "code": "Termékkód",
            "barcode": "Vonalkód",
            "name": "Név",
            "price": "Ár (Ft)",
            "alt_price": "Mennyiség / Ár",
            "description": "Leírás",
        }
        for c, h in headers.items():
            self.tree.heading(c, text=h)
            self.tree.column(c, width=140 if c == "image" else (220 if c == "description" else 120), anchor="w")

        self.tree.pack(fill="both", expand=True)

    def _sanitize_code_var(self, *_args):
        current = self.code_var.get()
        if "*" in current:
            self.code_var.set(current.replace("*", ""))

    def is_waiting_for_scan(self) -> bool:
        return self._waiting_for_device_scan

    def receive_device_barcode(self, code: str) -> None:
        if not self._waiting_for_device_scan:
            return
        self._waiting_for_device_scan = False
        if code.startswith("__ERR__:"):
            self.scan_hint_var.set(code.replace("__ERR__:", "Olvasó hiba: "))
            return
        self.barcode_var.set(code.strip())
        self.scan_hint_var.set(f"Vonalkód beolvasva: {code.strip()}")

    def trigger_barcode_scan(self):
        if not self.store.settings.scanner_connected:
            messagebox.showwarning(
                "Nincs aktív olvasó",
                "Kapcsold be a vonalkódolvasót az 'Egyéb & Settings' fülön (USB-HID, COM vagy Kamera).",
            )
            return

        mode = self.store.settings.scanner_mode
        if mode.startswith("CAMERA"):
            self.scan_hint_var.set("Kamera megnyitása...")
            code = self.store.hardware.scan_with_camera_modal(self, title="Termék vonalkód beolvasása")
            if code:
                self.barcode_var.set(code)
                self.scan_hint_var.set(f"Kamerával beolvasva: {code}")
            else:
                self.scan_hint_var.set("Kamerás olvasás megszakítva vagy sikertelen.")
            return

        self._waiting_for_device_scan = True
        self.scan_hint_var.set("Várakozás a vonalkódolvasó jelzésére...")

    def _ask_image_source(self) -> str | None:
        win = tk.Toplevel(self)
        win.title("Kép forrása")
        win.geometry("380x160")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        choice = {"value": None}

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Honnan szeretnéd kiválasztani a termékképet?", font=("Arial", 10, "bold")).pack(
            anchor="w", pady=(0, 12)
        )

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(4, 0))

        def pick_own():
            choice["value"] = "own"
            win.grab_release()
            win.destroy()

        def pick_library():
            choice["value"] = "library"
            win.grab_release()
            win.destroy()

        def cancel():
            win.grab_release()
            win.destroy()

        ttk.Button(btns, text="💻 Saját kép a gépről", command=pick_own).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="🗂️ Képtár (simpleicons)", command=pick_library).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Mégse", command=cancel).pack(side="right")

        win.bind("<Escape>", lambda e: cancel())
        self.wait_window(win)
        return choice["value"]

    def _open_simpleicons_picker(self) -> str | None:
        icons = self.store.list_simpleicons()
        if not icons:
            messagebox.showinfo(
                "Üres vagy hiányzó képtár",
                "Nem található kép a 'simpleicons' mappában.\n"
                "Helyezz el PNG/JPG/WEBP ikonokat a 'simpleicons' mappába, vagy válassz saját képet.",
            )
            return None

        win = tk.Toplevel(self)
        win.title("Képtár — simpleicons")
        win.geometry("540x400")
        win.transient(self)
        win.grab_set()

        picked = {"path": None}
        preview_holder = {"img": None}

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Keresés:").pack(anchor="w")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(frame, textvariable=search_var)
        search_entry.pack(fill="x", pady=(2, 8))
        search_entry.focus_set()

        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)

        listbox = tk.Listbox(body, font=("Consolas", 11))
        listbox.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right = ttk.Frame(body, width=160)
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Előnézet:", font=("Arial", 10, "bold")).pack(pady=(4, 8))
        prev_lbl = ttk.Label(right)
        prev_lbl.pack(pady=8)
        name_lbl = ttk.Label(right, text="", wraplength=150, justify="center")
        name_lbl.pack(pady=4)

        filtered: list[str] = []

        def populate(*_args):
            q = search_var.get().strip().lower()
            listbox.delete(0, "end")
            filtered.clear()
            for p in icons:
                base = os.path.basename(p)
                if not q or q in base.lower():
                    filtered.append(p)
                    listbox.insert("end", base)
            if filtered:
                listbox.selection_set(0)
                on_select()
            else:
                preview_holder["img"] = None
                prev_lbl.configure(image="")
                name_lbl.configure(text="Nincs találat")

        def on_select(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            path = filtered[sel[0]]
            tk_img = self.store.load_tk_image(path, size=(96, 96))
            preview_holder["img"] = tk_img
            prev_lbl.configure(image=tk_img if tk_img else "")
            name_lbl.configure(text=os.path.basename(path))

        def confirm(_event=None):
            sel = listbox.curselection()
            if sel:
                picked["path"] = filtered[sel[0]]
            win.grab_release()
            win.destroy()

        def cancel(_event=None):
            win.grab_release()
            win.destroy()

        search_var.trace_add("write", populate)
        listbox.bind("<<ListboxSelect>>", on_select)
        listbox.bind("<Double-Button-1>", confirm)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Mégse", command=cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Kiválasztás", command=confirm).pack(side="right")

        win.bind("<Return>", confirm)
        win.bind("<Escape>", cancel)
        populate()
        self.wait_window(win)
        return picked["path"]

    def _apply_chosen_image(self, path: str):
        self.selected_image_path = path
        self.img_label_var.set(os.path.basename(path))
        self.preview_photo = self.store.load_tk_image(path, size=(42, 42))
        self.preview_box.configure(image=self.preview_photo if self.preview_photo else "")

    def choose_image(self):
        source = self._ask_image_source()
        if source == "own":
            path = filedialog.askopenfilename(
                title="Termékkép kiválasztása",
                filetypes=[
                    ("Képfájlok", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
                    ("Minden fájl", "*.*"),
                ],
            )
            if path:
                self._apply_chosen_image(path)
        elif source == "library":
            path = self._open_simpleicons_picker()
            if path:
                self._apply_chosen_image(path)

    def clear_image(self):
        self.selected_image_path = None
        self.preview_photo = None
        self.preview_box.configure(image="")
        self.img_label_var.set("Nincs kép kiválasztva")

    def add_product(self):
        name = self.name_var.get().strip()
        code = self.code_var.get().replace("*", "").strip()
        barcode = self.barcode_var.get().strip()
        icon = self.icon_var.get().strip() or "📦"
        desc = self.desc_var.get().strip()

        if not name or not code:
            messagebox.showwarning(
                "Hiányzó adat",
                "A név és a termékkód ('*' nélkül) megadása kötelező.",
            )
            return

        try:
            price = int(self.price_var.get().strip())
        except ValueError:
            messagebox.showwarning("Hibás ár", "Az árnak egész számnak kell lennie.")
            return

        unit_qty = self.unit_qty_var.get().strip() or None
        unit_price = None
        if self.unit_price_var.get().strip():
            try:
                unit_price = int(self.unit_price_var.get().strip())
            except ValueError:
                messagebox.showwarning("Hibás mennyiségi ár", "A mennyiségi árnak egész számnak kell lennie.")
                return

        saved_img_path = None
        if self.selected_image_path:
            saved_img_path = self.store.import_product_image(self.selected_image_path, code)

        prod = Product(
            code=code,
            barcode=barcode,
            name=name,
            icon=icon,
            description=desc,
            price=price,
            unit_qty=unit_qty,
            unit_price=unit_price,
            image_path=saved_img_path,
        )
        self.store.add_product(prod)

        for var in (self.name_var, self.code_var, self.barcode_var, self.desc_var,
                    self.price_var, self.unit_qty_var, self.unit_price_var):
            var.set("")
        self.icon_var.set("📦")
        self._waiting_for_device_scan = False
        self.scan_hint_var.set("Vonalkód nem kötelező | '*' tilos a termékkódban.")
        self.clear_image()

        self.refresh_list()
        self.on_products_changed()

    def refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for p in self.store.products:
            img_display = f"[KÉP] {os.path.basename(p.image_path)}" if p.image_path else p.icon
            alt = f"{p.unit_qty} / {p.unit_price} Ft" if (p.unit_qty and p.unit_price) else "-"
            bc_display = p.barcode or "-"
            self.tree.insert("", "end", values=(img_display, p.code, bc_display, p.name, p.price, alt, p.description))

    def apply_touch_mode(self, enabled: bool):
        row_h = 44 if enabled else 24
        font_sz = 12 if enabled else 10
        self.style.configure("Treeview", rowheight=row_h, font=("Arial", font_sz))
        self.style.configure("Treeview.Heading", font=("Arial", font_sz, "bold"))