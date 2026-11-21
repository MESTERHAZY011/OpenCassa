import tkinter as tk
from tkinter import ttk
from store import StoreManager
from tab_products import ProductsTab
from tab_simple_pos import SimplePosTab
from tab_factory_pos import FactoryPosTab
from tab_settings import SettingsTab


class UniversalPosApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.store = StoreManager(on_barcode_scanned=self._on_barcode_from_hardware)
        self.title(f"Univerzális Bolti Szoftver — {self.store.settings.register_name}")
        self.geometry("1160x700")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.products_tab = ProductsTab(self.notebook, self.store, self._on_products_changed)
        self.simple_pos_tab = SimplePosTab(self.notebook, self.store)
        self.factory_pos_tab = FactoryPosTab(self.notebook, self.store)
        self.settings_tab = SettingsTab(self.notebook, self.store, self._on_settings_applied)

        self.notebook.add(self.products_tab, text="Termékek")
        self.notebook.add(self.simple_pos_tab, text="Egyszerű kassza")
        self.notebook.add(self.factory_pos_tab, text="Gyári kassza")
        self.notebook.add(self.settings_tab, text="Egyéb & Settings")

        self.factory_pos_tab.bind_shortcuts(self)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._on_settings_applied()

    def _on_barcode_from_hardware(self, code: str):
        def dispatch():
            if self.products_tab.is_waiting_for_scan():
                self.products_tab.receive_device_barcode(code)
            else:
                self.factory_pos_tab.handle_scanned_code(code)

        self.after(0, dispatch)

    def _on_tab_changed(self, event):
        selected_tab = self.notebook.nametowidget(self.notebook.select())
        if selected_tab is self.factory_pos_tab:
            self.factory_pos_tab.focus_scanner()

    def _on_products_changed(self):
        self.simple_pos_tab.refresh_products()

    def _on_settings_applied(self):
        touch = self.store.settings.touch_mode
        self.title(f"Univerzális Bolti Szoftver — {self.store.settings.register_name}")
        self.products_tab.apply_touch_mode(touch)
        self.simple_pos_tab.apply_touch_mode(touch)
        self.factory_pos_tab.apply_touch_mode(touch)
        self.simple_pos_tab.refresh_fee_button()
        self.factory_pos_tab.refresh_fee_button()
        self.store.hardware.start_scanner_listener()

    def _on_close(self):
        self.store.hardware.stop_scanner_listener()
        self.destroy()


if __name__ == "__main__":
    app = UniversalPosApp()
    app.mainloop()