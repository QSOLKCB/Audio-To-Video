"""Small standard-library desktop for Windows/macOS; GTK stays native on Linux."""
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk

from .core import AUDIO_FORMATS, IMAGE_FORMATS, Job, validate
from .desktop import Controller, next_output
from .process import RenderError
from .title import normalize_title, title_image
from .visualizer import HEIGHT, STYLES, WIDTH, render


class Window:
    def __init__(self, root, controller=None):
        self.root = root
        self.controller = controller or Controller()
        self.audio = self.image = self.output = None
        self.closing = False
        self.preview_key = None
        root.title('Audio to Video — QSOL-IMC')
        root.geometry('760x840')
        root.minsize(640, 560)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-o>', lambda _: self.choose_audio())
        root.bind('<Control-Return>', lambda _: self.start())
        root.bind('<Escape>', lambda _: self.cancel())
        if sys.platform == 'darwin':
            root.bind('<Command-o>', lambda _: self.choose_audio())
            root.bind('<Command-Return>', lambda _: self.start())
        # A scrollable form keeps all actions reachable on small laptop displays.
        viewport = ttk.Frame(root)
        viewport.pack(fill='both', expand=True)
        canvas = self.viewport_canvas = tk.Canvas(viewport, highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(canvas, padding=20)
        interior = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(interior, width=event.width))
        root.bind('<MouseWheel>', lambda event: canvas.yview_scroll(
            -int(event.delta) if sys.platform == 'darwin' else -int(event.delta/120), 'units'))
        root.bind('<Button-4>', lambda _: canvas.yview_scroll(-1, 'units'))
        root.bind('<Button-5>', lambda _: canvas.yview_scroll(1, 'units'))
        body.columnconfigure(1, weight=1)
        self.controls = []
        ttk.Label(body, text='Audio in. Video out.', font=('TkDefaultFont', 22, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Label(body, text='Local processing. Every video frame checked before saving.').grid(
            row=1, column=0, columnspan=3, sticky='w', pady=(0, 12))
        self.audio_text = tk.StringVar(value='Choose MP3, M4A or WAV')
        self.image_text = tk.StringVar(value='Choose PNG or JPEG')
        self.output_text = tk.StringVar(value='Choose audio first')
        for row, caption, variable, callback in (
                (2, 'Audio', self.audio_text, self.choose_audio),
                (3, 'Image', self.image_text, self.choose_image),
                (9, 'Save MP4', self.output_text, self.choose_output)):
            ttk.Label(body, text=caption).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)
            ttk.Label(body, textvariable=variable, wraplength=320).grid(row=row, column=1, sticky='w')
            button = ttk.Button(body, text='Choose…', command=callback)
            button.grid(row=row, column=2, sticky='e')
            self.controls.append(button)
        self.mode = tk.StringVar(value='visualizer')
        modes = ttk.Frame(body)
        modes.grid(row=4, column=0, columnspan=3, sticky='w', pady=8)
        for text, value in (('Still image', 'still'), ('Visualizer', 'visualizer')):
            button = ttk.Radiobutton(modes, text=text, value=value, variable=self.mode, command=self.changed)
            button.pack(side='left', padx=(0, 18))
            self.controls.append(button)
        self.style = tk.StringVar(value=next(iter(STYLES.values())))
        self.styles = ttk.Combobox(body, textvariable=self.style, values=list(STYLES.values()), state='readonly')
        self.styles.grid(row=5, column=0, columnspan=3, sticky='ew', pady=4)
        self.styles.bind('<<ComboboxSelected>>', lambda _: self.changed())
        self.controls.append(self.styles)
        self.preview = ttk.Label(body, anchor='center')
        self.preview.grid(row=6, column=0, columnspan=3, sticky='nsew', pady=6)
        body.rowconfigure(6, weight=1)
        self.preview_note = tk.StringVar()
        ttk.Label(body, textvariable=self.preview_note, wraplength=560).grid(
            row=7, column=0, columnspan=3, sticky='w')
        self.title = tk.StringVar()
        title_row = ttk.Frame(body)
        title_row.grid(row=8, column=0, columnspan=3, sticky='ew', pady=8)
        title_row.columnconfigure(1, weight=1)
        ttk.Label(title_row, text='Name – Track (optional)').grid(row=0, column=0, padx=(0, 12))
        entry = ttk.Entry(title_row, textvariable=self.title)
        entry.grid(row=0, column=1, sticky='ew')
        self.controls.append(entry)
        self.title.trace_add('write', lambda *_: self.changed())
        self.resolution = tk.StringVar(value='1080p')
        self.sizes = ttk.Combobox(body, textvariable=self.resolution, values=['1080p', '720p'], state='readonly', width=12)
        self.sizes.grid(row=10, column=0, sticky='w', pady=8)
        self.sizes.bind('<<ComboboxSelected>>', lambda _: self.changed())
        self.controls.append(self.sizes)
        ttk.Label(body, text='16:9 · 30 fps · 720p exports faster').grid(row=10, column=1, columnspan=2, sticky='w')
        self.progress = ttk.Progressbar(body, maximum=1)
        self.progress.grid(row=11, column=0, columnspan=3, sticky='ew', pady=8)
        self.status = tk.StringVar(value=self.controller.status)
        ttk.Label(body, textvariable=self.status, wraplength=560).grid(row=12, column=0, columnspan=3, sticky='w')
        self.elapsed = tk.StringVar()
        ttk.Label(body, textvariable=self.elapsed).grid(row=13, column=0, columnspan=3, sticky='w', pady=4)
        actions = ttk.Frame(body)
        actions.grid(row=14, column=0, columnspan=3, sticky='ew', pady=(12, 0))
        self.open_button = ttk.Button(actions, text='Open video', command=self.open_video)
        self.open_button.pack(side='left')
        ttk.Button(actions, text='Details', command=self.details).pack(side='left', padx=6)
        self.export_button = ttk.Button(actions, text='Create MP4', command=self.start)
        self.export_button.pack(side='right')
        self.cancel_button = ttk.Button(actions, text='Cancel', command=self.cancel)
        self.cancel_button.pack(side='right', padx=6)
        self.refresh()
        self.poll_id = root.after(80, self.poll)

    def changed(self):
        if self.controller.busy or self.closing:
            return
        self.controller.result, self.controller.error = None, ''
        self.controller.status = 'Ready to create MP4.' if self.audio else 'Choose an audio file to begin.'
        self.controller.fraction = 0
        self.refresh()

    def refresh(self):
        busy = self.controller.busy or self.closing
        for control in self.controls:
            control.configure(state='disabled' if busy else 'readonly' if control in (self.styles, self.sizes) else 'normal')
        if not busy and self.mode.get() == 'still':
            self.styles.configure(state='disabled')
        ready = not busy and self.audio and self.output and (self.mode.get() == 'visualizer' or self.image)
        self.export_button.configure(state='normal' if ready else 'disabled', text='Working…' if busy else 'Create MP4')
        self.cancel_button.configure(state='normal' if self.controller.busy and not self.controller.cancel.is_set() else 'disabled')
        self.open_button.configure(state='normal' if self.controller.result and not busy else 'disabled')
        self.audio_text.set(self.audio.name if self.audio else 'Choose MP3, M4A or WAV')
        self.image_text.set(self.image.name if self.image else 'Choose PNG or JPEG')
        self.output_text.set(str(self.output) if self.output else 'Choose audio first')
        self.progress['value'] = self.controller.fraction
        self.status.set(self.controller.status)
        self.preview_note.set('Style preview; movement follows the audio during export.' if self.mode.get() == 'visualizer'
                              else 'Image preview; the whole image fits below any title during export.')
        key = (self.mode.get(), self.style.get(), self.title.get(), self.image)
        if key != self.preview_key and not busy:
            try:
                if self.mode.get() == 'still' and self.image:
                    with Image.open(self.image) as source:
                        picture = ImageOps.contain(source.convert('RGB'), (WIDTH, HEIGHT))
                        canvas = Image.new('RGB', (WIDTH, HEIGHT), (12, 18, 25))
                        canvas.paste(picture, ((WIDTH-picture.width)//2, (HEIGHT-picture.height)//2))
                        picture = canvas
                elif self.mode.get() == 'still':
                    picture = Image.new('RGB', (WIDTH, HEIGHT), (12, 18, 25))
                    ImageDraw.Draw(picture).text((210, 170), 'Choose a PNG or JPEG', fill=(132, 166, 180))
                else:
                    style = next(k for k, v in STYLES.items() if v == self.style.get())
                    picture = Image.frombytes('RGB', (WIDTH, HEIGHT), render(b'', style, 60))
                title = normalize_title(self.title.get())
                if title and self.mode.get() == 'visualizer':
                    picture.paste(title_image(title, WIDTH), (0, 0))
                self.texture = ImageTk.PhotoImage(picture.resize((560, 315)))
                self.preview.configure(image=self.texture)
            except (OSError, ValueError, RenderError, Image.DecompressionBombError) as exc:
                self.status.set(str(exc))
            self.preview_key = key

    def choose_audio(self):
        if self.controller.busy or self.closing:
            return
        value = filedialog.askopenfilename(parent=self.root, title='Choose audio',
                                          filetypes=[('Audio', '*.mp3 *.MP3 *.m4a *.M4A *.wav *.WAV')])
        if value:
            self.audio = Path(value)
            self.output = next_output(self.audio)
            self.changed()

    def choose_image(self):
        if self.controller.busy or self.closing:
            return
        value = filedialog.askopenfilename(parent=self.root, title='Choose image',
                                          filetypes=[('Image', '*.png *.PNG *.jpg *.JPG *.jpeg *.JPEG')])
        if value:
            self.image = Path(value)
            self.changed()

    def choose_output(self):
        if self.controller.busy or self.closing:
            return
        value = filedialog.asksaveasfilename(parent=self.root, title='Save a new MP4', defaultextension='.mp4',
            filetypes=[('MP4', '*.mp4')], initialfile=self.output.name if self.output else 'video.mp4',
            initialdir=str(self.output.parent) if self.output else None)
        if value:
            self.output = Path(value)
            self.changed()

    def start(self):
        if self.controller.busy or self.closing or not self.audio or not self.output:
            return
        try:
            style = next(k for k, v in STYLES.items() if v == self.style.get())
            job = validate(Job(self.audio, self.output, self.mode.get(), self.image,
                               self.resolution.get(), style, self.title.get()))
            self.controller.start(job)
            self.refresh()
        except (RenderError, OSError) as exc:
            messagebox.showerror('Cannot create MP4', str(exc), parent=self.root)

    def cancel(self):
        self.controller.stop()
        self.refresh()

    def poll(self):
        if self.controller.drain():
            self.refresh()
        self.elapsed.set(self.controller.elapsed_text)
        if self.closing and not self.controller.busy:
            self.root.destroy()
            return
        self.poll_id = self.root.after(80, self.poll)

    def close(self):
        self.closing = True
        self.controller.stop()
        self.refresh()

    def details(self):
        messagebox.showinfo('Export details', self.controller.error or self.controller.status, parent=self.root)

    def open_video(self):
        if not self.controller.result:
            return
        path = str(self.controller.result.output)
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', path])
        except OSError as exc:
            messagebox.showerror('Cannot open video', str(exc), parent=self.root)


def launch():
    root = tk.Tk()
    Window(root)
    root.mainloop()
    return 0
