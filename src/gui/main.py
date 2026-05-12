#!/usr/bin/env python3
import sys
import configparser

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

CONFIG_PATH = "/etc/pardus/eta-right-click.conf"


class SettingsWindow(Gtk.Window):

    def __init__(self):
        super().__init__(title="ETA Right Click Settings")
        self.set_border_width(20)
        self.set_resizable(False)
        self.connect("destroy", Gtk.main_quit)

        self.timeout = 500
        self.threshold = 20
        self._load_config()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        vbox.pack_start(grid, False, False, 0)

        timeout_label = Gtk.Label(label="Timeout (ms):")
        timeout_label.set_xalign(0)
        grid.attach(timeout_label, 0, 0, 1, 1)

        self.timeout_spin = Gtk.SpinButton.new_with_range(100, 3000, 10)
        self.timeout_spin.set_value(self.timeout)
        grid.attach(self.timeout_spin, 1, 0, 1, 1)

        threshold_label = Gtk.Label(label="Threshold (px):")
        threshold_label.set_xalign(0)
        grid.attach(threshold_label, 0, 1, 1, 1)

        self.threshold_spin = Gtk.SpinButton.new_with_range(0, 200, 1)
        self.threshold_spin.set_value(self.threshold)
        grid.attach(self.threshold_spin, 1, 1, 1, 1)

        btn_box = Gtk.Box(spacing=8)
        vbox.pack_start(btn_box, False, False, 0)

        save_btn = Gtk.Button(label="Save")
        save_btn.connect("clicked", self._on_save)
        btn_box.pack_end(save_btn, False, False, 0)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: Gtk.main_quit())
        btn_box.pack_end(cancel_btn, False, False, 0)

    def _load_config(self):
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_PATH)
            self.timeout = int(config["main"]["timeout"])
            self.threshold = int(config["main"]["threshold"])
        except Exception:
            pass

    def _on_save(self, _btn):
        timeout = int(self.timeout_spin.get_value())
        threshold = int(self.threshold_spin.get_value())

        config = configparser.ConfigParser()
        config["main"] = {}
        config["main"]["timeout"] = str(timeout)
        config["main"]["threshold"] = str(threshold)

        try:
            with open(CONFIG_PATH, "w") as f:
                config.write(f)
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Failed to save config",
            )
            dialog.format_secondary_text(str(e))
            dialog.run()
            dialog.destroy()
            return

        Gtk.main_quit()


if __name__ == "__main__":
    settings = SettingsWindow()
    settings.show_all()
    Gtk.main()
