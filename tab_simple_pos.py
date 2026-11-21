import tkinter as tk
from tkinter import ttk, messagebox
from store import StoreManager, Product, CustomFee


class SimplePosTab(ttk.Frame):
    def __init__(self, parent, store: StoreManager):
        super().__init__(parent, padding=12)
        self.store = store
        self.cart: dict[str, tuple[Product, int, int]] = {}
        self.custom_fees: list[CustomFee] = []
        self.photo_refs: list[tk.PhotoImage] = []
        self._build_ui()
        self.refresh_products()
        self.refresh_fee_button()
        self._render_cart()

    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.LabelFrame(paned, text="Termékek (koppints vagy kattints)", padding=10)
        paned.add(left, weight=3)

        self.canvas = tk.Canvas(left, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        self.items_frame = ttk.Frame(self.canvas)

        self.items_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.items_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        right = ttk.LabelFrame(paned, text="Kosár, fizetés és nyugta", padding=10)
        paned.add(right, weight=2)

        cart_container = ttk.Frame(right)
        cart_container.pack(fill="both", expand=True, pady=(0, 8))

        self.cart_canvas = tk.Canvas(cart_container, highlightthickness=0, height=190)
        cart_scroll = ttk.Scrollbar(cart_container, orient="vertical", command=self.cart_canvas.yview)
        self.cart_rows_frame = ttk.Frame(self.cart_canvas)

        self.cart_rows_frame.bind(
            "<Configure>",
            lambda e: self.cart_canvas.configure(scrollregion=self.cart_canvas.bbox("all"))
        )
        self.cart_canvas_win = self.cart_canvas.create_window((0, 0), window=self.cart_rows_frame, anchor="nw")
        self.cart_canvas.configure(yscrollcommand=cart_scroll.set)
        self.cart_canvas.bind(
            "<Configure>",
            lambda e: self.cart_canvas.itemconfigure(self.cart_canvas_win, width=e.width)
        )

        self.cart_canvas.pack(side="left", fill="both", expand=True)
        cart_scroll.pack(side="right", fill="y")

        self.total_var = tk.StringVar(value="Fizetendő: 0 Ft")
        ttk.Label(right, textvariable=self.total_var, font=("Arial", 15, "bold")).pack(anchor="e", pady=(0, 8))

        ttk.Label(right, text="Fizetési mód:").pack(anchor="w")
        self.pay_method = tk.StringVar(value="Készpénz")
        pay_row = ttk.Frame(right)
        pay_row.pack(fill="x", pady=4)
        ttk.Radiobutton(pay_row, text="Készpénz", variable=self.pay_method, value="Készpénz").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(pay_row, text="Kártya", variable=self.pay_method, value="Kártya").pack(side="left")

        btn_row = ttk.Frame(right)
        btn_row.pack(fill="x", pady=8)
        self.fee_btn = ttk.Button(btn_row, text="+ Egyedi díj", command=self.add_configured_fee)
        self.fee_btn.pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Törlés", command=self.clear_cart).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Fizetés & Nyugta", command=self.checkout).pack(side="right")

        self.receipt_box = tk.Text(right, height=10, font=("Consolas", 9), state="disabled")
        self.receipt_box.pack(fill="both", expand=True)

    def refresh_fee_button(self):
        fee = self.store.get_configured_custom_fee()
        if fee:
            self.fee_btn.configure(text=f"+{fee.name} ({fee.amount} Ft)")
        else:
            self.fee_btn.configure(text="+ Egyedi díj")

    def add_configured_fee(self):
        fee = self.store.get_configured_custom_fee()
        if not fee:
            messagebox.showinfo(
                "Nincs beállított egyedi díj",
                "Add meg az egyedi díj nevét és árát az 'Egyéb & Settings' fülön, majd mentsd el.",
            )
            return
        self.custom_fees.append(CustomFee(name=fee.name, amount=fee.amount))
        self._render_cart()

    def refresh_products(self):
        for w in self.items_frame.winfo_children():
            w.destroy()
        self.photo_refs.clear()

        touch = self.store.settings.touch_mode
        pad_y = 10 if touch else 4
        font_sz = 13 if touch else 10
        img_size = (64, 64) if touch else (44, 44)

        for p in self.store.products:
            row = ttk.Frame(self.items_frame, padding=4)
            row.pack(fill="x", pady=2)

            tk_img = self.store.load_tk_image(p.image_path, size=img_size)
            if tk_img is not None:
                self.photo_refs.append(tk_img)
                label_txt = f"  {p.name}  —  {p.price} Ft"
            else:
                label_txt = f"{p.icon}  {p.name}  —  {p.price} Ft"

            if p.unit_qty and p.unit_price:
                label_txt += f"  (vagy {p.unit_qty}: {p.unit_price} Ft)"

            btn_main = tk.Button(
                row,
                text=label_txt,
                image=tk_img if tk_img is not None else "",
                compound="left" if tk_img is not None else "none",
                font=("Arial", font_sz),
                pady=pad_y,
                padx=8,
                anchor="w",
                command=lambda prod=p: self.add_to_cart(prod, prod.price, "alap")
            )
            btn_main.pack(side="left", fill="x", expand=True)

            if p.unit_qty and p.unit_price:
                btn_alt = tk.Button(
                    row,
                    text=f"+ {p.unit_qty} ({p.unit_price} Ft)",
                    font=("Arial", font_sz - 1),
                    pady=pad_y,
                    command=lambda prod=p: self.add_to_cart(prod, prod.unit_price, p.unit_qty)
                )
                btn_alt.pack(side="left", padx=(6, 0))

    def add_to_cart(self, prod: Product, amount: int, variant_label: str):
        key = f"{prod.code}_{variant_label}"
        if key in self.cart:
            _, qty, line_sum = self.cart[key]
            self.cart[key] = (prod, qty + 1, line_sum + amount)
        else:
            self.cart[key] = (prod, 1, amount)
        self._render_cart()

    def remove_cart_item(self, key: str):
        if key in self.cart:
            del self.cart[key]
            self._render_cart()

    def remove_custom_fee(self, idx: int):
        if 0 <= idx < len(self.custom_fees):
            self.custom_fees.pop(idx)
            self._render_cart()

    def clear_cart(self):
        self.cart.clear()
        self.custom_fees.clear()
        self._render_cart()

    def _render_cart(self):
        for w in self.cart_rows_frame.winfo_children():
            w.destroy()

        touch = self.store.settings.touch_mode
        row_font = ("Consolas", 12 if touch else 10)
        trash_font = ("Arial", 11 if touch else 9)

        total = 0

        for key, (prod, qty, line_sum) in list(self.cart.items()):
            total += line_sum
            row = ttk.Frame(self.cart_rows_frame, padding=(2, 2))
            row.pack(fill="x")

            lbl = tk.Label(
                row,
                text=f"{qty}x {prod.icon} {prod.name}  —  {line_sum} Ft",
                font=row_font,
                anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            trash_btn = tk.Button(
                row,
                text="🗑️",
                font=trash_font,
                bd=1,
                padx=4,
                pady=1,
                command=lambda k=key: self.remove_cart_item(k),
            )
            trash_btn.pack(side="right", padx=(4, 0))

        for idx, fee in enumerate(self.custom_fees):
            total += fee.amount
            row = ttk.Frame(self.cart_rows_frame, padding=(2, 2))
            row.pack(fill="x")

            lbl = tk.Label(
                row,
                text=f"+{fee.name} díj  —  {fee.amount} Ft",
                font=row_font,
                anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            trash_btn = tk.Button(
                row,
                text="🗑️",
                font=trash_font,
                bd=1,
                padx=4,
                pady=1,
                command=lambda i=idx: self.remove_custom_fee(i),
            )
            trash_btn.pack(side="right", padx=(4, 0))

        if not self.cart and not self.custom_fees:
            tk.Label(
                self.cart_rows_frame,
                text="A kosár üres",
                font=("Arial", 10, "italic"),
                fg="gray",
            ).pack(anchor="w", pady=6)

        self.total_var.set(f"Fizetendő: {total} Ft")

    def checkout(self):
        if not self.cart and not self.custom_fees:
            messagebox.showinfo("Üres kosár", "Válassz ki legalább egy terméket vagy díjat.")
            return

        items_list = list(self.cart.values())
        fees_list = list(self.custom_fees)
        total = sum(line_total for _, _, line_total in items_list) + sum(f.amount for f in fees_list)
        terminal_info = None

        if self.pay_method.get() == "Kártya":
            ok, info = self.store.hardware.process_card_payment(total, self.store.next_receipt_number)
            if not ok:
                messagebox.showwarning("Terminál", info)
                return
            terminal_info = info

        receipt_text, filepath, receipt_num = self.store.save_receipt(
            items=items_list,
            payment_method=self.pay_method.get(),
            terminal_info=terminal_info,
            custom_fees=fees_list,
        )
        self.receipt_box.configure(state="normal")
        self.receipt_box.delete("1.0", "end")
        self.receipt_box.insert("1.0", receipt_text)
        self.receipt_box.configure(state="disabled")

        messagebox.showinfo("Nyugta mentve", f"Nyugta #{receipt_num:06d} elmentve:\n{filepath}")
        self.clear_cart()

    def apply_touch_mode(self, enabled: bool):
        self.refresh_products()
        self.refresh_fee_button()
        self._render_cart()