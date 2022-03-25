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
    self.minsize(1200, 1000)
    self.resizable(True, True)

    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)

    self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # set up font and style
    style = ttk.Style()
    style.theme_use('default')
    style.configure('TNotebook.Tab', padding=[40, 5])
    style.configure('TFrame', background='#f8f8f8')
    style.configure('TLabelframe', background='#f8f8f8', labelmargins=10, padding=0)
    style.configure('TLabelframe.Label', background='#f8f8f8')
    style.configure('TCheckbutton', background='#f8f8f8')
    style.configure('TLabel', background='#f8f8f8')
    style.configure('TSpinbox', arrowsize=17)
    style.configure('TCombobox', arrowsize=17, fieldbackground='#f8f8f8')
    style.map('TCombobox', fieldbackground=[('readonly', '#f8f8f8')])

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
    w['cv_image_preview'].bind('<Configure>', lambda x: self.update_input_image_preview(self.current_preview_index))
    pn_tabimages.add(w['cv_image_preview'], weight=3)

    fr_image_actions = ttk.Frame(tab_images)
    fr_image_actions.grid(column=0, row=1, sticky=(tk.S, tk.EW))

    w['bt_image_add'] = ttk.Button(fr_image_actions, text='Add images', command=self.add_images)
    w['bt_image_add'].grid(column=0, row=0, padx=10, pady=10, ipadx=3)

    w['bt_image_remove'] = ttk.Button(fr_image_actions, text='Remove selected', command=self.remove_images)
    w['bt_image_remove'].grid(column=1, row=0, padx=10, pady=10, ipadx=3)



    # ==== set up Masks tab ====


    # ==== set up Stack tab ====
    tab_stack.rowconfigure(5, weight=1)
    tab_stack.columnconfigure(1, weight=2)


    # align_image_stack options
    fr_stack_align = ttk.Labelframe(tab_stack, text='Alignment')
    fr_stack_align.grid(column=0, row=0, sticky=(tk.N, tk.EW))

    v_ck_align = tk.BooleanVar()
    w['ck_align'] = ttk.Checkbutton(fr_stack_align, text='Align images', onvalue=True, offvalue=False,
                                    variable=v_ck_align, command=self.ui_ck_align_changed)
    w['ck_align'].grid(column=0, row=0, sticky=(tk.W, tk.N), padx=20, pady=5)
    w['ck_align'].var = v_ck_align

    v_ck_autocrop = tk.BooleanVar()
    w['ck_autocrop'] = ttk.Checkbutton(fr_stack_align, text='Autocrop', onvalue=True, offvalue=False,
                                       variable=v_ck_autocrop)
    w['ck_autocrop'].grid(column=1, row=0, sticky=(tk.W), padx=20, pady=5)
    w['ck_autocrop'].var = v_ck_autocrop

    v_ck_centershift = tk.BooleanVar()
    w['ck_centershift'] = ttk.Checkbutton(fr_stack_align, text='Optimize image center shift',
                                          onvalue=True, offvalue=False, variable=v_ck_centershift)
    w['ck_centershift'].grid(column=0, row=1, sticky=(tk.W), padx=20, pady=5)
    w['ck_centershift'].var = v_ck_centershift

    v_ck_fov = tk.BooleanVar()
    w['ck_fov'] = ttk.Checkbutton(fr_stack_align, text='Optimize field of view', onvalue=True, offvalue=False,
                                  variable=v_ck_fov)
    w['ck_fov'].grid(column=1, row=1, sticky=(tk.W), padx=20, pady=5)
    w['ck_fov'].var = v_ck_fov

    # correlation threshold
    lb_corr_threshold = ttk.Label(fr_stack_align, text='Correlation threshold: ')
    lb_corr_threshold.grid(column=0, row=2, sticky=(tk.E), padx=20, pady=10)

    v_sp_corr_threshold = tk.StringVar()
    w['sp_corr_threshold'] = ttk.Spinbox(fr_stack_align, from_=0.0, to=1.0, increment=0.1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_corr_threshold)
    w['sp_corr_threshold'].grid(column=1, row=2, sticky=(tk.W), padx=20, pady=10)
    w['sp_corr_threshold'].var = v_sp_corr_threshold

    # control points
    ttk.Label(fr_stack_align, text='Number of control points: ').grid(column=0, row=3, sticky=(tk.E), padx=20, pady=7)

    v_sp_control_points = tk.IntVar()
    w['sp_control_points'] = ttk.Spinbox(fr_stack_align, from_=0, to=50, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_control_points)
    w['sp_control_points'].grid(column=1, row=3, sticky=(tk.W), padx=20, pady=7)
    w['sp_control_points'].var = v_sp_control_points

    # grid size
    lb_grid_size = ttk.Label(fr_stack_align, text='Grid size: ')
    lb_grid_size.grid(column=0, row=4, sticky=(tk.E), padx=20, pady=7)

    v_sp_grid_size = tk.IntVar()
    w['sp_grid_size'] = ttk.Spinbox(fr_stack_align, from_=1, to=10, increment=1,
                                    justify=tk.CENTER, width=10, textvariable=v_sp_grid_size)
    w['sp_grid_size'].grid(column=1, row=4, sticky=(tk.W), padx=20, pady=7)
    w['sp_grid_size'].var = v_sp_grid_size

    # scale factor
    lb_scale_factor = ttk.Label(fr_stack_align, text='Scale factor: ')
    lb_scale_factor.grid(column=0, row=5, sticky=(tk.E), padx=20, pady=7)

    v_sp_scale_factor = tk.IntVar()
    w['sp_scale_factor'] = ttk.Spinbox(fr_stack_align, from_=1, to=5, increment=1,
                                       justify=tk.CENTER, width=10, textvariable=v_sp_scale_factor)
    w['sp_scale_factor'].grid(column=1, row=5, sticky=(tk.W), padx=20, pady=7)
    w['sp_scale_factor'].var = v_sp_scale_factor

    ttk.Frame(fr_stack_align).grid(column=0, row=6, pady=5)  # padding bottom


    # Fusion options
    ttk.Frame(tab_stack).grid(column=0, row=1, sticky=(tk.N, tk.EW), pady=5)  # padding between frames

    fr_stack_fusion = ttk.Labelframe(tab_stack, text='Fusion')
    fr_stack_fusion.grid(column=0, row=2, sticky=(tk.N, tk.EW))
    fr_stack_fusion.columnconfigure(3, weight=1)

    v_ck_hard_mask = tk.BooleanVar()
    w['ck_hard_mask'] = ttk.Checkbutton(fr_stack_fusion, text='Force hard mask', onvalue=True, offvalue=False,
                                        variable=v_ck_hard_mask)
    w['ck_hard_mask'].grid(column=0, columnspan=3, row=0, sticky=(tk.W), padx=10, pady=5)
    w['ck_hard_mask'].var = v_ck_hard_mask

    # pyramid level
    ttk.Label(fr_stack_fusion, text='Blending levels: ').grid(column=0, row=1, sticky=(tk.E), padx=10, pady=7)

    v_sp_levels = tk.IntVar()
    w['sp_levels'] = ttk.Spinbox(fr_stack_fusion, from_=1, to=29, increment=1,
                                 justify=tk.CENTER, width=10, textvariable=v_sp_levels)
    w['sp_levels'].grid(column=1, row=1, sticky=(tk.W), padx=20, pady=7)
    w['sp_levels'].var = v_sp_levels

    v_ck_levels = tk.BooleanVar()
    w['ck_levels'] = ttk.Checkbutton(fr_stack_fusion, text='Auto', onvalue=True, offvalue=False,
                                     variable=v_ck_levels, command=self.ui_ck_levels_changed)
    w['ck_levels'].grid(column=2, row=1, sticky=(tk.W), padx=20, pady=7)
    w['ck_levels'].var = v_ck_levels

    # contrast window size
    ttk.Label(fr_stack_fusion, text='Constrast window size: ').grid(column=0, row=2, sticky=(tk.E), padx=10, pady=7)

    v_sp_window_size = tk.IntVar()
    w['sp_window_size'] = ttk.Spinbox(fr_stack_fusion, from_=3, to=50, increment=1,
                                      justify=tk.CENTER, width=10, textvariable=v_sp_window_size)
    w['sp_window_size'].grid(column=1, row=2, sticky=(tk.W), padx=20, pady=7)
    w['sp_window_size'].var = v_sp_window_size

    # contrast edge scale
    v_ck_edge_scale = tk.BooleanVar()
    w['ck_edge_scale'] = ttk.Checkbutton(fr_stack_fusion, text='Contrast edge scale:', onvalue=True, offvalue=False,
                                         variable=v_ck_edge_scale, command=self.ui_ck_edge_scale_changed)
    w['ck_edge_scale'].grid(column=0, row=3, sticky=(tk.W), padx=10, pady=7)
    w['ck_edge_scale'].var = v_ck_edge_scale

    fr_edge_scale = ttk.Frame(fr_stack_fusion)
    fr_edge_scale.grid(column=1, columnspan=2, row=3, sticky=(tk.EW))

    v_sp_edge_scale = tk.IntVar()
    w['sp_edge_scale'] = ttk.Spinbox(fr_edge_scale, from_=1, to=100, increment=1,
                                     justify=tk.CENTER, width=5, textvariable=v_sp_edge_scale)
    w['sp_edge_scale'].grid(column=0, row=0, sticky=(tk.W), padx=20, pady=7)
    w['sp_edge_scale'].var = v_sp_edge_scale

    v_sp_lce_scale = tk.IntVar()
    w['sp_lce_scale'] = ttk.Spinbox(fr_edge_scale, from_=1, to=100, increment=1,
                                    justify=tk.CENTER, width=5, textvariable=v_sp_lce_scale)
    w['sp_lce_scale'].grid(column=1, row=0, sticky=(tk.W), padx=0, pady=7)
    w['sp_lce_scale'].var = v_sp_lce_scale

    v_ck_lce_scale = tk.BooleanVar()
    w['ck_lce_scale'] = ttk.Checkbutton(fr_edge_scale, text='%', onvalue=True, offvalue=False,
                                        var=v_ck_lce_scale)
    w['ck_lce_scale'].grid(column=2, row=0, sticky=(tk.W), padx=5, pady=7)
    w['ck_lce_scale'].var = v_ck_lce_scale

    v_sp_lce_level = tk.IntVar()
    w['sp_lce_level'] = ttk.Spinbox(fr_edge_scale, from_=1, to=100, increment=1,
                                    justify=tk.CENTER, width=5, textvariable=v_sp_lce_level)
    w['sp_lce_level'].grid(column=3, row=0, sticky=(tk.W), padx=0, pady=7)
    w['sp_lce_level'].var = v_sp_lce_level

    v_ck_lce_level = tk.BooleanVar()
    w['ck_lce_level'] = ttk.Checkbutton(fr_edge_scale, text='%', onvalue=True, offvalue=False,
                                        var=v_ck_lce_level)
    w['ck_lce_level'].grid(column=4, row=0, sticky=(tk.W), padx=5, pady=7)
    w['ck_lce_level'].var = v_ck_lce_level

    # contrast min curvature
    v_ck_curvature = tk.BooleanVar()
    w['ck_curvature'] = ttk.Checkbutton(fr_stack_fusion, text='Contrast min curvature:', onvalue=True, offvalue=False,
                                        variable=v_ck_curvature, command=self.ui_ck_curvature_changed)
    w['ck_curvature'].grid(column=0, row=4, sticky=(tk.W), padx=10, pady=7)
    w['ck_curvature'].var = v_ck_curvature

    w['sp_curvature'] = ttk.Spinbox(fr_stack_fusion, from_=1, to=100, increment=1, justify=tk.CENTER, width=10)
    w['sp_curvature'].grid(column=1, row=4, sticky=(tk.W), padx=20, pady=7)

    v_ck_curvature_pc = tk.BooleanVar()
    w['ck_curvature_pc'] = ttk.Checkbutton(fr_stack_fusion, text='%', onvalue=True, offvalue=False,
                                           variable=v_ck_curvature_pc)
    w['ck_curvature_pc'].grid(column=2, row=4, sticky=(tk.W), padx=0, pady=7)
    w['ck_curvature_pc'].var = v_ck_curvature_pc

    # gray projector
    ttk.Label(fr_stack_fusion, text='Gray projector: ').grid(column=0, row=5, sticky=(tk.E), padx=10, pady=7)

    gray_proj_value = ('anti-value', 'average', 'l-star', 'lightness', 'luminance', 'pl-star', 'value')
    v_cb_gray_proj = tk.StringVar()
    w['cb_gray_proj'] = ttk.Combobox(fr_stack_fusion, justify=tk.CENTER, values=gray_proj_value,
                                     state='readonly',textvariable=v_cb_gray_proj)
    w['cb_gray_proj'].grid(column=1, row=5, sticky=(tk.W), padx=20, pady=7)
    w['cb_gray_proj'].bind('<<ComboboxSelected>>', lambda x : w['cb_gray_proj'].selection_clear())
    w['cb_gray_proj'].var = v_cb_gray_proj

    ttk.Frame(fr_stack_fusion).grid(column=0, row=6, pady=5)  # padding bottom


    # Output options
    ttk.Frame(tab_stack).grid(column=0, row=3, sticky=(tk.N, tk.EW), pady=5)  # padding between frames

    fr_stack_output = ttk.Labelframe(tab_stack, text='Output')
    fr_stack_output.grid(column=0, row=4, sticky=(tk.N, tk.EW))
    fr_stack_output.columnconfigure(3, weight=1)

    # preview size
    ttk.Label(fr_stack_output, text='Preview size  ').grid(column=0, row=0, sticky=(tk.W), padx=10, pady=7)

    fr_preview_size = ttk.Frame(fr_stack_output)
    fr_preview_size.grid(column=1, row=0, sticky=(tk.E))

    ttk.Label(fr_preview_size, text='width: ').grid(column=0, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_preview_w = tk.IntVar()
    w['en_preview_w'] = ttk.Entry(fr_preview_size, width=10, justify=tk.CENTER, textvariable=v_en_preview_w)
    w['en_preview_w'].grid(column=1, row=0, sticky=(tk.W), padx=5, pady=7)
    w['en_preview_w'].var = v_en_preview_w

    ttk.Label(fr_preview_size, text='   height: ').grid(column=2, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_preview_h = tk.IntVar()
    w['en_preview_h'] = ttk.Entry(fr_preview_size, width=10, justify=tk.CENTER, textvariable=v_en_preview_h)
    w['en_preview_h'].grid(column=3, row=0, sticky=(tk.W), padx=5, pady=7)
    w['en_preview_h'].var = v_en_preview_h


    # final output size
    v_ck_output_size = tk.BooleanVar()
    w['ck_output_size'] = ttk.Checkbutton(fr_stack_output, text='Final size', onvalue=True, offvalue=False,
                                           variable=v_ck_output_size, command=self.ui_ck_output_size_changed)
    w['ck_output_size'].grid(column=0, row=1, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['ck_output_size'].var = v_ck_output_size

    fr_output_size = ttk.Frame(fr_stack_output)
    fr_output_size.grid(column=1, row=1, sticky=(tk.EW))

    ttk.Label(fr_output_size, text='width: ').grid(column=0, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_output_w = tk.IntVar()
    w['en_output_w'] = ttk.Entry(fr_output_size, width=10, justify=tk.CENTER, textvariable=v_en_output_w)
    w['en_output_w'].grid(column=1, row=0, sticky=(tk.W), padx=5, pady=7)
    w['en_output_w'].var = v_en_output_w

    ttk.Label(fr_output_size, text=' height: ').grid(column=2, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_output_h = tk.IntVar()
    w['en_output_h'] = ttk.Entry(fr_output_size, width=10, justify=tk.CENTER, textvariable=v_en_output_h)
    w['en_output_h'].grid(column=3, row=0, sticky=(tk.W), padx=5, pady=7)
    w['en_output_h'].var = v_en_output_h

    ttk.Label(fr_output_size, text='x-offset: ').grid(column=0, row=1, sticky=(tk.E), padx=5, pady=7)

    v_en_output_xoffset = tk.IntVar()
    w['en_output_xoffset'] = ttk.Entry(fr_output_size, width=10, justify=tk.CENTER, textvariable=v_en_output_xoffset)
    w['en_output_xoffset'].grid(column=1, row=1, sticky=(tk.W), padx=5, pady=7)
    w['en_output_xoffset'].var = v_en_output_xoffset

    ttk.Label(fr_output_size, text=' y-offset: ').grid(column=2, row=1, sticky=(tk.E), padx=5, pady=7)

    v_en_output_yoffset = tk.IntVar()
    w['en_output_yoffset'] = ttk.Entry(fr_output_size, width=10, justify=tk.CENTER, textvariable=v_en_output_yoffset)
    w['en_output_yoffset'].grid(column=3, row=1, sticky=(tk.W), padx=5, pady=7)
    w['en_output_yoffset'].var = v_en_output_yoffset

    # file format
    fr_file_format = ttk.Frame(fr_stack_output)
    fr_file_format.grid(column=0, columnspan=3, row=2, sticky=(tk.W), padx=10, pady=7)

    ttk.Label(fr_file_format, text='Format: ').grid(column=0, row=0, sticky=(tk.W), padx=10, pady=7)

    v_cb_file_format = tk.StringVar()
    w['cb_file_format'] = ttk.Combobox(fr_file_format, justify=tk.CENTER, values=('JPG', 'TIFF'),
                                       textvariable=v_cb_file_format, state='readonly', width=10)
    w['cb_file_format'].grid(column=1, row=0, sticky=(tk.W), padx=10, pady=7)
    w['cb_file_format'].bind('<<ComboboxSelected>>', self.ui_cb_file_format_changed)
    w['cb_file_format'].var = v_cb_file_format

    # JPG options
    w['fr_jpg_options'] = ttk.Frame(fr_file_format)
    w['fr_jpg_options'].grid(column=2, row=0, sticky=(tk.W), padx=10, pady=7)

    ttk.Label(w['fr_jpg_options'], text='JPG quality: ').grid(column=0, row=0, sticky=(tk.W))

    v_sp_jpg_quality = tk.IntVar()
    w['sp_jpg_quality'] = ttk.Spinbox(w['fr_jpg_options'], justify=tk.CENTER, from_=80, to=100,
                                      increment=10, width=10, textvariable=v_sp_jpg_quality)
    w['sp_jpg_quality'].grid(column=1, row=0, sticky=(tk.W))
    w['sp_jpg_quality'].var = v_sp_jpg_quality

    # TIFF options
    w['fr_tif_options'] = ttk.Frame(fr_file_format)
    w['fr_tif_options'].grid(column=2, row=0, sticky=(tk.W), padx=10, pady=7)

    ttk.Label(w['fr_tif_options'], text='TIFF compression: ').grid(column=0, row=0, sticky=(tk.W))

    v_cb_tif_compression = tk.StringVar()
    w['cb_tif_compression'] = ttk.Combobox(w['fr_tif_options'], justify=tk.CENTER, width=10,
                                           values=('none', 'packbit', 'lzw', 'deflate'), state='readonly',
                                           textvariable=v_cb_tif_compression)
    w['cb_tif_compression'].grid(column=1, row=0, sticky=(tk.W))
    w['cb_tif_compression'].var = v_cb_tif_compression
    w['cb_tif_compression'].bind('<<ComboboxSelected>>', lambda x : w['cb_tif_compression'].selection_clear())

    ttk.Frame(fr_stack_output).grid(column=0, row=3, pady=5)  # padding bottom


    # output actions
    fr_stack_actions = ttk.Frame(tab_stack)
    fr_stack_actions.grid(column=0, row=5, sticky=(tk.N, tk.EW), pady=20)
    fr_stack_actions.columnconfigure(0, weight=1)
    fr_stack_actions.columnconfigure(1, weight=1)

    w['bt_preview'] = ttk.Button(fr_stack_actions, text='Preview')
    w['bt_preview'].grid(column=0, row=0)

    w['bt_stack'] = ttk.Button(fr_stack_actions, text='Stack')
    w['bt_stack'].grid(column=1, row=0)


    # stacked preview pane
    w['cv_stacked_preview'] = tk.Canvas(tab_stack, background='#eeeeee')
    w['cv_stacked_preview'].grid(column=1, row=0, rowspan=6, sticky=(tk.NS, tk.EW))
    #w['cv_stacked_preview'].bind("<Configure>", self.update_stacked_image_preview)

    nb.select(2) # debug

    self.apply_config()


  def ui_ck_align_changed(self):
    w = self.widgets
    st = tk.NORMAL
    if w['ck_align'].var.get() == False:
      st = tk.DISABLED

    w['ck_autocrop'].config(state=st)
    w['ck_centershift'].config(state=st)
    w['ck_fov'].config(state=st)
    w['sp_corr_threshold'].config(state=st)
    w['sp_control_points'].config(state=st)
    w['sp_grid_size'].config(state=st)
    w['sp_scale_factor'].config(state=st)


  def ui_ck_levels_changed(self):
    w = self.widgets
    if w['ck_levels'].var.get() == True:
      w['sp_levels'].config(state=tk.DISABLED)
    else:
      w['sp_levels'].config(state=tk.NORMAL)


  def ui_ck_edge_scale_changed(self):
    w = self.widgets
    st = tk.NORMAL
    if w['ck_edge_scale'].var.get() == False:
      st = tk.DISABLED

    w['sp_edge_scale'].config(state=st)
    w['sp_lce_scale'].config(state=st)
    w['ck_lce_scale'].config(state=st)
    w['sp_lce_level'].config(state=st)
    w['ck_lce_level'].config(state=st)


  def ui_ck_curvature_changed(self):
    w = self.widgets
    st = tk.NORMAL
    if w['ck_curvature'].var.get() == False:
      st = tk.DISABLED

    w['sp_curvature'].config(state=st)
    w['ck_curvature_pc'].config(state=st)


  def ui_ck_output_size_changed(self):
    w = self.widgets
    st = tk.NORMAL
    if w['ck_output_size'].var.get() == False:
      st = tk.DISABLED

    w['en_output_w'].config(state=st)
    w['en_output_h'].config(state=st)
    w['en_output_xoffset'].config(state=st)
    w['en_output_yoffset'].config(state=st)


  def ui_cb_file_format_changed(self, event):
    w = self.widgets
    if w['cb_file_format'].get() == 'TIFF':
      w['fr_jpg_options'].grid_remove()
      w['fr_tif_options'].grid()
    else:
      w['fr_jpg_options'].grid()
      w['fr_tif_options'].grid_remove()

    w['cb_file_format'].selection_clear()


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
    c = self.config

    if os.path.isfile('config.ini'):
      c.read('config.ini')

    c['DEFAULT'] = {
      'ck_align'                : 'True',
      'ck_autocrop'             : 'True',
      'ck_centershift'          : 'True',
      'ck_fov'                  : 'True',
      'sp_corr_threshold'       : '0.9',
      'sp_control_points'       : '10',
      'sp_grid_size'            : '5',
      'sp_scale_factor'         : '1',
      'ck_hard_mask'            : 'True',
      'sp_levels'               : '29',
      'ck_levels'               : 'True',
      'sp_window_size'          : '5',
      'ck_edge_scale'           : 'False',
      'sp_edge_scale'           : '0',
      'sp_lce_scale'            : '0',
      'ck_lce_scale'            : 'False',
      'sp_lce_level'            : '0',
      'ck_lce_level'            : 'False',
      'ck_curvature'            : 'False',
      'sp_curvature'            : '0',
      'ck_curvature_pc'         : 'False',
      'cb_gray_proj'            : 'l-star',
      'en_preview_w'            : '640',
      'en_preview_h'            : '640',
      'ck_output_size'          : 'False',
      'en_output_w'             : '0',
      'en_output_h'             : '0',
      'en_output_xoffset'       : '0',
      'en_output_yoffset'       : '0',
      'cb_file_format'          : 'JPG',
      'sp_jpg_quality'          : '90',
      'cb_tif_compression'      : 'lzw'
    }

    if not c.has_section('prefs'):
      c.add_section('prefs')

    if not c.has_section('widgets'):
      c.add_section('widgets')


  def apply_config(self):
    # ==== Apply saved/default values to widgets from config ====
    w = self.widgets
    wc = self.config['widgets']

    for w_name in w:
      w_value = wc.get(w_name)

      if not w_value or not hasattr(w[w_name], 'var'):
        continue

      w_class = w[w_name].winfo_class()

      if w_class == 'TCheckbutton':
        # reverse the boolean here to workaround invoke() below
        if w_value == 'True':
          w[w_name].var.set(False)
        else:
          w[w_name].var.set(True)
        w[w_name].invoke()
      elif w_class == 'TCombobox':
        w[w_name].var.set(w_value)
        w[w_name].event_generate('<<ComboboxSelected>>', when='tail')
      else:
        w[w_name].var.set(w_value)


  def save_configs(self):
    # read the current values of the widgets
    w = self.widgets
    wc = self.config['widgets']

    for w_name in w:
      #w_class = w[w_name].winfo_class()
      if hasattr(w[w_name], 'var'):
        wc[w_name] = str(w[w_name].var.get())


    with open('config.ini', 'w') as configfile:
      self.config.write(configfile)



  def on_closing(self):
    try:
      self.save_configs()
    except Exception as e:
      print(e)

    self.destroy()





if __name__ == "__main__":
  app = App()
  app.mainloop()