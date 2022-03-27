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
import tempfile
import subprocess
import threading
import collections
import copy
import math

class App(tk.Tk):


  def __init__(self):
    super().__init__()

    # instance variables
    self.input_images = [] # list of filenames
    self.widgets = {}      # list of widgets
    self.config  = {}      # configurations
    self.flags   = {       # various flags used internally
      'tr_mask_clicked'   : False
    }
    self.masks   = {}      # storage for masks, indexed by filepaths
    self.new_mask = None   # keep track of the mask being created
    self.mask_clipboard = []  # clipboard for copying/pasting masks

    self.preview_cache = {
      'slots' : [None] * 5,
      'head'   : 0,
      'width'  : -1,
      'height' : -1
    }

    self.mask_preview_cache = {
      'slots' : [None] * 5,
      'head'   : 0,
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
    style.configure('TRadiobutton', background='#f8f8f8')
    style.configure('TLabel', background='#f8f8f8')
    style.configure('TSpinbox', arrowsize=17)
    style.configure('TCombobox', arrowsize=17, fieldbackground='#f8f8f8')
    style.map('TCombobox', fieldbackground=[('readonly', '#f8f8f8')])

    default_font = tk.font.nametofont('TkDefaultFont')
    default_font.configure(size=11)

    container = ttk.Frame(self)
    container.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)


    # create 3 tabs
    nb = ttk.Notebook(container)
    nb.grid(column=0, row=0, columnspan=3, sticky=(tk.N, tk.W, tk.E, tk.S))
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


    # add top-level buttons
    ttk.Button(container, text='Preferences').grid(column=2, row=0, sticky=(tk.E, tk.N), padx=10)


    w = self.widgets # shorthand
    w['nb'] = nb



    # ==== set up images/files tab ====
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
    w['lb_images'] = tk.Listbox(fr_images, selectmode=tk.EXTENDED)
    w['lb_images'].grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    w['lb_images'].bind('<<ListboxSelect>>', self.ui_lb_images_selected)

    # scrollbar for image list
    s = ttk.Scrollbar(fr_images, orient=tk.VERTICAL, command=w['lb_images'].yview)
    s.grid(column=1, row=0, sticky=(tk.NS))
    w['lb_images']['yscrollcommand'] = s.set

    # preview pane
    w['cv_image_preview'] = tk.Canvas(pn_tabimages, background='#eeeeee')
    w['cv_image_preview'].grid(column=1, row=0, sticky=(tk.NS, tk.EW))
    w['cv_image_preview'].bind('<Configure>', lambda x: self.update_input_image_preview())
    pn_tabimages.add(w['cv_image_preview'], weight=3)

    fr_image_actions = ttk.Frame(tab_images)
    fr_image_actions.grid(column=0, row=1, sticky=(tk.S, tk.EW))

    w['bt_image_add'] = ttk.Button(fr_image_actions, text='Add images', command=self.add_images)
    w['bt_image_add'].grid(column=0, row=0, padx=10, pady=10, ipadx=3)

    w['bt_image_remove'] = ttk.Button(fr_image_actions, text='Remove selected', command=self.remove_images)
    w['bt_image_remove'].grid(column=1, row=0, padx=10, pady=10, ipadx=3)




    # ==== set up Masks tab ====
    pn_tabmasks = ttk.PanedWindow(tab_masks, orient=tk.HORIZONTAL)

    pn_tabmasks.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_masks.columnconfigure(0, weight=1)
    tab_masks.rowconfigure(0, weight=1)

    # divide the left pane into two above/below panes (images and masks)
    pn_tabmasks_left = ttk.PanedWindow(pn_tabmasks, orient=tk.VERTICAL)
    pn_tabmasks.add(pn_tabmasks_left, weight=0)

    fr_mask_images = ttk.Frame(pn_tabmasks_left)
    fr_mask_images.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    pn_tabmasks_left.add(fr_mask_images, weight=1)

    fr_mask_images.columnconfigure(0, weight=1)
    fr_mask_images.rowconfigure(0, weight=1)

    # image/mask tree
    w['tr_mask_images'] = ttk.Treeview(fr_mask_images, selectmode=tk.EXTENDED,
                                       columns=('include', 'exclude'))
    w['tr_mask_images'].column('include', width=30, anchor=tk.CENTER)
    w['tr_mask_images'].heading('include', text='Include')
    w['tr_mask_images'].column('exclude', width=30, anchor=tk.CENTER)
    w['tr_mask_images'].heading('exclude', text='Exclude')

    w['tr_mask_images'].grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    w['tr_mask_images'].bind('<<TreeviewSelect>>', self.ui_tr_mask_images_selected)

    # scrollbar for image/mask tree
    s = ttk.Scrollbar(fr_mask_images, orient=tk.VERTICAL, command=w['tr_mask_images'].yview)
    s.grid(column=1, row=0, sticky=(tk.NS))
    w['tr_mask_images']['yscrollcommand'] = s.set


    # lower pane for masks
    fr_masks = ttk.Frame(pn_tabmasks_left)
    fr_masks.grid(column=0, row=1, sticky=(tk.NS, tk.EW))
    pn_tabmasks_left.add(fr_masks, weight=1)

    fr_masks.columnconfigure(0, weight=1)
    fr_masks.rowconfigure(1, weight=1)

    # mask actions/buttons
    fr_mask_image_actions = ttk.Frame(fr_masks)
    fr_mask_image_actions.grid(column=0, row=0, columnspan=2, sticky=(tk.S, tk.EW))

    w['bt_mask_add'] = ttk.Button(fr_mask_image_actions, text='Add mask', command=self.add_mask)
    w['bt_mask_add'].grid(column=0, row=0, padx=5, pady=5, ipadx=3)

    v_sp_mask_add_type = tk.StringVar()
    w['sp_mask_add_type'] = ttk.Spinbox(fr_mask_image_actions, values=('include', 'exclude'), justify=tk.CENTER,
                                        wrap=True, textvariable=v_sp_mask_add_type, width=8, state='readonly')
    w['sp_mask_add_type'].grid(column=1, row=0)
    w['sp_mask_add_type'].var = v_sp_mask_add_type
    w['sp_mask_add_type'].bind('<Button-1>', self.ui_sp_mask_add_type_b1)

    w['bt_mask_paste'] = ttk.Button(fr_mask_image_actions, text='Paste', command=self.paste_masks)
    w['bt_mask_paste'].grid(column=2, row=0, padx=10, pady=5, ipadx=3)

    w['bt_mask_clear'] = ttk.Button(fr_mask_image_actions, text='Clear', command=self.clear_masks)
    w['bt_mask_clear'].grid(column=3, row=0, padx=0, pady=5, ipadx=3)


    # mask lists of selected image
    w['tr_masks'] = ttk.Treeview(fr_masks, selectmode=tk.EXTENDED, columns=('type'))
    w['tr_masks'].column('type', width=150, anchor=tk.CENTER)
    w['tr_masks'].heading('type', text='Mask type')

    w['tr_masks'].grid(column=0, row=1, sticky=(tk.NS, tk.EW))
    w['tr_masks'].bind('<<TreeviewSelect>>', self.ui_tr_masks_selected)

    # scrollbar for mask list
    s = ttk.Scrollbar(fr_masks, orient=tk.VERTICAL, command=w['tr_masks'].yview)
    s.grid(column=1, row=1, sticky=(tk.NS))
    w['tr_masks']['yscrollcommand'] = s.set
    w['tr_masks'].scroll = s

    # mask actions: Include, Exclude, Delete, Copy
    fr_mask_actions = ttk.Frame(fr_masks)
    fr_mask_actions.grid(column=0, row=2, columnspan=2, sticky=(tk.EW, tk.S))

    w['bt_mask_include'] = ttk.Button(fr_mask_actions, text='Include', command=self.set_masks_include)
    w['bt_mask_include'].grid(column=0, row=0, padx=5, pady=5, ipadx=3)

    w['bt_mask_exclude'] = ttk.Button(fr_mask_actions, text='Exclude', command=self.set_masks_exclude)
    w['bt_mask_exclude'].grid(column=1, row=0, padx=5, pady=5, ipadx=3)

    w['bt_mask_delete'] = ttk.Button(fr_mask_actions, text='Delete', command=self.delete_masks)
    w['bt_mask_delete'].grid(column=2, row=0, padx=5, pady=5, ipadx=3)

    w['bt_mask_copy'] = ttk.Button(fr_mask_actions, text='Copy', command=self.copy_masks)
    w['bt_mask_copy'].grid(column=3, row=0, padx=5, pady=5, ipadx=3)


    # canvas to draw masks
    w['cv_image_masks'] = tk.Canvas(pn_tabmasks, background='#eeeeee')
    w['cv_image_masks'].grid(column=1, row=0, sticky=(tk.NS, tk.EW))
    w['cv_image_masks'].old_width  = w['cv_image_masks'].winfo_width()
    w['cv_image_masks'].old_height = w['cv_image_masks'].winfo_height()

    w['cv_image_masks'].bind('<Configure>', lambda x: self.update_mask_canvas())
    w['cv_image_masks'].bind('<Motion>', self.ui_cv_image_masks_motion)
    w['cv_image_masks'].bind('<Button-1>', self.ui_cv_image_masks_b1)
    w['cv_image_masks'].bind('<Double-Button-1>', self.end_new_mask)
    self.bind('<Return>', self.end_new_mask)

    pn_tabmasks.add(w['cv_image_masks'], weight=2)




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
    ttk.Label(fr_stack_align, text='Correlation threshold: ').grid(column=0, row=2, sticky=(tk.E), padx=20, pady=10)

    v_sp_corr_threshold = tk.StringVar()
    w['sp_corr_threshold'] = ttk.Spinbox(fr_stack_align, from_=0.0, to=1.0, increment=0.1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_corr_threshold)
    w['sp_corr_threshold'].grid(column=1, row=2, sticky=(tk.W), padx=20, pady=10)
    w['sp_corr_threshold'].var = v_sp_corr_threshold

    # error threshold
    ttk.Label(fr_stack_align, text='Error threshold: ').grid(column=0, row=3, sticky=(tk.E), padx=20, pady=10)

    v_sp_error_threshold = tk.StringVar()
    w['sp_error_threshold'] = ttk.Spinbox(fr_stack_align, from_=1, to=20, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_error_threshold)
    w['sp_error_threshold'].grid(column=1, row=3, sticky=(tk.W), padx=20, pady=10)
    w['sp_error_threshold'].var = v_sp_error_threshold


    # control points
    ttk.Label(fr_stack_align, text='Number of control points: ').grid(column=0, row=4, sticky=(tk.E), padx=20, pady=7)

    v_sp_control_points = tk.IntVar()
    w['sp_control_points'] = ttk.Spinbox(fr_stack_align, from_=0, to=50, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_control_points)
    w['sp_control_points'].grid(column=1, row=4, sticky=(tk.W), padx=20, pady=7)
    w['sp_control_points'].var = v_sp_control_points

    # grid size
    ttk.Label(fr_stack_align, text='Grid size: ').grid(column=0, row=5, sticky=(tk.E), padx=20, pady=7)

    v_sp_grid_size = tk.IntVar()
    w['sp_grid_size'] = ttk.Spinbox(fr_stack_align, from_=1, to=10, increment=1,
                                    justify=tk.CENTER, width=10, textvariable=v_sp_grid_size)
    w['sp_grid_size'].grid(column=1, row=5, sticky=(tk.W), padx=20, pady=7)
    w['sp_grid_size'].var = v_sp_grid_size

    # scale factor
    ttk.Label(fr_stack_align, text='Scale factor: ').grid(column=0, row=6, sticky=(tk.E), padx=20, pady=7)

    v_sp_scale_factor = tk.IntVar()
    w['sp_scale_factor'] = ttk.Spinbox(fr_stack_align, from_=1, to=5, increment=1,
                                       justify=tk.CENTER, width=10, textvariable=v_sp_scale_factor)
    w['sp_scale_factor'].grid(column=1, row=6, sticky=(tk.W), padx=20, pady=7)
    w['sp_scale_factor'].var = v_sp_scale_factor

    ttk.Frame(fr_stack_align).grid(column=0, row=7, pady=5)  # padding bottom


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

    w['bt_stack'] = ttk.Button(fr_stack_actions, text='Stack', command=self.stack_images)
    w['bt_stack'].grid(column=0, row=0)

    ttk.Button(fr_stack_actions, text='Toggle log', command=self.toggle_log).grid(column=1, row=0, sticky=(tk.E))



    # stacked preview pane
    w['cv_stacked_preview'] = tk.Canvas(tab_stack, background='#eeeeee')
    w['cv_stacked_preview'].grid(column=1, row=0, rowspan=6, sticky=(tk.NS, tk.EW), padx=(4,0))
    w['cv_stacked_preview'].bind("<Configure>", lambda x: self.update_output_image_preview())
    w['cv_stacked_preview'].grid_remove()


    # textbox to print log to
    w['tx_log'] = tk.Text(tab_stack, width=50, height=40, borderwidth=5, relief=tk.FLAT)
    w['tx_log'].grid(column=1, row=0, rowspan=6, sticky=(tk.NS, tk.EW), padx=(4, 0))

    # scrollbar for log text
    s = ttk.Scrollbar(tab_stack, orient=tk.VERTICAL, command=w['tx_log'].yview)
    s.grid(column=2, row=0, rowspan=6, sticky=(tk.NS))
    w['tx_log']['yscrollcommand'] = s.set
    w['tx_log'].scroll = s


    # apply configs to all widgets
    self.apply_config()

    # additional initial setup
    w['bt_image_remove'].configure(state=tk.DISABLED)

    w['bt_mask_add'].configure(state=tk.DISABLED)
    w['bt_mask_clear'].configure(state=tk.DISABLED)
    w['bt_mask_paste'].configure(state=tk.DISABLED)

    w['bt_mask_include'].configure(state=tk.DISABLED)
    w['bt_mask_exclude'].configure(state=tk.DISABLED)
    w['bt_mask_delete'].configure(state=tk.DISABLED)
    w['bt_mask_copy'].configure(state=tk.DISABLED)





  # ==== Event handlers for widgets ====

  def ui_lb_images_selected(self, event):
    if len(self.widgets['lb_images'].curselection()) > 0:
      self.widgets['bt_image_remove'].configure(state=tk.NORMAL)
    self.update_input_image_preview()



  def ui_tr_mask_images_selected(self, event):
    w = self.widgets

    if len(w['tr_mask_images'].selection()) > 0:
      w['bt_mask_add'].configure(state=tk.NORMAL)
      w['bt_mask_clear'].configure(state=tk.NORMAL)

    self.new_mask = None

    self.update_mask_canvas()
    self.update_mask_list()

  def ui_sp_mask_add_type_b1(self, event):
    sp = self.widgets['sp_mask_add_type']

    if sp.var.get() == 'include':
      sp.var.set('exclude')
    else:
      sp.var.set('include')


  def ui_tr_masks_selected(self, event):
    w = self.widgets

    if len(w['tr_masks'].selection()) > 0:
      w['bt_mask_include'].configure(state=tk.NORMAL)
      w['bt_mask_exclude'].configure(state=tk.NORMAL)
      w['bt_mask_delete'].configure(state=tk.NORMAL)
      w['bt_mask_copy'].configure(state=tk.NORMAL)



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


  def toggle_log(self, show = None):
    w = self.widgets

    if show == None:
      show = not w['tx_log'].winfo_ismapped()

    if show:
      w['tx_log'].grid()
      w['tx_log'].scroll.grid()
      w['cv_stacked_preview'].grid_remove()
    else:
      w['tx_log'].grid_remove()
      w['tx_log'].scroll.grid_remove()
      w['cv_stacked_preview'].grid()


  def add_images(self):
    w = self.widgets
    c = self.config
    initial_dir = '~'

    if 'prefs' in c and 'last_opened_location' in c['prefs']:
      initial_dir = c['prefs']['last_opened_location']

    filepaths = tk.filedialog.askopenfilenames(title='Add images', initialdir=initial_dir, filetypes=[
              ('image', '.jpg'),
              ('image', '.jpeg'),
              ('image', '.png'),
              ('image', '.tif'),
              ('image', '.tiff')
            ])

    if len(filepaths) == 0:
      return

    # save the current location
    c.set('prefs', 'last_opened_location', os.path.dirname(filepaths[0]))

    # update the image list in Images and Stacks tabs
    for filepath in filepaths:
      filename = os.path.basename(filepath)

      w['lb_images'].insert(tk.END, ' ' + filename)
      self.input_images.append(filepath)

      w['tr_mask_images'].insert('', tk.END, filepath, text=filename)


  def remove_images(self):
    w = self.widgets
    selection = w['lb_images'].curselection()

    for i in reversed(selection):
      filepath = self.input_images.pop(i)
      w['lb_images'].delete(i)
      w['tr_mask_images'].delete(filepath)

    w['bt_image_remove'].configure(state=tk.DISABLED)

    # clear the image and mask preview
    self.update_input_image_preview()


  def get_current_input_image(self):
    """ helper to get the currently selected input image.
    Return None if no image or multiple images selected """
    selection = self.widgets['lb_images'].curselection()

    if len(selection) != 1:
      return None

    return selection[0]



  def update_input_image_preview(self):
    """ update the preview with the specified image at index """
    cv = self.widgets['cv_image_preview']

    selection = self.widgets['lb_images'].curselection()

    if len(selection) != 1:
      cv.delete(tk.ALL)
      return

    index = selection[0]

    width = cv.winfo_width()
    height = cv.winfo_height()

    # if size changed, clear buffer
    hit = False
    cache = self.preview_cache

    if cache['width'] != width or cache['height'] != height:
      cache['slots'] = [None] * len(cache['slots'])
      cache['width'] = width
      cache['height'] = height
    else:
      # check buffer
      for item in cache['slots']:
        if item and item['filename'] == self.input_images[index]:
          img = item['img']
          hit = True
          break

    if hit == False:
      img = Image.open(self.input_images[index])
      img.thumbnail((width, height), Image.LANCZOS)
      img = ImageTk.PhotoImage(img)

      buffer_slot = cache['head'] % len(cache['slots'])
      cache['slots'][buffer_slot] = {
        'filename' : self.input_images[index],
        'img'      : img
      }
      cache['head'] = (cache['head']+1) % len(cache['slots'])

    cv.create_image(width/2, height/2, anchor=tk.CENTER, image=img)
    cv.image = img


  def get_current_mask_image(self):
    """ return the image_id/filepath of the currently selected image in Masks tab
        return None if no image or multiple images selected """
    selection = self.widgets['tr_mask_images'].selection()

    if len(selection) != 1:
      return None

    return selection[0]



  def add_mask(self):
    self.new_mask = []

    # add a place holder for cv.new_mask
    cv = self.widgets['cv_image_masks']
    cv.new_mask = cv.create_line(0, 0, 0, 0, fill='')

    self.widgets['bt_mask_add'].configure(state=tk.DISABLED)


  def copy_masks(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    image_id = self.get_current_mask_image()
    if image_id == None:
      return

    # clear clipboard
    self.mask_clipboard.clear()

    for mask_index in selection:
      self.mask_clipboard.append(copy.deepcopy(self.masks[image_id][int(mask_index)-1]))

    # make the Paste button available
    w['bt_mask_paste'].configure(state=tk.NORMAL)


  def paste_masks(self):
    w = self.widgets

    if len(self.mask_clipboard) == 0:
      tk.messagebox.showinfo('Mask clipboard is empty.')
      w['bt_mask_paste'].configure(state=tk.DISABLED)
      return

    selection = self.widgets['tr_mask_images'].selection()

    for image_id in selection:
      if image_id not in self.masks:
        self.masks[image_id] = []

      old_mask_count = len(self.masks[image_id])
      for mask in self.mask_clipboard:
        # avoid duplicate masks
        has_duplicate = False
        for i in range(old_mask_count):
          old_mask = self.masks[image_id][i]
          if collections.Counter(old_mask['mask']) == collections.Counter(mask['mask']):
            old_mask['type'] = mask['type'] # update existing mask
            has_duplicate = True
            break

        if has_duplicate == False:
          self.masks[image_id].append(copy.deepcopy(mask))

    self.update_mask_list()
    self.update_mask_canvas()



  def clear_masks(self):
    selection = self.widgets['tr_mask_images'].selection()

    for image_id in selection:
      if image_id in self.masks:
        del self.masks[image_id]

    self.update_mask_list()
    self.update_mask_canvas()


  def delete_masks(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    image_id = self.get_current_mask_image()
    if image_id == None:
      return

    for mask_index in reversed(selection):
      self.masks[image_id].pop(int(mask_index)-1)

    self.update_mask_list()
    self.update_mask_canvas()


  def set_masks_include(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    image_id = self.get_current_mask_image()
    if image_id == None:
      return

    for mask_index in selection:
      mask = self.masks[image_id][int(mask_index)-1]
      mask['type'] = 'include'

    self.update_mask_list()
    self.update_mask_canvas()


  def set_masks_exclude(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    image_id = self.get_current_mask_image()
    if image_id == None:
      return

    for mask_index in selection:
      mask = self.masks[image_id][int(mask_index)-1]
      mask['type'] = 'exclude'

    self.update_mask_list()
    self.update_mask_canvas()


  def ui_cv_image_masks_b1(self, event):
    cv = self.widgets['cv_image_masks']

    # handle mask creation
    if self.new_mask != None:
      self.new_mask = self.new_mask + [event.x, event.y]
      cv.delete(cv.new_mask)
      cv.new_mask = cv.create_polygon(self.new_mask + [event.x, event.y], fill='', outline='#ffffff')


  def ui_cv_image_masks_motion(self, event):
    if self.new_mask != None and len(self.new_mask) > 0:
      cv = self.widgets['cv_image_masks']

      if len(self.new_mask) == 2:
        cv.delete(cv.new_mask)
        cv.new_mask = cv.create_line(self.new_mask + [event.x, event.y], fill='#ffffff')
      else:
        cv.delete(cv.new_mask)
        cv.new_mask = cv.create_polygon(self.new_mask + [event.x, event.y], fill='', outline='#ffffff')



  def end_new_mask(self, event):
    """ user double-clicked on canvas ==> finish creating the new mask """
    w = self.widgets
    cv = w['cv_image_masks']

    if self.new_mask == None:
      return

    image_id = self.get_current_mask_image()

    if image_id == None or len(self.new_mask) < 6:
      self.new_mask = None
      w['bt_mask_add'].configure(state=tk.NORMAL)
      cv.delete(cv.new_mask)
      return

    if image_id not in self.masks:
      self.masks[image_id] = []


    # map/scale the mask to full image width
    mask = []

    for i in range(math.floor(len(self.new_mask)/2)):
      mask.append((self.new_mask[2*i] - cv.origin[0])/cv.image_scale)
      mask.append((self.new_mask[2*i+1] - cv.origin[1])/cv.image_scale)

    self.masks[image_id].append({
      'mask': mask,
      'type': w['sp_mask_add_type'].var.get()
    })

    self.new_mask = None
    cv.new_mask = None

    w['bt_mask_add'].configure(state=tk.NORMAL)
    self.update_mask_canvas()
    self.update_mask_list()


  def update_mask_image_list(self):
    tr = self.widgets['tr_mask_images']

    for image_id in tr.get_children():
      include = 0
      exclude = 0

      if image_id in self.masks:

        for mask in self.masks[image_id]:
          if mask['type'] == 'include':
            include = include + 1
          else:
            exclude = exclude + 1

      include = '' if include == 0 else include
      exclude = '' if exclude == 0 else exclude

      tr.set(image_id, 'include', include)
      tr.set(image_id, 'exclude', exclude)



  def update_mask_canvas(self):
    """ update the mask canvas with the specified item_id/filepath """
    cv = self.widgets['cv_image_masks']
    cv.delete(tk.ALL)

    image_id = self.get_current_mask_image()
    if image_id == None:
      return

    width = cv.winfo_width()
    height = cv.winfo_height()

    # if size changed, clear buffer
    hit = False
    cache = self.mask_preview_cache

    if cv.old_width != width or cv.old_height != height:
      # clear cache
      cache['slots'] = [None] * len(cache['slots'])
      cv.old_width  = width
      cv.old_height = height
    else:
      # check buffer
      for item in cache['slots']:
        if item and item['filename'] == image_id:
          tkimg = item['img']
          hit = True
          break

    if hit == False:
      img = Image.open(image_id)
      img_full_width = img.width

      img.thumbnail((width, height), Image.LANCZOS)
      cv.image_scale = img.width/img_full_width

      tkimg = ImageTk.PhotoImage(img)

      buffer_slot = cache['head'] % len(cache['slots'])
      cache['slots'][buffer_slot] = {
        'filename' : image_id,
        'img'      : tkimg
      }
      cache['head'] = (cache['head']+1) % len(cache['slots'])

    cv_image = cv.create_image(width/2, height/2, anchor=tk.CENTER, image=tkimg)
    cv.image = tkimg

    # calculate the image top-left corner
    img_center = cv.coords(cv_image)
    cv.origin = (img_center[0] - tkimg.width()/2, img_center[1] - tkimg.height()/2)

    # add the masks of the image
    if self.new_mask != None:
      cv.new_mask = cv.create_polygon(self.new_mask, fill='', outline='#ffffff')

    # add the existing masks of the current image
    if image_id in self.masks:
      self.draw_masks(self.masks[image_id], cv.origin, cv.image_scale)



  def draw_masks(self, masks, origin, scale):
    """ helper to add a list of masks on the canvas """
    cv = self.widgets['cv_image_masks']

    #print(self.masks[self.current_mask_image])
    cv.masks = []
    for mask in masks:
      mask_color = self.config.get('prefs', 'mask_include_color')
      if mask['type'] == 'exclude':
        mask_color = self.config.get('prefs', 'mask_exclude_color')

      cv.masks.append(
        cv.create_polygon(self.scale_polygon(mask['mask'], cv.origin, scale),
                          fill='', outline=mask_color))



  def update_mask_list(self):
    w = self.widgets
    tr = w['tr_masks']

    # save the current selection
    old_len = len(tr.get_children())
    selection = tr.selection()

    for item in tr.get_children():
      tr.delete(item)

    self.update_mask_image_list()

    image_id = self.get_current_mask_image()

    if image_id != None:
      # add all the masks
      if image_id in self.masks:
        for i, mask in enumerate(self.masks[image_id]):
          tr.insert('', tk.END, i+1, text='# ' + str(i+1), values=(mask['type']))

      if old_len > 0 and old_len == len(tr.get_children()):
        tr.selection_set(selection)

    new_state = tk.DISABLED
    if len(tr.selection()) > 0:
      new_state = tk.NORMAL

    w['bt_mask_include'].configure(state=new_state)
    w['bt_mask_exclude'].configure(state=new_state)
    w['bt_mask_delete'].configure(state=new_state)
    w['bt_mask_copy'].configure(state=new_state)



  def scale_polygon(self, poly, new_origin, scale) :
    p = []

    for i in range(math.floor(len(poly)/2)):
      p.append(poly[2*i]*scale + new_origin[0])
      p.append(poly[2*i+1]*scale + new_origin[1])

    return p


  def update_output_image_preview(self):
    if len(self.input_images) == 0:
      return

    cv = self.widgets['cv_stacked_preview']
    width = cv.winfo_width()
    height = cv.winfo_height()

    output_file = os.path.join(
      os.path.basename(self.input_images[0]),
      self.output_name
    )

    img = Image.open(output_file)
    img.thumbnail((width, height), Image.LANCZOS)
    img = ImageTk.PhotoImage(img)

    cv.create_image(width/2, height/2, anchor=tk.CENTER, image=img)
    cv.image = img


  def load_config(self):
    self.config = configparser.ConfigParser()
    c = self.config

    if os.path.isfile('config.ini'):
      c.read('config.ini')

    c['DEFAULT'] = {
      'rb_mask_type_include'    : 'include',
      'ck_align'                : 'True',
      'ck_autocrop'             : 'True',
      'ck_centershift'          : 'True',
      'ck_fov'                  : 'True',
      'sp_corr_threshold'       : '0.9',
      'sp_error_threshold'      : '3',
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
      'cb_tif_compression'      : 'lzw',

      'align_prefix'            : 'aligned__',
      'mask_include_color'      : '#55ff55',
      'mask_exclude_color'      : '#5555ff'
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


  def build_align_command(self):
    cmd = ['align_image_stack', '-v', '-aaligned__', '--use-given-order']

    # get the alignment options
    w = self.widgets

    if w['ck_autocrop'].var.get():
      cmd.append('-C')

    if w['ck_centershift'].var.get():
      cmd.append('-i')

    if w['ck_fov'].var.get():
      cmd.append('-m')

    cmd.append('--corr=' + str(w['sp_corr_threshold'].var.get()))
    cmd.append('-t ' + str(w['sp_error_threshold'].var.get()))
    cmd.append('-c ' + str(w['sp_control_points'].var.get()))
    cmd.append('-g ' + str(w['sp_grid_size'].var.get()))
    cmd.append('-s ' + str(w['sp_scale_factor'].var.get()))

    cmd = cmd + self.input_images
    return cmd


  def build_enfuse_command(self):
    cmd = ['enfuse', '-v', '-o', self.output_name,
           '--exposure-weight=0',
           '--saturation-weight=0',
           '--contrast-weight=1']

    w = self.widgets

    if w['ck_hard_mask'].var.get():
      cmd.append('--hard-mask')

    if not w['ck_levels'].var.get():
      cmd.append('--levels=' + str(w['sp_levels'].var.get()))

    if w['ck_edge_scale'].var.get():
      opt = str(w['sp_edge_scale'].var.get()) + ':'
      opt = opt + str(w['sp_lce_scale'].var.get()) + '%' if w['ck_lce_scale'].var.get() else ''
      opt = opt + ':' + str(w['sp_lce_level'].var.get()) + '%' if w['ck_lce_level'].var.get() else ''
      cmd.append('--contrast-edge-scale=' + opt)

    if w['ck_curvature'].var.get():
      cmd.append('--contrast-min-curvature=' + str(w['sp_curvature'].var.get()) +
                 '%' if w['ck_curvature_pc'].var.get() else '')

    cmd.append('--gray-projector=' + str(w['cb_gray_proj'].var.get()))
    cmd.append('--contrast-window-size=' + str(w['sp_window_size'].var.get()))

    if w['cb_file_format'].var.get() == 'JPG':
      cmd.append('--compression=' + str(w['sp_jpg_quality'].var.get()))
    else:
      cmd.append('--compression=' + str(w['cb_tif_compression'].var.get()))

    if w['ck_align'].var.get():
      cmd = cmd + self.aligned_images
    else:
      cmd = cmd + self.input_images

    return cmd


  def stack_images(self):
    """ perform optional alignment and fusing the images """
    w = self.widgets

    # check if we have at least 2 images
    if len(self.input_images) < 2:
      tk.messagebox.showinfo(message='Please add at least two images.')
      w['nb'].select(0)
      return

    extension = '.jpg' if w['cb_file_format'].var.get() == 'JPG' else '.tif'
    default_filename = os.path.splitext(os.path.basename(self.input_images[0]))[0] + '_fused' + extension

    self.output_name = tk.filedialog.asksaveasfilename(
      initialdir=self.config['prefs']['last_opened_location'],
      confirmoverwrite=True,
      defaultextension=extension,
      initialfile=default_filename
    )

    if not self.output_name:
      return

    w['tx_log'].delete(1.0, tk.END)
    self.toggle_log(True)

    self.returncode = tk.IntVar()

    if w['ck_align'].var.get():
      self.aligned_images = []

      for i, image in enumerate(self.input_images):
        self.aligned_images.append(os.path.join(
          os.path.dirname(image),
          self.config.get('prefs', 'align_prefix') + '{:04d}'.format(i) + '.tif'))

      align_cmd = self.build_align_command()
      print(align_cmd)

      self.returncode.set(-1)
      threading.Thread(target=self.execute_cmd, args=[align_cmd], daemon=True).start()
      self.wait_variable(self.returncode)

      if self.returncode.get() > 0:
        tk.messagebox.showerror(message='Error aligning images, please check output log.')
        return


    enfuse_cmd = self.build_enfuse_command()
    print(enfuse_cmd)

    w['tx_log'].insert(tk.END, '\n\n===== CALLING ENFUSE =====\n')
    w['tx_log'].insert(tk.END, 'output to ' + self.output_name + '\n\n')

    self.returncode.set(-1)
    threading.Thread(target=self.execute_cmd, args=[enfuse_cmd], daemon=True).start()
    self.wait_variable(self.returncode)

    if self.returncode.get() > 0:
      tk.messagebox.showerror(message='Error stacking images, please check output log.')
      return

    w['tx_log'].insert(tk.END, '\nDone stacking to ' + self.output_name + '\n\n')
    w['tx_log'].see(tk.END)

    # load the output file into the result pane
    self.update_output_image_preview()
    self.toggle_log(False)

    # clean up aligned TIFFs
    if w['ck_align'].var.get():
      for filename in self.aligned_images:
        os.remove(filename)



  def execute_cmd(self, cmd):
    log_box = self.widgets['tx_log']
    working_dir = os.path.dirname(self.input_images[0])

    p = subprocess.Popen(cmd, cwd=working_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    while p.poll() is None:
      msg = p.stdout.readline()
      log_box.insert(tk.END, msg)
      log_box.see(tk.END)

    self.returncode.set(p.returncode)



if __name__ == "__main__":
  app = App()
  app.mainloop()