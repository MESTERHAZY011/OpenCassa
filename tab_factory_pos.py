import time
import tkinter as tk
from tkinter import ttk, messagebox
from store import StoreManager, Product, CustomFee


class FactoryPosTab(ttk.Frame):
    def __init__(self, parent, store: StoreManager):
        super().__init__(parent, padding=16)
        self.store = store
        # Minden bejegyzés: ("product", (Product, qty, line_total)) vagy ("fee", CustomFee)
        self.entries: list[tuple[str, object]] = []
        self.payment_method = "Készpénz"
        self._hid_buffer: str = ""
        self._hid_last_ts: float = 0.0
        self._build_ui()
        self.refresh_fee_button()

    def _build_ui(self):
        top = ttk.LabelFrame(self, text="Gyári beolvasás (Termékkód / Vonalkód / Kamera)", padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Kód / Vonalkód:").pack(side="left", padx=(0, 8))
        self.code_entry = ttk.Entry(top, font=("Consolas", 14), width=22)
        self.code_entry.pack(side="left", padx=(0, 8))
        self.code_entry.bind("<Return>", self._on_enter_code)

        ttk.Button(top, text="Hozzáad (Enter)", command=self._submit_code).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="📷 Kamera olvasás", command=self.scan_from_camera).pack(side="left", padx=(0, 6))

        self.fee_btn = ttk.Button(top, text="+ Egyedi díj (F5)", command=self.add_configured_fee)
        self.fee_btn.pack(side="left")

        self.status_var = tk.StringVar(value="Készenlét — pl. T001*3 vagy vonalkód.")
        ttk.Label(top, textvariable=self.status_var, font=("Arial", 10, "bold")).pack(side="right")

        mid = ttk.Frame(self, padding=(0, 12))
        mid.pack(fill="both", expand=True)

        self.log_box = tk.Listbox(mid, font=("Consolas", 12), height=10, exportselection=False)
        self.log_box.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.log_box.bind("<Up>", lambda e: (self.move_selection(-1), "break")[1])
        self.log_box.bind("<Down>", lambda e: (self.move_selection(1), "break")[1])
        self.log_box.bind("<BackSpace>", lambda e: (self.delete_selected_entry(), "break")[1])

        right = ttk.Frame(mid)
        right.pack(side="right", fill="both", expand=True)

        self.sum_var = tk.StringVar(value="ÖSSZESEN: 0 Ft")
        ttk.Label(right, textvariable=self.sum_var, font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 6))

        self.pay_var = tk.StringVar(value="Fizetés: Készpénz")
        ttk.Label(right, textvariable=self.pay_var, font=("Arial", 12)).pack(anchor="w", pady=(0, 10))

        self.receipt_preview = tk.Text(right, height=12, font=("Consolas", 9), state="disabled")
        self.receipt_preview.pack(fill="both", expand=True)

        self.hint_var = tk.StringVar()
        ttk.Label(self, textvariable=self.hint_var, font=("Arial", 10, "bold")).pack(anchor="w", pady=(8, 0))

    def refresh_fee_button(self):
        fee = self.store.get_configured_custom_fee()
        if fee:
            self.fee_btn.configure(text=f"+{fee.name} ({fee.amount} Ft) [F5]")
            fee_hint = f"+{fee.name}"
        else:
            self.fee_btn.configure(text="+ Egyedi díj (F5)")
            fee_hint = "+<név>"

        self.hint_var.set(
            f"[Enter] Kód[*db] | [↑/↓] Léptetés | [Backspace] Törlés | "
            f"[F2] KP | [F3] Kártya | [F4] Fizetés | [F5] {fee_hint} | [Esc] Összes törlése"
        )

    def add_configured_fee(self):
        fee = self.store.get_configured_custom_fee()
        if not fee:
            messagebox.showinfo(
                "Nincs beállított egyedi díj",
                "Add meg az egyedi díj nevét és árát az 'Egyéb & Settings' fülön, majd mentsd el.",
            )
            return
        new_fee = CustomFee(name=fee.name, amount=fee.amount)
        self.entries.append(("fee", new_fee))
        self.status_var.set(f"Hozzáadva: +{new_fee.name} díj ({new_fee.amount} Ft)")
        self._refresh_view(select_idx=len(self.entries) - 1)

    @staticmethod
    def _parse_code_and_qty(raw: str) -> tuple[str | None, int, str | None]:
        text = raw.strip()
        if not text:
            return None, 0, None

        if "*" not in text:
            return text, 1, None

        parts = text.split("*")
        if len(parts) != 2:
            return None, 0, f"Érvénytelen szorzó formátum: {text}"

        code_part = parts[0].strip()
        qty_part = parts[1].strip()

        if not code_part:
            return None, 0, "Hiányzik a termékkód a '*' előtt."

        if not qty_part.isdigit():
            return None, 0, f"Érvénytelen darabszám a '*' után: '{qty_part}'"

        qty = int(qty_part)
        if qty < 1:
            return None, 0, "A darabszámnak legalább 1-nek kell lennie."

        return code_part, qty, None

    def scan_from_camera(self):
        if not self.store.settings.scanner_connected:
            messagebox.showwarning("Olvasó", "Kapcsold be a vonalkódolvasót a Beállításokban.")
            return
        code = self.store.hardware.scan_with_camera_modal(self, title="Kassza vonalkód olvasás")
        if code:
            self.handle_scanned_code(code)
        else:
            self.status_var.set("Kamerás olvasás megszakítva.")

    def bind_shortcuts(self, root: tk.Tk):
        root.bind("<F2>", lambda e: self.set_payment("Készpénz"))
        root.bind("<F3>", lambda e: self.set_payment("Kártya"))
        root.bind("<F4>", lambda e: self.checkout())
        root.bind("<F5>", lambda e: self.add_configured_fee())
        root.bind("<Escape>", lambda e: self.clear_lines())
        root.bind("<Up>", self._on_arrow_up)
        root.bind("<Down>", self._on_arrow_down)
        root.bind("<BackSpace>", self._on_backspace)
        root.bind("<Key>", self._on_global_hid_key)

    def _is_in_factory_tab(self) -> bool:
        try:
            focused = self.focus_get()
            if focused is None:
                return False
            widget = focused
            while widget is not None:
                if widget is self:
                    return True
                widget = widget.master
        except Exception:
            pass
        return False

    def _on_arrow_up(self, _event):
        if not self._is_in_factory_tab() or not self.entries:
            return
        self.move_selection(-1)
        return "break"

    def _on_arrow_down(self, _event):
        if not self._is_in_factory_tab() or not self.entries:
            return
        self.move_selection(1)
        return "break"

    def _on_backspace(self, _event):
        if not self._is_in_factory_tab() or not self.entries:
            return
        # Ha a kódmezőben épp van szöveg, engedjük a normál karaktertörlést
        if self.focus_get() is self.code_entry and self.code_entry.get():
            return
        self.delete_selected_entry()
        return "break"

    def move_selection(self, delta: int):
        count = len(self.entries)
        if count == 0:
            return
        sel = self.log_box.curselection()
        if not sel:
            new_idx = 0 if delta > 0 else count - 1
        else:
            new_idx = max(0, min(count - 1, sel[0] + delta))
        self.log_box.selection_clear(0, "end")
        self.log_box.selection_set(new_idx)
        self.log_box.activate(new_idx)
        self.log_box.see(new_idx)

    def delete_selected_entry(self):
        if not self.entries:
            return
        sel = self.log_box.curselection()
        idx = sel[0] if sel else len(self.entries) - 1
        kind, payload = self.entries.pop(idx)
        if kind == "product":
            prod, qty, line_sum = payload
            self.status_var.set(f"Törölve: {prod.name} x{qty} ({line_sum} Ft)")
        else:
            fee: CustomFee = payload
            self.status_var.set(f"Törölve: +{fee.name} díj ({fee.amount} Ft)")

        next_idx = min(idx, len(self.entries) - 1) if self.entries else None
        self._refresh_view(select_idx=next_idx)

    def _on_global_hid_key(self, event):
        if not self.store.settings.scanner_connected:
            return
        if not self.store.settings.scanner_mode.startswith("USB-HID"):
            return

        now = time.monotonic()
        if now - self._hid_last_ts > 0.15:
            self._hid_buffer = ""
        self._hid_last_ts = now

        if event.keysym == "Return":
            scanned = self._hid_buffer.strip()
            self._hid_buffer = ""
            if len(scanned) >= 3 and self.focus_get() is not self.code_entry:
                self.handle_scanned_code(scanned)
        elif event.char and event.char.isprintable():
            self._hid_buffer += event.char

    def focus_scanner(self):
        self.code_entry.focus_set()

    def _on_enter_code(self, event):
        self._submit_code()
        return "break"

    def _submit_code(self):
        raw = self.code_entry.get().strip()
        self.code_entry.delete(0, "end")
        if raw:
            self.handle_scanned_code(raw)

    def handle_scanned_code(self, raw: str):
        if raw.startswith("__ERR__:"):
            self.status_var.set(raw.replace("__ERR__:", "Olvasó hiba: "))
            return

        code_query, qty, err = self._parse_code_and_qty(raw)
        if err:
            self.status_var.set(err)
            return
        if not code_query:
            return

        prod = self.store.find_product(code_query)
        if not prod:
            self.status_var.set(f"Ismeretlen kód: {code_query}")
            return

        line_total = prod.price * qty
        self.entries.append(("product", (prod, qty, line_total)))
        self.status_var.set(f"Beolvasva: {prod.name} x{qty} ({line_total} Ft)")
        self._refresh_view(select_idx=len(self.entries) - 1)

    def set_payment(self, method: str):
        self.payment_method = method
        self.pay_var.set(f"Fizetés: {method}")

    def clear_lines(self):
        self.entries.clear()
        self._refresh_view()
        self.status_var.set("Lista és díjak törölve.")

    def _refresh_view(self, select_idx: int | None = None):
        self.log_box.delete(0, "end")
        total = 0
        for idx, (kind, payload) in enumerate(self.entries):
            row_num = idx + 1
            if kind == "product":
                p, qty, line_sum = payload
                total += line_sum
                qty_tag = f" x{qty}" if qty > 1 else ""
                self.log_box.insert("end", f"{row_num:02d}. [{p.code}] {p.name:<15}{qty_tag:<4} {line_sum:>6} Ft")
            else:
                fee: CustomFee = payload
                total += fee.amount
                label = f"+{fee.name} díj"
                self.log_box.insert("end", f"{row_num:02d}. {label:<20} {fee.amount:>6} Ft")

        if self.entries:
            target = len(self.entries) - 1 if select_idx is None else max(0, min(len(self.entries) - 1, select_idx))
            self.log_box.selection_set(target)
            self.log_box.activate(target)
            self.log_box.see(target)

        self.sum_var.set(f"ÖSSZESEN: {total} Ft")

    def checkout(self):
        if not self.entries:
            self.status_var.set("Nincs beolvasott tétel vagy díj.")
            return

        merged: dict[str, tuple[Product, int, int]] = {}
        fees_list: list[CustomFee] = []

        for kind, payload in self.entries:
            if kind == "product":
                prod, qty, line_sum = payload
                if prod.code in merged:
                    p, q, s = merged[prod.code]
                    merged[prod.code] = (p, q + qty, s + line_sum)
                else:
                    merged[prod.code] = (prod, qty, line_sum)
            else:
                fees_list.append(payload)

        items_list = list(merged.values())
        total = sum(line_total for _, _, line_total in items_list) + sum(f.amount for f in fees_list)
        terminal_info = None

        if self.payment_method == "Kártya":
            ok, info = self.store.hardware.process_card_payment(total, self.store.next_receipt_number)
            if not ok:
                messagebox.showwarning("Kártyaterminál", info)
                self.status_var.set("Kártyás fizetés sikertelen.")
                return
            terminal_info = info

        receipt_text, filepath, receipt_num = self.store.save_receipt(
            items=items_list,
            payment_method=self.payment_method,
            terminal_info=terminal_info,
            custom_fees=fees_list,
        )

        self.receipt_preview.configure(state="normal")
        self.receipt_preview.delete("1.0", "end")
        self.receipt_preview.insert("1.0", receipt_text)
        self.receipt_preview.configure(state="disabled")

        self.entries.clear()
        self._refresh_view()
        self.status_var.set(f"Nyugta #{receipt_num:06d} mentve: {filepath}")

    def apply_touch_mode(self, enabled: bool):
        font_sz = 16 if enabled else 14
        self.code_entry.configure(font=("Consolas", font_sz))
        self.log_box.configure(font=("Consolas", 14 if enabled else 12))
        self.refresh_fee_button()