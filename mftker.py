#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# License : GPLv3 : http://gplv3.fsf.org/


import tkinter as tk
import tkinter.filedialog
import tkinter.font
from tkinter import ttk
from PIL import Image, ImageTk

import os, sys
import configparser

class App(tk.Tk):


  def __init__(self):
    super().__init__()

    # instance variables
    self.input_images = [] # list of filenames
    self.widgets = {}      # list of widgets
    self.config  = {}      # configurations
    self.flags   = {}      # various flags used internally

    self.current_preview_index = -1;
    self.preview_cache = {
      'slots' : [None] * 5,
      'head'   : 0,
      'width'  : -1,
      'height' : -1
    }

    self.load_config()


    self.title('MFTker')
    self.geometry('1600x1000')
    self.minsize(1000, 700)
    self.resizable(True, True)

    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)

    # set up font and style
    style = ttk.Style()
    style.theme_use('default')
    style.configure('TNotebook.Tab', padding=[40, 5])
    style.configure('TFrame', background='#eeeeee')
    style.configure('TLabelframe', background='#f8f8f8', labelmargins=5)
    style.configure('TLabelframe.Label', background='#f8f8f8')
    style.configure('TCheckbutton', background='#f8f8f8')
    style.configure('TLabel', background='#f8f8f8')
    style.configure('TSpinbox', arrowsize=20)

    default_font = tk.font.nametofont('TkDefaultFont')
    default_font.configure(size=12)

    container = ttk.Frame(self)
    container.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)


    # create 3 tabs
    nb = ttk.Notebook(container)
    nb.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    nb.columnconfigure(0, weight=1)
    nb.rowconfigure(0, weight=1)

    tab_images = ttk.Frame(nb)
    tab_masks  = ttk.Frame(nb)
    tab_stack  = ttk.Frame(nb)

    tab_images.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_masks.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_stack.grid(column=0, row=0, sticky=(tk.NS, tk.EW))

    nb.add(tab_images, text='Images')
    nb.add(tab_masks, text='Masks')
    nb.add(tab_stack, text='Stack')


    # ==== set up images/files tab ====
    w = self.widgets # shorthand

    pn_tabimages = ttk.PanedWindow(tab_images, orient=tk.HORIZONTAL)

    pn_tabimages.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_images.columnconfigure(0, weight=1)
    tab_images.rowconfigure(0, weight=1)

    fr_images = ttk.Frame(pn_tabimages)
    fr_images.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    pn_tabimages.add(fr_images, weight=1)

    fr_images.columnconfigure(0, weight=1)
    fr_images.rowconfigure(0, weight=1)

    # image list
    w['lb_images'] = tk.Listbox(fr_images, selectmode='extended')
    w['lb_images'].grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    w['lb_images'].bind('<<ListboxSelect>>', self.lb_images_selected)
    w['lb_images'].bind('<Button-1>', self.lb_images_clicked)

    # scrollbar for image list
    s = ttk.Scrollbar(fr_images, orient=tk.VERTICAL, command=w['lb_images'].yview)
    s.grid(column=1, row=0, sticky=(tk.NS))
    w['lb_images']['yscrollcommand'] = s.set

    # preview pane
    w['cv_image_preview'] = tk.Canvas(pn_tabimages, background='#eeeeee')
    w['cv_image_preview'].grid(column=1, row=0, sticky=(tk.NS, tk.EW))
    w['cv_image_preview'].bind("<Configure>", lambda x: self.update_input_image_preview(self.current_preview_index))
    pn_tabimages.add(w['cv_image_preview'], weight=3)

    fr_image_actions = ttk.Frame(tab_images)
    fr_image_actions.grid(column=0, row=1, sticky=(tk.S, tk.EW))

    w['bt_image_add'] = ttk.Button(fr_image_actions, text='Add images', command=self.add_images)
    w['bt_image_add'].grid(column=0, row=0, padx=10, pady=10, ipadx=3)

    w['bt_image_remove'] = ttk.Button(fr_image_actions, text='Remove selected', command=self.remove_images)
    w['bt_image_remove'].grid(column=1, row=0, padx=10, pady=10, ipadx=3)



    # ==== set up Masks tab ====


    # ==== set up Stack tab ====
    tab_stack.rowconfigure(0, weight=0)
    tab_stack.rowconfigure(1, weight=0)
    tab_stack.rowconfigure(1, weight=1)
    tab_stack.columnconfigure(0, weight=0)
    tab_stack.columnconfigure(1, weight=2)


    # align_image_stack options
    fr_stack_align = ttk.Labelframe(tab_stack, text='Alignment')
    fr_stack_align.grid(column=0, row=0, sticky=(tk.N, tk.EW))

    w['ck_align'] = ttk.Checkbutton(fr_stack_align, text='Align images', onvalue='align', offvalue='no_align')
    w['ck_align'].grid(column=0, row=0, sticky=(tk.W, tk.N), padx=10, pady=5)

    w['ck_autocrop'] = ttk.Checkbutton(fr_stack_align, text='Autocrop', onvalue='autocrop', offvalue='no_autocrop')
    w['ck_autocrop'].grid(column=1, row=0, sticky=(tk.W), padx=10, pady=5)

    w['ck_centershift'] = ttk.Checkbutton(fr_stack_align, text='Optimize image center shift',
                                          onvalue='centershift', offvalue='no_centershift')
    w['ck_centershift'].grid(column=0, row=1, sticky=(tk.W), padx=10, pady=5)

    w['ck_fov'] = ttk.Checkbutton(fr_stack_align, text='Optimize field of view',
                                          onvalue='fov', offvalue='no_fov')
    w['ck_fov'].grid(column=1, row=1, sticky=(tk.W), padx=10, pady=5)

    # correlation threshold
    lb_corr_threshold = ttk.Label(fr_stack_align, text='Correlation threshold: ')
    lb_corr_threshold.grid(column=0, row=2, sticky=(tk.E), padx=10, pady=7)

    w['sp_corr_threshold'] = ttk.Spinbox(fr_stack_align, from_=0.0, to=1.0, increment=0.1, justify=tk.CENTER)
    w['sp_corr_threshold'].grid(column=1, row=2, sticky=(tk.W), padx=10, pady=7)

    # control points
    lb_control_points = ttk.Label(fr_stack_align, text='Number of control points: ')
    lb_control_points.grid(column=0, row=3, sticky=(tk.E), padx=10, pady=7)

    w['sp_control_points'] = ttk.Spinbox(fr_stack_align, from_=0, to=50, increment=1, justify=tk.CENTER)
    w['sp_control_points'].grid(column=1, row=3, sticky=(tk.W), padx=10, pady=7)

    # grid size
    lb_grid_size = ttk.Label(fr_stack_align, text='Grid size: ')
    lb_grid_size.grid(column=0, row=4, sticky=(tk.E), padx=10, pady=7)

    w['sp_grid_size'] = ttk.Spinbox(fr_stack_align, from_=1, to=10, increment=1, justify=tk.CENTER)
    w['sp_grid_size'].grid(column=1, row=4, sticky=(tk.W), padx=10, pady=7)

    # scale factor
    lb_scale_factor = ttk.Label(fr_stack_align, text='Scale factor: ')
    lb_scale_factor.grid(column=0, row=5, sticky=(tk.E), padx=10, pady=7)

    w['sp_scale_factor'] = ttk.Spinbox(fr_stack_align, from_=1, to=5, increment=1, justify=tk.CENTER)
    w['sp_scale_factor'].grid(column=1, row=5, sticky=(tk.W), padx=10, pady=7)

    # Fusion options
    fr_stack_fusion = ttk.Labelframe(tab_stack, text='Fusion')
    fr_stack_fusion.grid(column=0, row=1, sticky=(tk.N, tk.EW))

    w['ck_align'] = ttk.Checkbutton(fr_stack_fusion, text='force hard mask', onvalue='hardmask', offvalue='no_hardmask')
    w['ck_align'].grid(column=0, row=0, sticky=(tk.W), padx=10, pady=5)

    # stacked preview pane
    w['cv_stacked_preview'] = tk.Canvas(tab_stack, background='#eeeeee')
    w['cv_stacked_preview'].grid(column=1, row=0, rowspan=3, sticky=(tk.NS, tk.EW))
    #w['cv_stacked_preview'].bind("<Configure>", self.update_stacked_image_preview)

    nb.select(2) # debug

  def add_images(self):
    initial_dir = '~'

    if 'prefs' in self.config and 'last_opened_location' in self.config['prefs']:
      initial_dir = self.config['prefs']['last_opened_location']

    filenames = tk.filedialog.askopenfilenames(title='Add images', initialdir=initial_dir, filetypes=[
              ('image', '.jpg'),
              ('image', '.jpeg'),
              ('image', '.png'),
              ('image', '.tif'),
              ('image', '.tiff')
            ])

    if len(filenames) == 0:
      return

    # save the current location
    self.config.set('prefs', 'last_opened_location', os.path.dirname(filenames[0]))

    # update the image list
    for filename in filenames:
      self.widgets['lb_images'].insert('end', ' ' + os.path.basename(filename))
      self.input_images.append(filename)


  def remove_images(self):
    selection = self.widgets['lb_images'].curselection()

    for i in reversed(selection):
      self.input_images.pop(i)
      self.widgets['lb_images'].delete(i)


  def lb_images_clicked(self, event):
    self.flags['lb_images_clicked'] = True
    index = self.widgets['lb_images'].index("@%s,%s" % (event.x, event.y))
    self.update_input_image_preview(index)


  def lb_images_selected(self, event):
    if self.flags['lb_images_clicked']:
      self.flags['lb_images_clicked'] = False
      return

    selection = self.widgets['lb_images'].curselection()
    self.update_input_image_preview(selection[-1])


  def update_input_image_preview(self, index):
    # update the preview with the specified image at index
    if index < 0:
      return

    self.current_preview_index = index
    cv = self.widgets['cv_image_preview']
    width = cv.winfo_width()
    height = cv.winfo_height()

    # if size changed, clear buffer
    hit = False

    if self.preview_cache['width'] != width or self.preview_cache['height'] != height:
      self.preview_cache['slots'] = [None] * len(self.preview_cache['slots'])
      self.preview_cache['width'] = width
      self.preview_cache['height'] = height
    else:
      # check buffer
      for item in self.preview_cache['slots']:
        if item and item['filename'] == self.input_images[index]:
          img = item['img']
          hit = True
          break

    if hit == False:
      img = Image.open(self.input_images[index])
      img.thumbnail((width, height), Image.LANCZOS)
      img = ImageTk.PhotoImage(img)

      buffer_slot = self.preview_cache['head'] % len(self.preview_cache['slots'])
      self.preview_cache['slots'][buffer_slot] = {
        'filename' : self.input_images[index],
        'img'      : img
      }
      self.preview_cache['head'] = (self.preview_cache['head']+1) % len(self.preview_cache['slots'])

    cv.create_image(width/2, height/2, anchor=tk.CENTER, image=img)
    cv.image = img


  def load_config(self):
    self.config = configparser.ConfigParser()

    if os.path.isfile('config.ini'):
      self.config.read('config.ini')

    if not self.config.has_section('prefs'):
      self.config.add_section('prefs')


  def save_configs(self):
    with open('config.ini', 'w') as configfile:
      self.config.write(configfile)


if __name__ == "__main__":
  app = App()
  app.mainloop()
  app.save_configs()