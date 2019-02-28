#!/usr/bin/env python3
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

import os
import sys
import time
import locale
import json

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio, Gtk, Gdk, GObject, Pango


class EditorWindow(Gtk.ApplicationWindow):


    def __init__(self, app, file=None):
        content = ""

        self.title = _("TextView Editor")
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

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(grid)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_monospace(True)
        self.textview.connect("focus-in-event", self.on_focus_in)

        scrolled_window.add(self.textview)
        grid.pack_start(scrolled_window, True, True, 0)

        self.searchbar = Gtk.SearchBar()
        # We use Gtk.Entry since Gtk.SearchEntry does not support IME
        # at this point.
        searchentry = Gtk.Entry()
        self.searchbar.add(searchentry)
        self.searchbar.connect_entry(searchentry)
        grid.pack_start(self.searchbar, False, False, 0)
        self.searchbar.set_search_mode(False)
        searchentry.connect("focus-out-event", self.on_searchbar_focus_out)
        searchentry.connect("activate", self.on_find)

        self.buffer = self.textview.get_buffer()
        if content:
            self.buffer.set_text(content)
            self.buffer.set_modified(False)
            self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.connect("insert_text", self.on_insert)
        self.buffer.connect("delete_range", self.on_delete)
        self.buffer.connect("begin_user_action", self.on_begin_user_action)
        self.buffer.connect("end_user_action", self.on_end_user_action)

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
            "find": self.find_callback,
            "selectall": self.select_all_callback,
            "font": self.font_callback,
            "about": self.about_callback,
        }
        for name, method in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", method)
            self.add_action(action)
        self.connect("delete-event", self.on_delete_event)

        wordwrap_action = Gio.SimpleAction.new_stateful(
            "wordwrap", None, GLib.Variant.new_boolean(True))
        wordwrap_action.connect("activate", self.wordwrap_callback)
        self.add_action(wordwrap_action)

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
            if window.file and window.file.equal(file):
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
            _("Open File"), self,
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
        filter_text.set_name(_("Text files"))
        filter_text.add_mime_type("text/plain")
        dialog.add_filter(filter_text)

        filter_py = Gtk.FileFilter()
        filter_py.set_name(_("Python files"))
        filter_py.add_mime_type("text/x-python")
        dialog.add_filter(filter_py)

        filter_any = Gtk.FileFilter()
        filter_any.set_name(_("Any files"))
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
            _("Save File"), self,
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
            Gtk.ButtonsType.NONE, _("Save changes to this document?"))
        dialog.format_secondary_text(
            _("If you don't, changes will be lost."))
        dialog.add_button(_("Close _Without Saving"), Gtk.ResponseType.NO)
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
        if not self.undo or not self.textview.is_focus():
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
        if not self.redo or not self.textview.is_focus():
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

    def on_focus_in(self, widget, event):
        self.searchbar.set_search_mode(False)
        return False

    def find_callback(self, action, parameter):
        self.searchbar.set_search_mode(True)
        self.searchbar.grab_focus()

    def on_find(self, entry):
        cursor_mark = self.buffer.get_insert()
        start = self.buffer.get_iter_at_mark(cursor_mark)
        selecton_mark = self.buffer.get_selection_bound()
        selected = self.buffer.get_iter_at_mark(selecton_mark)
        if start.get_offset() < selected.get_offset():
            start = selected

        match = start.forward_search(entry.get_text(), 0, None)
        if match is not None:
            match_start, match_end = match
            self.buffer.select_range(match_start, match_end)
        else:
            start = self.buffer.get_start_iter()
            match = start.forward_search(entry.get_text(), 0, None)
            if match is not None:
                match_start, match_end = match
                self.buffer.select_range(match_start, match_end)

    def on_searchbar_focus_out(self, widget, event):
        # Take the focus back to textview from somewhere
        # after searchbar is closed.
        self.textview.grab_focus()
        return False

    def select_all_callback(self, action, parameter):
        start, end = self.buffer.get_bounds()
        self.buffer.select_range(start, end)

    def font_callback(self, action, parameter):
        dialog = Gtk.FontChooserDialog(_("Font"), self)
        dialog.props.preview_text = _("The quick brown fox jumps over the lazy dog.")
        style = self.textview.get_style()
        dialog.set_font_desc(style.font_desc)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            font = dialog.get_font()
            if font:
                self.textview.modify_font(
                    Pango.font_description_from_string(font))
        dialog.destroy()

    def wordwrap_callback(self, action, parameter):
        wordwrap = not action.get_state()
        action.set_state(GLib.Variant.new_boolean(wordwrap))
        if wordwrap:
            self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        else:
            self.textview.set_wrap_mode(Gtk.WrapMode.NONE)

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

        self.lang = locale.getdefaultlocale()[0]
        filename = os.path.splitext(sys.argv[0])[0] + '.' + self.lang + ".json"
        try:
            with open(filename, 'r') as file:
                self.uitexts = json.load(file)
        except OSError as e:
            print("Error: " + e.strerror)
            self.uitexts = {}

    def do_activate(self):
        win = EditorWindow(self)
        win.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        builder = Gtk.Builder()
        filename = os.path.splitext(sys.argv[0])[0] + '.menu.' + self.lang + ".ui"
        try:
            builder.add_from_file(filename)
        except GObject.GError as e:
            print("Error: " + e.message)
            try:
                filename = os.path.splitext(sys.argv[0])[0] + ".menu.ui"
                builder.add_from_file(filename)
            except GObject.GError as e:
                print("Error: " + e.message)
                sys.exit()
        self.set_menubar(builder.get_object("menubar"))

    def do_open(self, files, *hint):
        for file in files:
            win = EditorWindow(self, file=file)
            win.show_all()

    def get_text(self, string):
        if string in self.uitexts:
            return self.uitexts[string]
        return string


# i18n
def _(string):
    return app.get_text(string)


app = EditorApplication()
exit_status = app.run(sys.argv)
sys.exit(exit_status)
