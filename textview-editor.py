#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019  Esrille Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.


import sys
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Gdk, GObject


class EditorWindow(Gtk.ApplicationWindow):

    title = "TextView Editor"

    def __init__(self, app, file=None):
        content = ""

        self.user_action = False
        self.undo = []  # undo buffer
        self.redo = []  # redo buffer

        if file:
            try:
                [success, content, etags] = file.load_contents(None)
                content = content.decode("utf-8", "ignore")
            except GObject.GError as e:
                file = None
                print("Error: " + e.message)
        super().__init__(application=app)
        self.set_default_size(720, 400)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)

        self.buffer = self.textview.get_buffer()
        if content:
            self.buffer.set_text(content)
            self.buffer.set_modified(False)
            self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.connect("insert_text", self.on_insert)
        self.buffer.connect("delete_range", self.on_delete)
        self.buffer.connect("begin_user_action", self.on_begin_user_action)
        self.buffer.connect("end_user_action", self.on_end_user_action)

        scrolled_window.add(self.textview)
        self.add(scrolled_window)

        actions = {
            "new": self.new_callback,
            "open": self.open_callback,
            "save": self.save_callback,
            "saveas": self.save_as_callback,
            "close": self.close_callback,
            "closeall": self.close_all_callback,
            "undo": self.undo_callback,
            "redo": self.redo_callback,
            "cut": self.cut_callback,
            "copy": self.copy_callback,
            "paste": self.paste_callback,
            "selectall": self.select_all_callback,
            "about": self.about_callback,
        }
        for name, method in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", method)
            self.add_action(action)
        self.connect("delete-event", self.on_delete_event)

        self.set_file(file)

    def set_file(self, file):
        self.file = file
        if self.file:
            self.buffer.set_modified(False)
            self.undo = []
            self.redo = []
            self.set_title(file.get_basename() + " ― " + self.title)
            return False
        else:
            self.set_title(self.title)
            return True

    def is_opened(self, file):
        windows = self.get_application().get_windows()
        for window in windows:
            if window.file.equal(file):
                return window
        return None

    def on_insert(self, textbuffer, iter, text, length):
        if self.user_action:
            self.undo.append(["insert_text", iter.get_offset(), text,
                              time.perf_counter()])
            self.redo.clear()

    def on_delete(self, textbuffer, start, end):
        if self.user_action:
            text = self.buffer.get_text(start, end, True)
            self.undo.append(["delete_range", start.get_offset(), text,
                              time.perf_counter()])
            self.redo.clear()

    def on_begin_user_action(self, textbuffer):
        self.user_action = True

    def on_end_user_action(self, textbuffer):
        self.user_action = False

    def new_callback(self, action, parameter):
        win = EditorWindow(self.get_application())
        win.show_all()

    def open_callback(self, action, parameter):
        open_dialog = Gtk.FileChooserDialog(
            "Pick a file", self,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))
        self.add_filters(open_dialog)
        open_dialog.set_local_only(False)
        open_dialog.set_modal(True)
        open_dialog.connect("response", self.open_response_cb)
        open_dialog.show()

    def open_response_cb(self, dialog, response):
        file = None
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
        dialog.destroy()
        # open new window after closing dialog to raise the new window
        # in the stacking order.
        if file:
            win = self.is_opened(file)
            if win:
                win.present()
                return
            win = EditorWindow(self.get_application(), file=file)
            win.show_all()

    def add_filters(self, dialog):
        filter_text = Gtk.FileFilter()
        filter_text.set_name("Text files")
        filter_text.add_mime_type("text/plain")
        dialog.add_filter(filter_text)

        filter_py = Gtk.FileFilter()
        filter_py.set_name("Python files")
        filter_py.add_mime_type("text/x-python")
        dialog.add_filter(filter_py)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)

    def save(self):
        [start, end] = self.buffer.get_bounds()
        current_contents = self.buffer.get_text(start, end, False)
        if current_contents:
            try:
                current_contents = current_contents.encode()
                self.file.replace_contents(current_contents,
                                           None,
                                           False,
                                           Gio.FileCreateFlags.NONE,
                                           None)
            except GObject.GError as e:
                self.file = None
        else:
            try:
                self.file.replace_readwrite(None,
                                            False,
                                            Gio.FileCreateFlags.NONE,
                                            None)
            except GObject.GError as e:
                self.file = None
        return self.set_file(self.file)

    def save_as(self):
        dialog = Gtk.FileChooserDialog(
            "Pick a file", self,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT))
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_modal(True)
        if self.file is not None:
            try:
                dialog.set_file(self.file)
            except GObject.GError as e:
                print("Error: " + e.message)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            self.file = dialog.get_file()
            dialog.destroy()
            return self.save()
        dialog.destroy()
        return self.set_file(None)

    def confirm_save_changes(self):
        if not self.buffer.get_modified():
            return False
        dialog = Gtk.MessageDialog(
            self, 0, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.NONE, "Save changes to this document?")
        dialog.format_secondary_text(
            "If you don't, changes will be lost.")
        dialog.add_button("Close _Without Saving", Gtk.ResponseType.NO)
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.YES)
        dialog.set_default_response(Gtk.ResponseType.YES)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.NO:
            return False
        elif response == Gtk.ResponseType.YES:
            # close the window after saving changes
            self.close_after_save = True
            if self.file is not None:
                return self.save()
            else:
                return self.save_as()
        else:
            return True

    def save_callback(self, action, parameter):
        if self.file is not None:
            self.save()
        else:
            self.save_as()

    def save_as_callback(self, action, parameter):
        self.save_as()

    def close_callback(self, action, parameter):
        if not self.confirm_save_changes():
            self.destroy()

    def close_all_callback(self, action, parameter):
        windows = self.get_application().get_windows()
        for window in windows:
            window.lookup_action("close").activate()

    def on_delete_event(self, widget, event):
        return self.confirm_save_changes()

    def undo_callback(self, action, parameter):
        if not self.undo:
            return
        action = self.undo.pop()
        if action[0] == "insert_text":
            start = self.buffer.get_iter_at_offset(action[1])
            end = self.buffer.get_iter_at_offset(action[1] + len(action[2]))
            self.buffer.delete(start, end)
            # undo previous delete_range that issued within 1 msec
            # to cope with ibus-replace-with-kanji smoothly
            if self.undo:
                prev = self.undo[-1]
                if prev[0] == "delete_range" and action[3] - prev[3] < 0.001:
                    self.redo.append(action)
                    action = self.undo.pop()
                    start = self.buffer.get_iter_at_offset(action[1])
                    self.buffer.insert(start, action[2])
        elif action[0] == "delete_range":
            start = self.buffer.get_iter_at_offset(action[1])
            self.buffer.insert(start, action[2])
        self.redo.append(action)

    def redo_callback(self, action, parameter):
        if not self.redo:
            return
        action = self.redo.pop()
        if action[0] == "insert_text":
            start = self.buffer.get_iter_at_offset(action[1])
            self.buffer.insert(start, action[2])
        elif action[0] == "delete_range":
            start = self.buffer.get_iter_at_offset(action[1])
            end = self.buffer.get_iter_at_offset(action[1] + len(action[2]))
            self.buffer.delete(start, end)
            # redo previous insert_text that issued within 1 msec
            # to cope with ibus-replace-with-kanji smoothly
            if self.redo:
                prev = self.redo[-1]
                if prev[0] == "insert_text" and action[3] - prev[3] < 0.001:
                    self.undo.append(action)
                    action = self.redo.pop()
                    start = self.buffer.get_iter_at_offset(action[1])
                    self.buffer.insert(start, action[2])
        self.undo.append(action)

    def cut_callback(self, action, parameter):
        self.buffer.cut_clipboard(self.clipboard, self.textview.get_editable())
        self.textview.scroll_mark_onscreen(self.buffer.get_insert())

    def copy_callback(self, action, parameter):
        self.buffer.copy_clipboard(self.clipboard)

    def paste_callback(self, action, parameter):
        text = self.clipboard.wait_for_text()
        if text is not None:
            self.buffer.begin_user_action()
            self.buffer.insert_at_cursor(text)
            self.buffer.end_user_action()

    def select_all_callback(self, action, parameter):
        start, end = self.buffer.get_bounds()
        self.buffer.select_range(start, end)

    def about_callback(self, action, parameter):
        dialog = Gtk.AboutDialog()
        dialog.set_transient_for(self)

        authors = ["Esrille Inc."]
        documenters = ["Esrille Inc."]

        dialog.set_program_name(self.title)
        dialog.set_copyright("Copyright 2019 Esrille Inc.")
        dialog.set_authors(authors)
        dialog.set_documenters(documenters)
        dialog.set_website("http://www.esrille.com/")
        dialog.set_website_label("Esrille Inc.")

        # to close the dialog when "close" is clicked, e.g. on RPi,
        # we connect the "response" signal to about_response_callback
        dialog.connect("response", self.about_response_callback)
        dialog.show()

    def about_response_callback(self, dialog, response):
        dialog.destroy()


class EditorApplication(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super().__init__(*args,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN,
                         **kwargs)

    def do_activate(self):
        win = EditorWindow(self)
        win.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        builder = Gtk.Builder()
        try:
            builder.add_from_file("textview-editor.menu.ui")
        except GObject.GError as e:
            print("Error: " + e.message)
            sys.exit()
        self.set_menubar(builder.get_object("menubar"))

    def do_open(self, files, *hint):
        for file in files:
            win = EditorWindow(self, file=file)
            win.show_all()


app = EditorApplication()
exit_status = app.run(sys.argv)
sys.exit(exit_status)