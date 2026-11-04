"""Native GTK 4 / libadwaita desktop: two modes and one export action."""
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from . import __version__
from .core import AUDIO_FORMATS, IMAGE_FORMATS, Job, dependencies, validate
from .desktop import Controller, next_output
from .process import RenderError
from .visualizer import WIDTH, HEIGHT, STYLES, render
from .title import normalize_title, title_image
from PIL import Image


def label(text, style=None):
    widget = Gtk.Label(label=text, xalign=0, wrap=True)
    widget.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if style:
        widget.add_css_class(style)
    return widget


def button(text, callback):
    widget = Gtk.Button(label=text)
    widget.connect("clicked", lambda _: callback())
    return widget


class Window(Adw.ApplicationWindow):
    def __init__(self, app, controller=None):
        super().__init__(application=app, title="Audio to Video", default_width=720, default_height=900)
        self.set_size_request(480, 560)
        self.controller = controller or Controller()
        self.audio = self.image = self.output = None
        self.mode = "still"
        self.closing = False
        self.dialogs = []
        self.chooser_cancel = Gio.Cancellable()
        self.connect("close-request", self.on_close)

        self.overlay = Adw.ToastOverlay()
        self.set_content(self.overlay)
        toolbar = Adw.ToolbarView()
        self.overlay.set_child(toolbar)
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Audio to Video", subtitle="QSOL-IMC · local media tools"))
        header.pack_end(button("Details", self.details))
        toolbar.add_top_bar(header)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        toolbar.set_content(scroll)
        clamp = Adw.Clamp(maximum_size=760)
        scroll.set_child(clamp)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_start=24, margin_end=24, margin_top=18, margin_bottom=18)
        clamp.set_child(body)
        body.append(label("Audio in. Video out.", "title-1"))
        body.append(label("Choose your sound and its visual. Export a ready-to-play MP4.", "dim-label"))

        self.audio_row, self.audio_button = self.file_row("Audio", "Choose MP3, M4A or WAV", self.choose_audio)
        body.append(self.audio_row)

        choices = Gtk.Box(spacing=10, homogeneous=True)
        self.still_button = Gtk.ToggleButton(label="Still image")
        self.viz_button = Gtk.ToggleButton(label="Visualizer")
        self.viz_button.set_group(self.still_button)
        for widget in (self.still_button, self.viz_button):
            widget.set_size_request(-1, 44)
            choices.append(widget)
        self.still_button.set_active(True)
        self.still_button.connect("toggled", self.mode_changed, "still")
        self.viz_button.connect("toggled", self.mode_changed, "visualizer")
        body.append(choices)

        self.style_row = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.style_row.add_css_class("boxed-list")
        style_action = Adw.ActionRow(title="Visual style", use_markup=False)
        self.style = Gtk.DropDown.new_from_strings(list(STYLES.values()))
        self.style.set_valign(Gtk.Align.CENTER)
        self.style.set_tooltip_text("Visualizer style")
        style_action.add_suffix(self.style)
        self.style_row.append(style_action)
        body.append(self.style_row)

        self.visual = Gtk.Stack(vhomogeneous=True)
        self.visual.set_size_request(-1, 150)
        self.visual.add_css_class("card")
        self.empty_image = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER)
        self.empty_image.append(Gtk.Image(icon_name="image-x-generic-symbolic", pixel_size=48))
        self.empty_image.append(Gtk.Label(label="Your image stays still for the whole track."))
        self.visual.add_named(self.empty_image, "empty")
        self.cover = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.visual.add_named(self.cover, "cover")
        texture = Gdk.MemoryTexture.new(WIDTH, HEIGHT, Gdk.MemoryFormat.R8G8B8,
                                        GLib.Bytes.new(render(b"")), WIDTH * 3)
        self.waveform = Gtk.Picture(paintable=texture, content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.visual.add_named(self.waveform, "waveform")
        body.append(self.visual)
        self.visual_note = label("PNG or JPEG. Fitted to the frame without cropping or movement.", "caption")
        body.append(self.visual_note)
        self.image_row, self.image_button = self.file_row("Image", "Choose PNG or JPEG", self.choose_image)
        body.append(self.image_row)

        self.track_title = Gtk.Entry(placeholder_text="Name – Track (optional)", max_length=120)
        self.track_title.set_tooltip_text("Title at the top of the video; leave empty for no text")
        self.track_title.set_size_request(-1, 42)
        body.append(self.track_title)
        self.preview_key = None
        self.style.connect("notify::selected", lambda *_: self.selection_changed())
        self.track_title.connect("changed", lambda *_: self.selection_changed())

        settings = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        settings.add_css_class("boxed-list")
        self.output_row = Adw.ActionRow(title="Save MP4", subtitle="Choose audio first", use_markup=False)
        self.output_row.set_subtitle_lines(2)
        self.output_button = button("Save as…", self.choose_output)
        self.output_button.set_valign(Gtk.Align.CENTER)
        self.output_row.add_suffix(self.output_button)
        settings.append(self.output_row)
        resolution_row = Adw.ActionRow(title="Resolution", subtitle="16:9 · 30 frames per second", use_markup=False)
        self.resolution = Gtk.DropDown.new_from_strings(["1080p", "720p"])
        self.resolution.connect("notify::selected", lambda *_: self.selection_changed())
        self.resolution.set_valign(Gtk.Align.CENTER)
        self.resolution.set_tooltip_text("Output resolution")
        resolution_row.add_suffix(self.resolution)
        settings.append(resolution_row)
        body.append(settings)
        body.append(label("Processed on this computer. Every exported video frame is checked before saving.", "caption"))

        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                         margin_start=24, margin_end=24, margin_top=14, margin_bottom=18)
        self.progress = Gtk.ProgressBar()
        bottom.append(self.progress)
        self.status = label(self.controller.status)
        bottom.append(self.status)
        self.elapsed = label("", "caption")
        bottom.append(self.elapsed)
        actions = Gtk.Box(spacing=10)
        self.open_button = button("Open video", self.open_video)
        actions.append(self.open_button)
        spacer = Gtk.Box(hexpand=True)
        actions.append(spacer)
        self.cancel_button = button("Cancel", self.cancel_work)
        actions.append(self.cancel_button)
        self.export_button = button("Create MP4", self.start)
        self.export_button.add_css_class("suggested-action")
        self.export_button.set_size_request(150, 42)
        actions.append(self.export_button)
        bottom.append(actions)
        toolbar.add_bottom_bar(bottom)
        self.refresh()
        self.poll_id = GLib.timeout_add(80, self.poll)

    def file_row(self, title, subtitle, callback):
        group = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        group.add_css_class("boxed-list")
        row = Adw.ActionRow(title=title, subtitle=subtitle, use_markup=False)
        row.set_subtitle_lines(2)
        choose = button("Choose…", callback)
        choose.set_valign(Gtk.Align.CENTER)
        row.add_suffix(choose)
        row.set_activatable_widget(choose)
        group.append(row)
        return group, choose

    def toast(self, text):
        self.overlay.add_toast(Adw.Toast.new(str(text)))

    def mode_changed(self, widget, mode):
        if widget.get_active():
            self.mode = mode
            self.selection_changed()

    def selection_changed(self):
        if self.controller.busy or self.closing:
            return
        self.controller.result, self.controller.error = None, ""
        self.controller.fraction = 0.0
        self.controller.status = ("Choose an audio file to begin." if self.audio is None else
            "Choose a PNG or JPEG for your still image." if self.mode == "still" and self.image is None else
            "Ready to create MP4.")
        self.refresh()

    def refresh(self):
        busy = self.controller.busy or self.closing
        for widget in (self.audio_button, self.image_button, self.output_button,
                       self.still_button, self.viz_button, self.resolution, self.style, self.track_title):
            widget.set_sensitive(not busy)
        self.export_button.set_sensitive(not busy and self.audio is not None and self.output is not None
                                         and (self.mode == "visualizer" or self.image is not None)
                                         and not dependencies())
        self.export_button.set_label("Working…" if busy else "Create MP4")
        self.cancel_button.set_visible(self.controller.busy)
        self.cancel_button.set_sensitive(not self.controller.cancel.is_set())
        self.open_button.set_visible(self.controller.result is not None and not self.controller.busy)
        self.image_row.set_visible(self.mode == "still")
        self.style_row.set_visible(self.mode == "visualizer")
        self.visual.set_visible_child_name("waveform" if self.mode == "visualizer" else "cover" if self.image else "empty")
        self.visual_note.set_text("Style preview. Movement follows your audio in the exported video."
                                 if self.mode == "visualizer" else
                                 "PNG or JPEG. Fitted to the frame without cropping or movement.")
        key = (self.style.get_selected(), self.track_title.get_text())
        if self.mode == "visualizer" and key != self.preview_key:
            picture = Image.frombytes("RGB", (WIDTH, HEIGHT), render(b"", list(STYLES)[key[0]], 60))
            try:
                text = normalize_title(key[1])
                if text:
                    picture.paste(title_image(text, WIDTH), (0, 0))
            except RenderError:
                pass  # Export validation presents the actionable error.
            texture = Gdk.MemoryTexture.new(WIDTH, HEIGHT, Gdk.MemoryFormat.R8G8B8,
                                            GLib.Bytes.new(picture.tobytes()), WIDTH * 3)
            self.waveform.set_paintable(texture)
            self.preview_key = key
        if self.audio:
            self.audio_row.get_first_child().set_subtitle(self.audio.name)
        if self.image:
            self.image_row.get_first_child().set_subtitle(self.image.name)
        if self.output:
            self.output_row.set_subtitle(str(self.output))
        self.progress.set_fraction(self.controller.fraction)
        self.status.set_text(self.controller.status)
        if dependencies() and not busy:
            self.status.set_text("Install FFmpeg first: run ./install-deps.sh")

    def choose(self, title, extensions, callback, save=False):
        if self.controller.busy or self.closing:
            return
        dialog = Gtk.FileDialog(title=title, modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        kind = Gtk.FileFilter(name=title)
        for suffix in extensions:
            kind.add_pattern("*" + suffix)
            kind.add_pattern("*" + suffix.upper())
        filters.append(kind)
        dialog.set_filters(filters)
        self.dialogs.append(dialog)

        def finished(d, result):
            try:
                file = d.save_finish(result) if save else d.open_finish(result)
                path = file.get_path()
                if path is None:
                    self.toast("Choose a file on this computer.")
                elif not self.closing and not self.controller.busy:
                    callback(Path(path))
            except GLib.Error as exc:
                if not (exc.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED)
                        or exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)):
                    self.toast(exc.message)
            finally:
                self.dialogs.remove(d)

        if save:
            if self.output:
                dialog.set_initial_folder(Gio.File.new_for_path(str(self.output.parent)))
                dialog.set_initial_name(self.output.name)
            dialog.save(self, self.chooser_cancel, finished)
        else:
            dialog.open(self, self.chooser_cancel, finished)

    def choose_audio(self):
        self.choose("Choose audio", AUDIO_FORMATS, self.set_audio)

    def set_audio(self, path):
        self.audio = path
        self.output = next_output(path)
        self.selection_changed()

    def choose_image(self):
        self.choose("Choose image", IMAGE_FORMATS, self.set_image)

    def set_image(self, path):
        self.image = path
        self.cover.set_filename(str(path))
        self.selection_changed()

    def choose_output(self):
        self.choose("Save a new MP4", (".mp4",), self.set_output, save=True)

    def set_output(self, path):
        self.output = path if path.suffix.lower() == ".mp4" else Path(str(path) + ".mp4")
        self.selection_changed()

    def start(self):
        if self.controller.busy or self.closing or not self.audio or not self.output:
            return
        try:
            job = validate(Job(self.audio, self.output, self.mode, self.image,
                               "1080p" if self.resolution.get_selected() == 0 else "720p",
                               list(STYLES)[self.style.get_selected()], self.track_title.get_text()))
            self.controller.start(job)
            self.refresh()
        except (RenderError, OSError) as exc:
            self.toast(exc)

    def cancel_work(self):
        self.controller.stop()
        self.refresh()

    def poll(self):
        self.elapsed.set_text(self.controller.elapsed_text)
        if self.controller.drain():
            self.refresh()
            if self.controller.error:
                self.toast(self.controller.error.splitlines()[0])
        if self.closing and not self.controller.busy:
            self.poll_id = None
            self.destroy()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def open_video(self):
        if self.controller.result:
            try:
                Gio.AppInfo.launch_default_for_uri(self.controller.result.output.as_uri(), None)
            except GLib.Error as exc:
                self.toast(exc.message)

    def details(self):
        window = Adw.Window(transient_for=self, modal=True, title="Export details",
                            default_width=620, default_height=420)
        window.set_destroy_with_parent(True)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                            top_margin=20, bottom_margin=20, left_margin=20, right_margin=20)
        view.get_buffer().set_text(f"Audio to Video {__version__}\n\n{self.controller.error or self.controller.status}"
            "\n\nLocal CPU rendering: Python + Pillow + FFmpeg. Visualizers use fixed 48 kHz sample windows"
            " and 30 fps. Every decoded MP4 frame is compared with its visual and title references before saving."
            "\n\nQuantum Galaxy, GLUBALL Knot and ETQ Graph Walk use three audio bands as visual controls."
            " They are quantum-inspired artwork, not a physics simulation. ETQ follows real graph edges."
            "\n\nTemporary decoded audio uses about 660 MiB per hour, plus the MP4, in the destination folder."
            "\n\nUbuntu 24.04+: ./install-deps.sh\nThe application makes no network requests.")
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(view)
        toolbar.set_content(scroll)
        window.set_content(toolbar)
        window.present()

    def on_close(self, _window):
        self.closing = True
        self.chooser_cancel.cancel()
        self.controller.stop()
        self.refresh()
        return True


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.qsolkcb.AudioToVideo", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = Window(self)
        self.window.present()


def launch():
    if Gtk.get_minor_version() < 10 or (Adw.get_major_version(), Adw.get_minor_version()) < (1, 4):
        raise RuntimeError("GTK 4.10+ and libadwaita 1.4+ are required (Ubuntu 24.04+).")
    if not Gtk.init_check():
        raise RuntimeError("No graphical desktop display is available. Use the render command on a headless machine.")
    return Application().run(["audio2video"])
