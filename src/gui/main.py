#!/usr/bin/env python3
import os
import sys
import configparser
import subprocess

import gi


gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

CONFIG_PATH = "/etc/pardus/eta-right-click.conf"

import locale
from locale import gettext as _

# Translation Constants:
APPNAME = "eta-right-click"
TRANSLATIONS_PATH = "/usr/share/locale"

# Translation functions:
locale.bindtextdomain(APPNAME, TRANSLATIONS_PATH)
locale.textdomain(APPNAME)

class SettingsWindow(Gtk.Window):

    def __init__(self):
        super().__init__(title=_("ETA Right Click Settings"))
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

        timeout_label = Gtk.Label(label=_("Timeout (ms):"))
        timeout_label.set_xalign(0)
        grid.attach(timeout_label, 0, 0, 1, 1)

        self.timeout_spin = Gtk.SpinButton.new_with_range(100, 3000, 10)
        self.timeout_spin.set_value(self.timeout)
        grid.attach(self.timeout_spin, 1, 0, 1, 1)

        threshold_label = Gtk.Label(label=_("Threshold (px):"))
        threshold_label.set_xalign(0)
        grid.attach(threshold_label, 0, 1, 1, 1)

        self.threshold_spin = Gtk.SpinButton.new_with_range(0, 200, 1)
        self.threshold_spin.set_value(self.threshold)
        grid.attach(self.threshold_spin, 1, 1, 1, 1)

        btn_box = Gtk.Box(spacing=8)
        vbox.pack_start(btn_box, False, False, 0)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.connect("clicked", self._on_save)
        btn_box.pack_end(save_btn, False, False, 0)

        cancel_btn = Gtk.Button(label=_("Cancel"))
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
            self._restart_service()
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=_("Failed to save config"),
            )
            dialog.format_secondary_text(str(e))
            dialog.run()
            dialog.destroy()
            return

        Gtk.main_quit()

    def _restart_service(self):
        subprocess.run(["systemctl", "restart", "eta-right-click.service"])


if __name__ == "__main__":

    if os.getuid() != 0:
        subprocess.run(["pkexec", __file__])
        sys.exit(0)
    settings = SettingsWindow()
    settings.show_all()
    Gtk.main()
