#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# License : GPLv3 : http://gplv3.fsf.org/


import tkinter as tk
import tkinter.filedialog
import tkinter.font
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
from tkinterdnd2 import DND_FILES, TkinterDnD
from cv2 import cv2
import numpy as np
import multiprocessing as mp

import timeit


import os
import platform
from shutil import which
import configparser
import subprocess
import threading
import collections
import copy
import math
import json

class App(TkinterDnD.Tk):


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

    self.output_image = None
    self.save_file    = None

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

    self.thread = None
    self.subprocess = None
    self.opencv_aligner = None

    self.load_config()

    self.title('MFTker')
    self.minsize(800, 600)
    self.resizable(True, True)

    # self.geometry('1500x800')
    # use all screen size
    self.geometry("%dx%d+0+0" % (self.winfo_screenwidth(), self.winfo_screenheight()))


    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)

    self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # set up font and style
    style = ttk.Style()
    style.theme_use('default')
    style.configure('TNotebook.Tab', padding=[40, 5])
    style.configure('TFrame', background='#f8f8f8')
    style.configure('TLabelframe', background='#f8f8f8', labelmargins=(10, 5, 0, 0),
                    borderwidth=2, bordercolor='#cccccc', padding=0)
    style.configure('TLabelframe.Label', background='#f8f8f8')
    style.configure('Treeview', rowheight=25)
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
    tab_prefs  = ttk.Frame(nb)

    tab_images.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_masks.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_stack.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    tab_prefs.grid(column=0, row=0, sticky=(tk.NS, tk.EW))

    nb.add(tab_images, text='Images')
    nb.add(tab_masks, text='Masks')
    nb.add(tab_stack, text='Stack')
    nb.add(tab_prefs, text='Preferences')


    # add top-level buttons
    ttk.Button(container, text='Load', command=self.load_project) \
       .grid(column=1, row=0, sticky=(tk.E, tk.N), padx=(0, 10))
    ttk.Button(container, text='Save', command=self.save_project) \
       .grid(column=2, row=0, sticky=(tk.E, tk.N), padx=(0,10))


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
    w['tr_images'] = ttk.Treeview(fr_images, selectmode=tk.EXTENDED)
    w['tr_images'].grid(column=0, row=0, sticky=(tk.NS, tk.EW))
    w['tr_images'].bind('<<TreeviewSelect>>', self.ui_tr_images_selected)
    self.drop_target_register(DND_FILES)
    self.dnd_bind('<<Drop>>', self.add_images_from_drop)

    # scrollbar for image list
    s = ttk.Scrollbar(fr_images, orient=tk.VERTICAL, command=w['tr_images'].yview)
    s.grid(column=1, row=0, sticky=(tk.NS))
    w['tr_images']['yscrollcommand'] = s.set

    # preview pane
    w['cv_image_preview'] = tk.Canvas(pn_tabimages, background='#eeeeee')
    w['cv_image_preview'].grid(column=1, row=0, sticky=(tk.NS, tk.EW))
    w['cv_image_preview'].bind('<Configure>', lambda x: self.update_input_image_preview())
    pn_tabimages.add(w['cv_image_preview'], weight=3)

    fr_image_actions = ttk.Frame(tab_images)
    fr_image_actions.grid(column=0, row=1, sticky=(tk.S, tk.EW))

    w['bt_image_add'] = ttk.Button(fr_image_actions, text='Add images', command=self.ui_bt_image_add)
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

    w['bt_mask_copy'] = ttk.Button(fr_mask_actions, text='Copy', command=self.copy_masks)
    w['bt_mask_copy'].grid(column=2, row=0, padx=5, pady=5, ipadx=3)

    w['bt_mask_delete'] = ttk.Button(fr_mask_actions, text='Delete', command=self.delete_masks)
    w['bt_mask_delete'].grid(column=3, row=0, padx=5, pady=5, ipadx=3)


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
    tab_stack.rowconfigure(0, weight=1)
    tab_stack.columnconfigure(2, weight=1)

    # fr_stack_left_pane = ScrollFrame(tab_stack)
    fr_stack_left_pane = ScrollableFrame(tab_stack, background='#ff5555')
    fr_stack_left_pane.grid(column=1, row=0, sticky=(tk.NS, tk.EW))


    fr_stack_left_pane.view_port.rowconfigure(8, weight=1)
    fr_stack_left_pane.view_port.columnconfigure(0, weight=1)

    # scrollbar for left pane
    s = tk.Scrollbar(tab_stack, orient=tk.VERTICAL, command=fr_stack_left_pane.yview)
    fr_stack_left_pane.configure(yscrollcommand=s.set)
    fr_stack_left_pane.scrollbar = s
    s.grid(column=0, row=0, sticky=(tk.NS))


    # alignment frame
    fr_stack_align = ttk.Labelframe(fr_stack_left_pane.view_port, text=' Alignment options ')
    fr_stack_align.grid(column=0, row=0, sticky=(tk.NS, tk.EW))

    v_ck_align = tk.BooleanVar()
    w['ck_align'] = ttk.Checkbutton(fr_stack_align, text='Align images', onvalue=True, offvalue=False,
                                    variable=v_ck_align, command=self.ui_ck_align_changed)
    w['ck_align'].grid(column=0, row=0, sticky=(tk.W, tk.N), padx=20, pady=5)
    w['ck_align'].var = v_ck_align


    ttk.Label(fr_stack_align, text='    Aligner: ').grid(column=1, row=0, sticky=(tk.E, tk.N), padx=(20,0), pady=5)

    v_cb_stack_aligner = tk.StringVar()
    w['cb_stack_aligner'] = ttk.Combobox(fr_stack_align, justify=tk.CENTER,
                                         values=('ECC', 'align_image_stack'),
                                         textvariable=v_cb_stack_aligner, state='readonly', width=20)
    w['cb_stack_aligner'].grid(column=2, row=0, sticky=(tk.W, tk.N), padx=(0,10), pady=(5, 20))
    w['cb_stack_aligner'].bind('<<ComboboxSelected>>', lambda x: self.ui_cb_stack_aligner_changed())
    w['cb_stack_aligner'].var = v_cb_stack_aligner


    # padding between frames
    ttk.Frame(fr_stack_left_pane.view_port).grid(column=0, row=1, sticky=(tk.N, tk.EW), pady=7)


    # align_image_stack options
    fr_stack_ais = ttk.Labelframe(fr_stack_left_pane.view_port, text=' align_image_stack options ')
    fr_stack_ais.grid(column=0, row=2, sticky=(tk.N, tk.EW))
    w['fr_stack_ais'] = fr_stack_ais


    v_ck_autocrop = tk.BooleanVar()
    w['ck_autocrop'] = ttk.Checkbutton(fr_stack_ais, text='Autocrop', onvalue=True, offvalue=False,
                                       variable=v_ck_autocrop)
    w['ck_autocrop'].grid(column=1, row=0, sticky=(tk.W), padx=20, pady=5)
    w['ck_autocrop'].var = v_ck_autocrop

    v_ck_centershift = tk.BooleanVar()
    w['ck_centershift'] = ttk.Checkbutton(fr_stack_ais, text='Optimize image center shift',
                                          onvalue=True, offvalue=False, variable=v_ck_centershift)
    w['ck_centershift'].grid(column=0, row=1, sticky=(tk.W), padx=20, pady=5)
    w['ck_centershift'].var = v_ck_centershift

    v_ck_fov = tk.BooleanVar()
    w['ck_fov'] = ttk.Checkbutton(fr_stack_ais, text='Optimize field of view', onvalue=True, offvalue=False,
                                  variable=v_ck_fov)
    w['ck_fov'].grid(column=1, row=1, sticky=(tk.W), padx=20, pady=5)
    w['ck_fov'].var = v_ck_fov

    # correlation threshold
    ttk.Label(fr_stack_ais, text='Correlation threshold: ').grid(column=0, row=2, sticky=(tk.E), padx=20, pady=10)

    v_sp_corr_threshold = tk.StringVar()
    w['sp_corr_threshold'] = ttk.Spinbox(fr_stack_ais, from_=0.0, to=1.0, increment=0.1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_corr_threshold)
    w['sp_corr_threshold'].grid(column=1, row=2, sticky=(tk.W), padx=20, pady=10)
    w['sp_corr_threshold'].var = v_sp_corr_threshold

    # error threshold
    ttk.Label(fr_stack_ais, text='Error threshold: ').grid(column=0, row=3, sticky=(tk.E), padx=20, pady=10)

    v_sp_error_threshold = tk.StringVar()
    w['sp_error_threshold'] = ttk.Spinbox(fr_stack_ais, from_=1, to=20, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_error_threshold)
    w['sp_error_threshold'].grid(column=1, row=3, sticky=(tk.W), padx=20, pady=10)
    w['sp_error_threshold'].var = v_sp_error_threshold


    # control points
    ttk.Label(fr_stack_ais, text='Number of control points: ').grid(column=0, row=4, sticky=(tk.E), padx=20, pady=7)

    v_sp_control_points = tk.IntVar()
    w['sp_control_points'] = ttk.Spinbox(fr_stack_ais, from_=0, to=50, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_control_points)
    w['sp_control_points'].grid(column=1, row=4, sticky=(tk.W), padx=20, pady=7)
    w['sp_control_points'].var = v_sp_control_points

    # grid size
    ttk.Label(fr_stack_ais, text='Grid size: ').grid(column=0, row=5, sticky=(tk.E), padx=20, pady=7)

    v_sp_grid_size = tk.IntVar()
    w['sp_grid_size'] = ttk.Spinbox(fr_stack_ais, from_=1, to=10, increment=1,
                                    justify=tk.CENTER, width=10, textvariable=v_sp_grid_size)
    w['sp_grid_size'].grid(column=1, row=5, sticky=(tk.W), padx=20, pady=7)
    w['sp_grid_size'].var = v_sp_grid_size

    # scale factor
    ttk.Label(fr_stack_ais, text='Scale factor: ').grid(column=0, row=6, sticky=(tk.E), padx=20, pady=7)

    v_sp_scale_factor = tk.IntVar()
    w['sp_scale_factor'] = ttk.Spinbox(fr_stack_ais, from_=0, to=5, increment=1,
                                       justify=tk.CENTER, width=10, textvariable=v_sp_scale_factor)
    w['sp_scale_factor'].grid(column=1, row=6, sticky=(tk.W), padx=20, pady=(7, 20))
    w['sp_scale_factor'].var = v_sp_scale_factor



    # ECC option
    fr_stack_ecc = ttk.Labelframe(fr_stack_left_pane.view_port, text=' ECC options ')
    fr_stack_ecc.grid(column=0, row=2, sticky=(tk.N, tk.EW))
    w['fr_stack_ecc'] = fr_stack_ecc

    # number of iteration
    ttk.Label(fr_stack_ecc, text='Number of iterations: ').grid(column=0, row=0, sticky=(tk.E), padx=20, pady=10)

    v_sp_ecc_iterations = tk.IntVar()
    w['sp_ecc_iterations'] = ttk.Spinbox(fr_stack_ecc, from_=0, to=100, increment=1,
                                         justify=tk.CENTER, width=10, textvariable=v_sp_ecc_iterations)
    w['sp_ecc_iterations'].grid(column=1, row=0, sticky=(tk.W), padx=20, pady=10)
    w['sp_ecc_iterations'].var = v_sp_ecc_iterations

    # termination epsilon
    ttk.Label(fr_stack_ecc, text='Termination epsilon: ').grid(column=0, row=1, sticky=(tk.E), padx=20, pady=10)

    v_sp_ecc_ter_eps = tk.StringVar()
    w['sp_ecc_ter_eps'] = ttk.Entry(fr_stack_ecc, justify=tk.CENTER, width=10, textvariable=v_sp_ecc_ter_eps)
    w['sp_ecc_ter_eps'].grid(column=1, row=1, sticky=(tk.W), padx=20, pady=10)
    w['sp_ecc_ter_eps'].var = v_sp_ecc_ter_eps

    # number of processes in the Pool
    ttk.Label(fr_stack_ecc, text='Multiprocessing pool: ').grid(column=0, row=3, sticky=(tk.E), padx=20, pady=10)

    v_sp_ecc_pool = tk.IntVar()
    w['sp_ecc_pool'] = ttk.Spinbox(fr_stack_ecc, from_=1, to=mp.cpu_count()-1, increment=1,
                                   justify=tk.CENTER, width=10, textvariable=v_sp_ecc_pool)
    w['sp_ecc_pool'].grid(column=1, row=3, sticky=(tk.W), padx=20, pady=(10, 20))
    w['sp_ecc_pool'].var = v_sp_ecc_pool



    # padding between frames
    ttk.Frame(fr_stack_left_pane.view_port).grid(column=0, row=3, sticky=(tk.N, tk.EW), pady=7)


    # enfuse options
    fr_stack_fusion = ttk.Labelframe(fr_stack_left_pane.view_port, text=' enfuse options ')
    fr_stack_fusion.grid(column=0, row=4, sticky=(tk.N, tk.EW))
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
    w['sp_window_size'] = ttk.Spinbox(fr_stack_fusion, from_=3, to=100, increment=2,
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

    v_sp_edge_scale = tk.StringVar()
    w['sp_edge_scale'] = ttk.Spinbox(fr_edge_scale, from_=0, to=100, increment=1,
                                     justify=tk.CENTER, width=5, textvariable=v_sp_edge_scale)
    w['sp_edge_scale'].grid(column=0, row=0, sticky=(tk.W), padx=20, pady=7)
    w['sp_edge_scale'].var = v_sp_edge_scale

    v_sp_lce_scale = tk.StringVar()
    w['sp_lce_scale'] = ttk.Spinbox(fr_edge_scale, from_=0, to=100, increment=1,
                                    justify=tk.CENTER, width=5, textvariable=v_sp_lce_scale)
    w['sp_lce_scale'].grid(column=1, row=0, sticky=(tk.W), padx=0, pady=7)
    w['sp_lce_scale'].var = v_sp_lce_scale

    v_ck_lce_scale = tk.BooleanVar()
    w['ck_lce_scale'] = ttk.Checkbutton(fr_edge_scale, text='%', onvalue=True, offvalue=False,
                                        var=v_ck_lce_scale)
    w['ck_lce_scale'].grid(column=2, row=0, sticky=(tk.W), padx=5, pady=7)
    w['ck_lce_scale'].var = v_ck_lce_scale

    v_sp_lce_level = tk.StringVar()
    w['sp_lce_level'] = ttk.Spinbox(fr_edge_scale, from_=0, to=100, increment=1,
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

    v_sp_curvature = tk.StringVar()
    w['sp_curvature'] = ttk.Spinbox(fr_stack_fusion, from_=1, to=100, increment=1, justify=tk.CENTER,
                                    width=10, textvariable=v_sp_curvature)
    w['sp_curvature'].grid(column=1, row=4, sticky=(tk.W), padx=20, pady=7)
    w['sp_curvature'].var = v_sp_curvature

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


    # padding between frames
    ttk.Frame(fr_stack_left_pane.view_port).grid(column=0, row=5, sticky=(tk.N, tk.EW), pady=7)

    # Output options

    fr_stack_output = ttk.Labelframe(fr_stack_left_pane.view_port, text=' Output ')
    fr_stack_output.grid(column=0, row=6, sticky=(tk.N, tk.EW))
    fr_stack_output.columnconfigure(3, weight=1)


    # final output size
    v_ck_output_size = tk.BooleanVar()
    w['ck_output_size'] = ttk.Checkbutton(fr_stack_output, text='Final size', onvalue=True, offvalue=False,
                                           variable=v_ck_output_size, command=self.ui_ck_output_size_changed)
    #w['ck_output_size'].grid(column=0, row=1, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['ck_output_size'].var = v_ck_output_size

    fr_output_size = ttk.Frame(fr_stack_output)
    #fr_output_size.grid(column=1, row=1, sticky=(tk.EW))

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
    fr_file_format.grid(column=0, columnspan=3, row=0, sticky=(tk.W), padx=10, pady=7)

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
                                      increment=1, width=10, textvariable=v_sp_jpg_quality)
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

    fr_intermediate_files = ttk.Frame(fr_stack_output)
    fr_intermediate_files.grid(column=0, columnspan=3, row=1, sticky=(tk.EW), padx=10, pady=7)

    v_ck_keep_aligned = tk.BooleanVar()
    w['ck_keep_aligned'] = ttk.Checkbutton(fr_intermediate_files, text='Keep aligned images',
                                           onvalue=True, offvalue=False, variable=v_ck_keep_aligned)
    w['ck_keep_aligned'].grid(column=0, row=0, sticky=(tk.EW, tk.N), padx=20, pady=7)
    w['ck_keep_aligned'].var = v_ck_keep_aligned

    v_ck_keep_masked = tk.BooleanVar()
    w['ck_keep_masked'] = ttk.Checkbutton(fr_intermediate_files, text='Keep masked images',
                                           onvalue=True, offvalue=False, variable=v_ck_keep_masked)
    w['ck_keep_masked'].grid(column=1, row=0, sticky=(tk.EW, tk.N), padx=20, pady=7)
    w['ck_keep_masked'].var = v_ck_keep_masked

    ttk.Frame(fr_stack_output).grid(column=0, row=3, pady=5)  # padding bottom


    # output actions
    fr_stack_actions = ttk.Frame(fr_stack_left_pane.view_port, padding=(15, 10))
    fr_stack_actions.grid(column=0, row=7, sticky=(tk.N, tk.EW), pady=20)
    fr_stack_actions.columnconfigure(0, weight=1)
    fr_stack_actions.columnconfigure(1, weight=1)
    fr_stack_actions.columnconfigure(2, weight=1)


    w['bt_stack'] = ttk.Button(fr_stack_actions, text='Stack', command=self.stack_images)
    w['bt_stack'].grid(column=0, row=0)

    w['bt_cancel_stack'] = ttk.Button(fr_stack_actions, text='Cancel', command=self.cancel_stack_images)
    w['bt_cancel_stack'].grid(column=1, row=0)

    ttk.Button(fr_stack_actions, text='Toggle log', command=self.toggle_log).grid(column=2, row=0, sticky=(tk.E))

    # stacked preview pane
    w['cv_stacked_preview'] = tk.Canvas(tab_stack, background='#eeeeee')
    w['cv_stacked_preview'].grid(column=2, row=0, sticky=(tk.NS, tk.EW), padx=(4,0))
    w['cv_stacked_preview'].bind("<Configure>", lambda x: self.update_output_image_preview())
    w['cv_stacked_preview'].grid_remove()


    # textbox to print log to
    w['tx_log'] = tk.Text(tab_stack, borderwidth=5, relief=tk.FLAT)
    w['tx_log'].grid(column=2, row=0, sticky=(tk.NS, tk.EW), padx=(4, 0))

    # scrollbar for log text
    s = ttk.Scrollbar(tab_stack, orient=tk.VERTICAL, command=w['tx_log'].yview)
    s.grid(column=3, row=0, sticky=(tk.NS))
    w['tx_log']['yscrollcommand'] = s.set
    w['tx_log'].scroll = s


    # ==== preferences panel ====
    tab_prefs.rowconfigure(5, weight=1)
    tab_prefs.columnconfigure(1, weight=1)

    # path to the required tools
    fr_prefs_exec = ttk.Labelframe(tab_prefs, text=' Program/Execute ')
    fr_prefs_exec.grid(column=0, row=0, sticky=(tk.N, tk.EW), pady=(0, 20))

    # align_image_stack exec
    ttk.Label(fr_prefs_exec, text='   align_image_stack:').grid(column=0, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_exec_align = tk.StringVar()
    w['en_exec_align'] = ttk.Entry(fr_prefs_exec, textvariable=v_en_exec_align, width=70)
    w['en_exec_align'].grid(column=1, row=0, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_exec_align'].var = v_en_exec_align

    ttk.Button(fr_prefs_exec, text="Browse", command=self.browse_exec_align) \
       .grid(column=3, row=0, sticky=(tk.W), padx=10, pady=0)

    # enfuse exec
    ttk.Label(fr_prefs_exec, text='enfuse:').grid(column=0, row=1, sticky=(tk.E), padx=5, pady=7)

    v_en_exec_enfuse = tk.StringVar()
    w['en_exec_enfuse'] = ttk.Entry(fr_prefs_exec, textvariable=v_en_exec_enfuse, width=70)
    w['en_exec_enfuse'].grid(column=1, row=1, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_exec_enfuse'].var = v_en_exec_enfuse

    ttk.Button(fr_prefs_exec, text="Browse", command=self.browse_exec_enfuse) \
       .grid(column=3, row=1, sticky=(tk.W), padx=10, pady=0)

    # exiftool exec
    ttk.Label(fr_prefs_exec, text='exiftool:').grid(column=0, row=2, sticky=(tk.E), padx=5, pady=7)

    v_en_exec_exiftool = tk.StringVar()
    w['en_exec_exiftool'] = ttk.Entry(fr_prefs_exec, textvariable=v_en_exec_exiftool, width=70)
    w['en_exec_exiftool'].grid(column=1, row=2, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_exec_exiftool'].var = v_en_exec_exiftool

    ttk.Button(fr_prefs_exec, text="Browse", command=self.browse_exec_exiftool) \
       .grid(column=3, row=2, sticky=(tk.W), padx=(10, 20), pady=(0, 18))


    # align_image_stack options
    fr_prefs_align = ttk.Labelframe(tab_prefs, text=' Alignment options ')
    fr_prefs_align.grid(column=0, row=2, sticky=(tk.N, tk.EW), pady=(0,20))

    # aligned prefix
    ttk.Label(fr_prefs_align, text='   aligned prefix:').grid(column=0, row=0, sticky=(tk.E, tk.N), padx=5, pady=7)

    v_en_prefs_align_prefix = tk.StringVar()
    w['en_prefs_align_prefix'] = ttk.Entry(fr_prefs_align, textvariable=v_en_prefs_align_prefix,
                                           width=20, justify=tk.CENTER)
    w['en_prefs_align_prefix'].grid(column=1, row=0, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_prefs_align_prefix'].var = v_en_prefs_align_prefix

    # use GPU
    v_ck_prefs_align_gpu = tk.BooleanVar()
    w['ck_prefs_align_gpu'] = ttk.Checkbutton(fr_prefs_align, variable=v_ck_prefs_align_gpu, text='use GPU')
    w['ck_prefs_align_gpu'].grid(column=2, row=0, sticky=(tk.E, tk.N), padx=50, pady=(7,18))
    w['ck_prefs_align_gpu'].var = v_ck_prefs_align_gpu


    # GUI options
    fr_prefs_gui = ttk.Labelframe(tab_prefs, text=' GUI options ')
    fr_prefs_gui.grid(column=0, row=4, sticky=(tk.N, tk.EW))

    # mask include color
    ttk.Label(fr_prefs_gui, text='  mask-include color:').grid(column=0, row=0, sticky=(tk.E), padx=5, pady=7)

    v_en_prefs_gui_mask_include = tk.StringVar()
    w['en_prefs_gui_mask_include'] = ttk.Entry(fr_prefs_gui, textvariable=v_en_prefs_gui_mask_include,
                                               width=20, justify=tk.CENTER)
    w['en_prefs_gui_mask_include'].grid(column=1, row=0, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_prefs_gui_mask_include'].var = v_en_prefs_gui_mask_include

    # mask exclude color
    ttk.Label(fr_prefs_gui, text='  mask-exclude color:').grid(column=0, row=1, sticky=(tk.E), padx=5, pady=7)

    v_en_prefs_gui_mask_exclude = tk.StringVar()
    w['en_prefs_gui_mask_exclude'] = ttk.Entry(fr_prefs_gui, textvariable=v_en_prefs_gui_mask_exclude,
                                               width=20, justify=tk.CENTER)
    w['en_prefs_gui_mask_exclude'].grid(column=1, row=1, sticky=(tk.W, tk.N), padx=10, pady=7)
    w['en_prefs_gui_mask_exclude'].var = v_en_prefs_gui_mask_exclude

    # mask active color
    ttk.Label(fr_prefs_gui, text='  mask-active color:').grid(column=0, row=2, sticky=(tk.E), padx=5, pady=7)

    v_en_prefs_gui_mask_active = tk.StringVar()
    w['en_prefs_gui_mask_active'] = ttk.Entry(fr_prefs_gui, textvariable=v_en_prefs_gui_mask_active,
                                               width=20, justify=tk.CENTER)
    w['en_prefs_gui_mask_active'].grid(column=1, row=2, sticky=(tk.W, tk.N), padx=10, pady=(7,17))
    w['en_prefs_gui_mask_active'].var = v_en_prefs_gui_mask_active



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

    w['bt_cancel_stack'].configure(state=tk.DISABLED)

    self.ui_cb_stack_aligner_changed()


    # check for availability of the required commands/executes
    for cmd, widget in {
        'align_image_stack' : 'en_exec_align',
        'enfuse'            : 'en_exec_enfuse',
        'exiftool'          : 'en_exec_exiftool'}.items():
      if which(cmd) is None:
        custom_exec = w[widget].var.get()
        if custom_exec.strip() == '':
          tk.messagebox.showerror(message='Cannot find "' + cmd + '".\nPlease specify the file location manually.')
          nb.select(3)  # show the preferences tab
          break
        elif not os.path.exists(custom_exec):
          tk.messagebox.showerror(message='Cannot find "' + custom_exec + '".\nPlease specify the correct location for ' + cmd)
          nb.select(3)  # show the preferences tab
          break




  # ==== Event handlers for widgets ====

  def ui_tr_images_selected(self, event):
    if len(self.widgets['tr_images'].selection()) > 0:
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

    selection = w['tr_masks'].selection()

    if len(selection) > 0:
      w['bt_mask_include'].configure(state=tk.NORMAL)
      w['bt_mask_exclude'].configure(state=tk.NORMAL)
      w['bt_mask_delete'].configure(state=tk.NORMAL)
      w['bt_mask_copy'].configure(state=tk.NORMAL)

    # if one mask selected, make it editable
    self.update_mask_canvas()

  def ui_ck_align_changed(self):
    w = self.widgets
    st = tk.NORMAL
    if w['ck_align'].var.get() == False:
      st = tk.DISABLED

    w['ck_autocrop'].config(state=st)
    w['ck_centershift'].config(state=st)
    w['ck_fov'].config(state=st)
    w['sp_corr_threshold'].config(state=st)
    w['sp_error_threshold'].config(state=st)
    w['sp_control_points'].config(state=st)
    w['sp_grid_size'].config(state=st)
    w['sp_scale_factor'].config(state=st)


  def ui_cb_stack_aligner_changed(self):
    w = self.widgets

    if w['cb_stack_aligner'].var.get() == 'ECC':
      w['fr_stack_ais'].grid_remove()
      w['fr_stack_ecc'].grid()
    else:
      w['fr_stack_ais'].grid()
      w['fr_stack_ecc'].grid_remove()


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



  def browse_exec_align(self):
    filepath = tk.filedialog.askopenfilename(title='Select align_image_stack execute file')

    if filepath != '':
      self.widgets['en_exec_align'].var.set(filepath)


  def browse_exec_enfuse(self):
    filepath = tk.filedialog.askopenfilename(title='Select enfuse execute file')

    if filepath != '':
      self.widgets['en_exec_enfuse'].var.set(filepath)


  def browse_exec_exiftool(self):
    filepath = tk.filedialog.askopenfilename(title='Select exiftool execute file')

    if filepath != '':
      self.widgets['en_exec_exiftool'].var.set(filepath)


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


  def ui_bt_image_add(self):
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

    self.add_images(filepaths)


  def add_images_from_drop(self, event):
    w = self.widgets

    filepaths = w['tr_images'].tk.splitlist(event.data)
    self.add_images(filepaths)

    w['nb'].select(0)



  def add_images(self, filepaths):
    if len(filepaths) == 0:
      return

    # save the current location
    self.config.set('prefs', 'last_opened_location', os.path.dirname(filepaths[0]))

    # update the image list in Images and Stacks tabs
    w = self.widgets
    for filepath in filepaths:
      if filepath in self.input_images:
        continue

      if not os.path.exists(filepath):
        continue

      filename = os.path.basename(filepath)

      w['tr_images'].insert('', tk.END, filepath, text=filename)
      self.input_images.append(filepath)

      w['tr_mask_images'].insert('', tk.END, filepath, text=filename)



  def remove_images(self):
    w = self.widgets
    selection = w['tr_images'].selection()

    for image_id in selection:
      w['tr_images'].delete(image_id)
      w['tr_mask_images'].delete(image_id)

    for image_id in self.input_images[:]:
      if image_id in selection:
        self.input_images.remove(image_id)

    w['bt_image_remove'].configure(state=tk.DISABLED)

    # clear the image and mask preview
    self.update_input_image_preview()


  def get_current_input_image(self):
    """ helper to get the currently selected input image.
    Return None if no image or multiple images selected """
    selection = self.widgets['tr_images'].selection()

    if len(selection) != 1:
      return None

    return selection[0]



  def update_input_image_preview(self):
    """ update the preview with the specified image at index """
    cv = self.widgets['cv_image_preview']

    selection = self.widgets['tr_images'].selection()

    if len(selection) != 1:
      cv.delete(tk.ALL)
      return

    image_id = selection[0]

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
        if item and item['filename'] == image_id:
          img = item['img']
          hit = True
          break

    if hit == False:
      img = Image.open(image_id)
      img.thumbnail((width, height), Image.Resampling.LANCZOS)
      img = ImageTk.PhotoImage(img)

      buffer_slot = cache['head'] % len(cache['slots'])
      cache['slots'][buffer_slot] = {
        'filename' : image_id,
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
    mask_color = self.config.get('widgets', 'en_prefs_gui_mask_active')
    cv.new_mask = cv.create_line(0, 0, 0, 0, fill=mask_color)

    self.widgets['bt_mask_add'].configure(state=tk.DISABLED)


  def copy_masks(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    # clear clipboard
    self.mask_clipboard.clear()

    for mask_id in selection:
      image_id, index = mask_id.split('|')
      self.mask_clipboard.append(copy.deepcopy(self.masks[image_id][int(index)]))

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

    for mask_id in reversed(selection):
      image_id, mask_index = mask_id.split('|')
      self.masks[image_id].pop(int(mask_index))

    self.update_mask_list()
    self.update_mask_canvas()


  def set_masks_include(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    for mask_id in selection:
      image_id, mask_index = mask_id.split('|')
      mask = self.masks[image_id][int(mask_index)]
      mask['type'] = 'include'

    self.update_mask_list()
    self.update_mask_canvas()


  def set_masks_exclude(self):
    w = self.widgets
    selection = w['tr_masks'].selection()

    for mask_id in selection:
      image_id, mask_index = mask_id.split('|')
      mask = self.masks[image_id][int(mask_index)]
      mask['type'] = 'exclude'

    self.update_mask_list()
    self.update_mask_canvas()


  def ui_cv_image_masks_b1(self, event):
    cv = self.widgets['cv_image_masks']

    if self.new_mask != None:
      # handle mask creation
      self.new_mask += [event.x, event.y]

      if len(self.new_mask) <= 6:
        self.ui_cv_image_masks_motion(event)
        return

      cv.coords(cv.new_mask, self.new_mask)
      return

    # select a mask
    current_item = cv.find_closest(event.x, event.y, halo=None, start=None)

    if len(current_item) == 0:
       return

    if cv.type(current_item[0]) == 'polygon':
      if cv.masks[current_item[0]] == 'editable':
        return

      self.widgets['tr_masks'].selection_set(cv.masks[current_item[0]])


  def ui_cv_image_masks_motion(self, event):
    cv = self.widgets['cv_image_masks']

    # set mouse cursor
    current_item = cv.find_closest(event.x, event.y, halo=None, start=None)

    if len(current_item) == 0:
      return

    if cv.type(current_item[0]) == 'oval':
      cv.config(cursor='hand1')
    else:
      cv.config(cursor='')

    if self.new_mask == None or len(self.new_mask) == 0:
      return

    node_count = len(self.new_mask)
    if node_count <= 2:
        cv.coords(cv.new_mask, self.new_mask + [event.x, event.y])
    elif node_count == 4:
      cv.delete(cv.new_mask)
      mask_color = self.config.get('widgets', 'en_prefs_gui_mask_active')
      cv.new_mask = cv.create_polygon(self.new_mask + [event.x, event.y], fill='', outline=mask_color)
    else:
      cv.coords(cv.new_mask, self.new_mask + [event.x, event.y])


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
    mask = self.unscale_polygon(self.new_mask, cv.origin, cv.image_scale)

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

      img.thumbnail((width, height), Image.Resampling.LANCZOS)
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
    w = self.widgets
    cv = w['cv_image_masks']

    # make the currently selected mask editable
    editable_mask = None
    selection = w['tr_masks'].selection()
    if len(selection) == 1:
      editable_mask = selection[0]

    #print(self.masks[self.current_mask_image])
    cv.masks ={}
    image_id = self.get_current_mask_image()

    for i, mask in enumerate(masks):
      mask_color = self.config.get('widgets', 'en_prefs_gui_mask_include')
      if mask['type'] == 'exclude':
        mask_color = self.config.get('widgets', 'en_prefs_gui_mask_exclude')

      if editable_mask != None and editable_mask == (image_id + '|' + str(i)):
        cv.editable_mask = {
          'mask_id':str(i + 1),
          'mask': mask,
          'polygon': None
        }
        self.draw_editable_mask()
      else:
        object_id = cv.create_polygon(self.scale_polygon(mask['mask'], cv.origin, scale),
                                      fill='', outline=mask_color)
        cv.masks[object_id] = image_id + '|' + str(i)  # revert mapping back to the mask

    # bring the editable mask up top (after drawing all masks)
    if editable_mask != None and cv.editable_mask['polygon'] != None:
      cv.tag_raise(cv.editable_mask['polygon'])
      cv.tag_raise('handle')



  def draw_editable_mask(self):
    cv = self.widgets['cv_image_masks']

    if not cv.editable_mask:
      return

    # remove current editable mask and handles
    if 'polygon' in cv.editable_mask and cv.editable_mask['polygon'] != None:
      cv.delete(cv.editable_mask['polygon'])

    mask = cv.editable_mask['mask']
    points = self.scale_polygon(mask['mask'], cv.origin, cv.image_scale)

    # create the mask
    mask_color = self.config.get('widgets', 'en_prefs_gui_mask_active')
    p = cv.create_polygon(points, fill='', outline=mask_color, tags=('editable'))
    cv.masks[p] = 'editable'
    cv.editable_mask['polygon'] = p

    cv.tag_bind(p, '<ButtonPress-1>',   lambda event, tag=p: self.mask_canvas_on_press_tag(event, tag))
    cv.tag_bind(p, '<ButtonRelease-1>', self.mask_canvas_on_release_tag)
    cv.tag_bind(p, '<B1-Motion>', self.mask_canvas_on_move_polygon)

    # add handles for editable mask
    handle_size = 5
    cv.editable_mask['handles'] = []
    for i in range(math.floor(len(points)/2)):
      handle = cv.create_oval(points[2*i]-handle_size, points[2*i+1]-handle_size,
                              points[2*i]+handle_size, points[2*i+1]+handle_size,
                              fill=mask_color, outline=mask_color, tags=('handle'))
      cv.editable_mask['handles'].append(handle)
      cv.tag_bind(handle, '<ButtonPress-1>',   lambda event, tag=handle: self.mask_canvas_on_press_tag(event, tag))
      cv.tag_bind(handle, '<ButtonRelease-1>', self.mask_canvas_on_release_tag)
      cv.tag_bind(handle, '<B1-Motion>', lambda event, number=i: self.mask_canvas_on_move_handle(event, number))


  def mask_canvas_on_press_tag(self, event, tag):
    cv = self.widgets['cv_image_masks']
    cv.editable_mask['selected'] = tag
    cv.editable_mask['previous_x'] = event.x
    cv.editable_mask['previous_y'] = event.y


  def mask_canvas_on_release_tag(self, event):
    cv = self.widgets['cv_image_masks']
    cv.editable_mask['selected'] = None
    cv.editable_mask['previous_x'] = None
    cv.editable_mask['previous_y'] = None


  def mask_canvas_on_move_polygon(self, event):
    ''' move editable mask polygon and handles '''
    cv= self.widgets['cv_image_masks']

    if cv.editable_mask['selected']:
      dx = event.x - cv.editable_mask['previous_x']
      dy = event.y - cv.editable_mask['previous_y']

      # move polygon
      cv.move(cv.editable_mask['selected'], dx, dy)

      # move handles
      for handle in cv.editable_mask['handles']:
        cv.move(handle, dx, dy)

      # update mask data
      points = self.scale_polygon(cv.editable_mask['mask']['mask'], cv.origin, cv.image_scale)

      for i in range(math.floor(len(points)/2)):
        points[2*i]   += dx
        points[2*i+1] += dy

      cv.editable_mask['mask']['mask'] = self.unscale_polygon(points, cv.origin, cv.image_scale)

      cv.editable_mask['previous_x'] = event.x
      cv.editable_mask['previous_y'] = event.y


  def mask_canvas_on_move_handle(self, event, number):
    '''move single hadnle of mask polygon'''
    cv= self.widgets['cv_image_masks']

    if cv.editable_mask['selected']:
      dx = event.x - cv.editable_mask['previous_x']
      dy = event.y - cv.editable_mask['previous_y']

      # move handle
      cv.move(cv.editable_mask['selected'], dx, dy)

      # update mask data
      points = self.scale_polygon(cv.editable_mask['mask']['mask'], cv.origin, cv.image_scale)

      points[2*number]    += dx
      points[2*number+1]  += dy

      cv.editable_mask['mask']['mask'] = self.unscale_polygon(points, cv.origin, cv.image_scale)

      # update mask polygon
      cv.coords(cv.editable_mask['polygon'], points)

      cv.editable_mask['previous_x'] = event.x
      cv.editable_mask['previous_y'] = event.y



  def update_mask_list(self):
    w = self.widgets
    tr = w['tr_masks']

    # save the current selection
    selection = tr.selection()

    for item in tr.get_children():
      tr.delete(item)

    self.update_mask_image_list()

    image_id = self.get_current_mask_image()

    if image_id != None:
      # add all the masks
      if image_id in self.masks:
        for i, mask in enumerate(self.masks[image_id]):
          tr.insert('', tk.END, image_id + '|' + str(i), text='# ' + str(i+1), values=(mask['type']))

      try:
        tr.selection_set(selection)
      except:
        pass

    new_state = tk.DISABLED
    if len(tr.selection()) > 0:
      new_state = tk.NORMAL

    w['bt_mask_include'].configure(state=new_state)
    w['bt_mask_exclude'].configure(state=new_state)
    w['bt_mask_delete'].configure(state=new_state)
    w['bt_mask_copy'].configure(state=new_state)



  def scale_polygon(self, poly, new_origin, new_scale) :
    ''' calculate the point of a polygon at specified scale and origin '''
    p = []

    for i in range(math.floor(len(poly)/2)):
      p.append(poly[2*i]*new_scale + new_origin[0])
      p.append(poly[2*i+1]*new_scale + new_origin[1])

    return p


  def unscale_polygon(self, poly, current_origin, current_scale):
    ''' Calculate the points of a polygon at actual/image scale '''
    p = []

    for i in range(math.floor(len(poly)/2)):
      p.append((poly[2*i]   - current_origin[0])/current_scale)
      p.append((poly[2*i+1] - current_origin[1])/current_scale)

    return p


  def update_output_image_preview(self):
    cv = self.widgets['cv_stacked_preview']
    cv.delete(tk.ALL)

    if len(self.input_images) == 0:
      return

    if self.output_image == None:
       return

    width = cv.winfo_width()
    height = cv.winfo_height()

    img = Image.open(self.output_image)
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    img = ImageTk.PhotoImage(img)

    cv.create_image(width/2, height/2, anchor=tk.CENTER, image=img)
    cv.image = img


  def load_config(self):
    self.config = configparser.ConfigParser()
    c = self.config

    if os.path.isfile('config.ini'):
      c.read('config.ini')

    c['DEFAULT'] = {
      'ck_align'                : 'True',
      'cb_stack_aligner'        : 'ECC',
      'sp_ecc_iterations'       : '50',
      'sp_ecc_ter_eps'          : '1e-1',
      'sp_ecc_pool'             : math.floor(mp.cpu_count()/2),
      'ck_autocrop'             : 'True',
      'ck_centershift'          : 'True',
      'ck_fov'                  : 'True',
      'sp_corr_threshold'       : '0.95',
      'sp_error_threshold'      : '1',
      'sp_control_points'       : '20',
      'sp_grid_size'            : '5',
      'sp_scale_factor'         : '0',
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
      'ck_keep_aligned'         : False,
      'ck_keep_masked'          : False,

      # preferences
      'sp_mask_add_type'        : 'exclude',
      'en_exec_align'           : 'align_image_stack',
      'en_exec_enfuse'          : 'enfuse',
      'en_exec_exiftool'        : 'exiftool',
      'ck_prefs_align_gpu'      : False,

      'en_prefs_align_prefix'     : 'aligned__',
      'en_prefs_gui_mask_include' : '#00ff00',
      'en_prefs_gui_mask_exclude' : '#ff0000',
      'en_prefs_gui_mask_active'  : '#ffff00'
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
    w = self.widgets

    align_exec = self.config.get('widgets', 'en_exec_align')
    align_prefix = self.config.get('widgets', 'en_prefs_align_prefix')

    cmd = [align_exec, '-v', '-a'+align_prefix, '--use-given-order', '--distortion']

    if w['ck_prefs_align_gpu'].var.get():
      cmd.append('--gpu')

    # get the alignment options

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



  def build_enfuse_command(self, images):
    enfuse_exec = self.config.get('widgets', 'en_exec_enfuse')

    cmd = [enfuse_exec, '-v', '-o', self.output_name,
           '--exposure-weight=0',
           '--saturation-weight=0',
           '--contrast-weight=1',
           '--blend-colorspace=CIECAM']

    w = self.widgets

    if w['ck_hard_mask'].var.get():
      cmd.append('--hard-mask')

    if not w['ck_levels'].var.get():
      cmd.append('--levels=' + str(w['sp_levels'].var.get()))

    if w['ck_edge_scale'].var.get():
      opt = str(w['sp_edge_scale'].var.get()) + ':'
      opt += str(w['sp_lce_scale'].var.get()) + ('%' if w['ck_lce_scale'].var.get() else '')
      opt += ':' + str(w['sp_lce_level'].var.get()) + ('%' if w['ck_lce_level'].var.get() else '')
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

    cmd = cmd + images
    return cmd



  def apply_masks_to_images(self, images):
    """ applied masks to images, assuming that they are aligned """
    masked_images = []

    # images might have different filename/path from original input
    images_map = {}
    for i, filepath in enumerate(self.input_images):
      images_map[filepath] = images[i]

    # each "include" mask is equivalent to "exclude" masks for each of the other images
    file_masks = copy.deepcopy(self.masks)

    for filepath in self.masks:
      for mask in file_masks[filepath]:
        if mask['type'] == 'include':
          for other_filepath in self.input_images:
            if filepath != other_filepath:
              exclude_mask = copy.deepcopy(mask)
              exclude_mask['type'] = 'exclude'

              if other_filepath not in file_masks:
                file_masks[other_filepath] = []

              file_masks[other_filepath].append(exclude_mask)

    for filepath in self.input_images:
      # important: treat every image as having mask. Our outputs might have
      # different format/setting than the original, don't mix them
      img  = Image.open(images_map[filepath]).convert('RGBA')

      alpha = Image.new('L', img.size, 255)
      alpha_mask = ImageDraw.Draw(alpha)

      if filepath in file_masks:
        for mask in file_masks[filepath]:
          if mask['type'] == 'exclude':
            alpha_mask.polygon(mask['mask'], fill=126)

        # add include mask after exclude masks
        for mask in file_masks[filepath]:
          if mask['type'] == 'include':
            alpha_mask.polygon(mask['mask'], fill=255)

      img.putalpha(alpha)

      new_path = os.path.join(
        os.path.dirname(images_map[filepath]),
        'masked_' + os.path.splitext(os.path.basename(images_map[filepath]))[0] + '.tif'
      )

      img.save(new_path)
      masked_images.append(new_path)

    return masked_images


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

    w['bt_stack'].configure(state=tk.DISABLED)
    w['bt_cancel_stack'].configure(state=tk.NORMAL)

    w['tx_log'].delete(1.0, tk.END)
    self.toggle_log(True)

    self.output_image = None
    self.update_output_image_preview()

    self.stack_cancelled = False
    self.returncode = tk.IntVar()

    if w['ck_align'].var.get():
      aligned_prefix = self.config.get('widgets', 'en_prefs_align_prefix')

      if w['cb_stack_aligner'].var.get() == 'align_image_stack':
        self.aligned_images = []

        for i, image in enumerate(self.input_images):
          self.aligned_images.append(os.path.join(
            os.path.dirname(image),
            aligned_prefix + '{:04d}'.format(i) + '.tif'))

        align_cmd = self.build_align_command()
        print(align_cmd)

        self.returncode.set(-1)
        self.thread = threading.Thread(target=self.execute_cmd, args=[align_cmd], daemon=True).start()
        self.wait_variable(self.returncode)

        if self.returncode.get() > 0:
          tk.messagebox.showerror(message='Error aligning images, please check output log.')
          w['bt_cancel_stack'].configure(state=tk.DISABLED)
          w['bt_stack'].configure(state=tk.NORMAL)
          return

      else:  # ECC alignment
        self.opencv_aligner = OpenCV_Aligner()
        ecc_options = {
          'prefix'      : aligned_prefix,
          'iteration'   : int(w['sp_ecc_iterations'].var.get()),
          'ter_eps'     : float(w['sp_ecc_ter_eps'].var.get()),
          'pool_size'   : int(w['sp_ecc_pool'].var.get()),
          'signaler'    : self.returncode,
          'align_images': [],
          'logger'      : w['tx_log']
        }

        w['tx_log'].insert(tk.END, '\n======== Aligning images using ECC ======== ')
        w['tx_log'].see(tk.END)


        self.returncode.set(-1)
        self.thread = threading.Thread(target=self.opencv_aligner.align, args=[self.input_images, ecc_options], daemon=True).start()
        self.wait_variable(self.returncode)
        self.aligned_images = ecc_options['aligned_images']


    if self.stack_cancelled == True:
      return

    if w['ck_align'].var.get():
      images = self.aligned_images
    else:
      images = self.input_images

    # generate masked images
    has_mask = False
    for filepath in self.masks:
      for mask in self.masks[filepath]:
        has_mask = True
        break
      if has_mask == True:
        break

    if not has_mask:
      w['tx_log'].insert(tk.END, '\n\n===== NO MASK FOUND =====\n\n')
    else:
      w['tx_log'].insert(tk.END, '\n\n===== APPLYING MASK =====\n\n')
      images = self.apply_masks_to_images(images)


    # call enfuse
    enfuse_cmd = self.build_enfuse_command(images)
    print(enfuse_cmd)

    w['tx_log'].insert(tk.END, '\n\n===== CALLING ENFUSE =====\n')
    w['tx_log'].insert(tk.END, 'output to ' + self.output_name + '\n\n')

    self.returncode.set(-1)
    self.thread = threading.Thread(target=self.execute_cmd, args=[enfuse_cmd], daemon=True).start()
    self.wait_variable(self.returncode)

    if self.stack_cancelled == True:
      return

    if self.returncode.get() > 0:
      tk.messagebox.showerror(message='Error stacking images, please check output log.')
      w['bt_cancel_stack'].configure(state=tk.DISABLED)
      w['bt_stack'].configure(state=tk.NORMAL)
      return

    w['tx_log'].insert(tk.END, '\nDone stacking to ' + self.output_name + '\n\n')
    w['tx_log'].see(tk.END)


    # copy EXIF
    w['tx_log'].insert(tk.END, '\nCopying EXIF from ' + self.input_images[0] + ' to ' + self.output_name + '\n\n')
    w['tx_log'].see(tk.END)

    exiftool_exec = self.config.get('widgets', 'en_exec_exiftool')
    exiftool_cmd = [exiftool_exec, '-TagsFromFile', self.input_images[0],
                    '-all:all', '-overwrite_original', self.output_name]
    self.execute_cmd(exiftool_cmd)

    # clean up aligned TIFFs
    if w['ck_align'].var.get() and not w['ck_keep_aligned'].var.get():
      for filename in self.aligned_images:
        os.remove(filename)
      w['tx_log'].insert(tk.END, '\nRemoved aligned images \n\n')
      w['tx_log'].see(tk.END)

    # clean up masked TIFFs
    if has_mask and not w['ck_keep_masked'].var.get():
      for filename in images:
        os.remove(filename)
      w['tx_log'].insert(tk.END, '\nRemoved masked images \n\n')
      w['tx_log'].see(tk.END)


    # load the output file into the result pane
    self.output_image = os.path.join(
      os.path.basename(self.input_images[0]),
      self.output_name
    )

    self.update_output_image_preview()
    self.toggle_log(False)

    w['bt_cancel_stack'].configure(state=tk.DISABLED)
    w['bt_stack'].configure(state=tk.NORMAL)




  def cancel_stack_images(self):
    w = self.widgets
    self.stack_cancelled = True
    self.output_name = None

    w['bt_cancel_stack'].configure(state=tk.DISABLED)
    w['bt_stack'].configure(state=tk.NORMAL)

    if self.subprocess:
      self.subprocess.kill()

    if self.thread:
      self.thread.join()

    if self.opencv_aligner:
      self.opencv_aligner.cancel()

    w['tx_log'].insert(tk.END, '\n\nStacking cancelled by user.\n\n')
    w['tx_log'].see(tk.END)



  def execute_cmd(self, cmd):
    log_box = self.widgets['tx_log']
    working_dir = os.path.dirname(self.input_images[0])

    p = subprocess.Popen(cmd, cwd=working_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    self.subprocess = p

    while p.poll() is None:
      msg = p.stdout.readline()
      log_box.insert(tk.END, msg)
      log_box.see(tk.END)

    self.subprocess = None
    self.returncode.set(p.returncode)


  def save_project(self):
    # ask if we don't have a save file yet
    if self.save_file == None:
      if len(self.input_images) > 0:
        initial_dir = os.path.dirname(self.input_images[0])
        default_filename = os.path.splitext(os.path.basename(self.input_images[0]))[0] + '.mft'
      else:
        initial_dir = self.config['prefs']['last_opened_location']
        default_filename = 'new_project.mft'

      save_file = tk.filedialog.asksaveasfilename(
        initialdir= initial_dir,
        confirmoverwrite=True,
        defaultextension='mft',
        initialfile=default_filename
      )

      if save_file == '':
        return

      self.save_file = save_file

    data = {
      'input_images': self.input_images,
      'masks'       : self.masks
    }

    with open(self.save_file, 'w') as outfile:
      outfile.write(json.dumps(data))

    # set the window title to the filename
    self.title('MFTker - ' + os.path.basename(self.save_file))


  def load_project(self):
    w = self.widgets

    load_file = tk.filedialog.askopenfilename(
      title = 'Load a project file',
      initialdir = self.config['prefs']['last_opened_location'],
      filetypes = [('MFTker project file', '.mft')],
      multiple = False
    )

    if load_file != '':
      with open(load_file) as infile:
        try:
          data = json.load(infile)
          infile.close()
        except json.JSONDecodeError as e:
          tk.messagebox.showerror(message='Error parsing project file "' +
                                  os.path.basename(load_file) + '":\n' + str(e))
          infile.close()
          return

        # clean out the current files
        for image_id in self.input_images[:]:
          w['tr_images'].delete(image_id)
          w['tr_mask_images'].delete(image_id)
          self.input_images.remove(image_id)

        self.add_images(data['input_images'])

        self.masks.clear()
        for image_id in data['masks']:
          if image_id in self.input_images:
            self.masks[image_id] = data['masks'][image_id]

        self.update_mask_image_list()
        self.update_mask_canvas()

        # set the window title to the filename
        self.title('MFTker - ' + os.path.basename(load_file))
        self.save_file = load_file






class OpenCV_Aligner():
  prefix = 'aligned__'
  iteration = 20
  ter_eps = 1e-1
  pool_size = math.floor(mp.cpu_count()/2)
  cancelled = False  # flag to terminate processes

  def align(self, image_list, options = {}):
    """ root-level function for multiprocessing """
    global pool

    if 'prefix' in options:
      self.prefix = options['prefix']

    if 'iteration' in options:
      self.iteration = options['iteration']

    if 'ter_eps' in options:
      self.ter_eps = options['ter_eps']

    if 'pool_size' in options:
      self.pool_size = options['pool_size']

    anchor_index = math.floor(len(image_list)/2)
    anchor_img = cv2.imread(image_list[anchor_index])

    # write out anchor image as-is
    aligned_filename = os.path.join(
      os.path.dirname(image_list[anchor_index]),
      self.prefix + os.path.basename(image_list[anchor_index])
    )

    cv2.imwrite(aligned_filename, anchor_img)
    options['logger'].insert(tk.END, '\nUsing "' + os.path.basename(image_list[anchor_index]) + '" as anchor')
    options['logger'].see(tk.END)

    # initiate a pool
    pool = mp.Pool(self.pool_size)

    options['logger'].insert(tk.END, '\nInitated a pool of ' + str(self.pool_size) + ' workers\n')
    options['logger'].see(tk.END)

    aligned_images = []
    results = []
    self.cancelled = False

    worker_options = {
      'prefix'      :  str(options['prefix']),
      'iteration'   :  int(options['iteration']),
      'ter_eps'     :  float(options['ter_eps'])
    }

    for i, filepath in enumerate(image_list):
      if i != anchor_index:
        options['logger'].insert(tk.END, '\nAligning "' + os.path.basename(filepath) + '"')
        options['logger'].see(tk.END)


        # important: do not pass any widget to apply_async since we're copying the parent into the child processes
        result = pool.apply_async(self.align_pyramid, (str(image_list[anchor_index]), str(filepath), worker_options.copy()))

        # for single-process debugging:
        # result = self.align_pyramid(str(image_list[anchor_index]), str(filepath), worker_options.copy())

        if self.cancelled == True:
          break

        results.append(result)

      aligned_filename = os.path.join(
        os.path.dirname(filepath),
        self.prefix + os.path.basename(filepath)
      )
      aligned_images.append(aligned_filename)


    # close Pool and let all the processes complete
    pool.close()
    pool.join()  # wait for all processes

    if not self.cancelled:
      options['logger'].insert(tk.END, '\n\nDone aligning all images\n')
      options['logger'].see(tk.END)


    options['aligned_images'] = aligned_images
    options['signaler'].set(0)




  def align_pyramid(self, anchor_filepath, target_filepath, options):
    ''' pyramid algorithm from https://stackoverflow.com/questions/45997891/cv2-motion-euclidean-for-the-warp-mode-in-ecc-image-alignment-method '''

    print('\nECC aligning ' + os.path.basename(target_filepath) + ' against ' + os.path.basename(anchor_filepath))

    anchor_img = cv2.imread(anchor_filepath)
    anchor_img_gray = cv2.cvtColor(anchor_img, cv2.COLOR_RGB2GRAY)

    prefix    = options['prefix']
    iteration = options['iteration']
    ter_eps   = options['ter_eps']

    pyramid_level = None
    if 'pyramid_level' in options:
      pyramid_level = options['pyramid_level']


    warp_mode = cv2.MOTION_HOMOGRAPHY

    # Initialize the matrix to identity
    warp_matrix = np.array([[1,0,0],[0,1,0],[0,0,1]], dtype=np.float32)

    w = anchor_img_gray.shape[1]

    # determine number of levels
    if pyramid_level is None:
      nol =  math.floor((math.log(w/300, 2)))
    else:
      nol = pyramid_level

    # print('Number of levels: ' + str(nol))

    warp_matrix[0][2] /= (2**nol)
    warp_matrix[1][2] /= (2**nol)

    target_img = cv2.imread(target_filepath)
    target_img_gray = cv2.cvtColor(target_img, cv2.COLOR_RGB2GRAY)

    # construct grayscale pyramid
    gray1_pyr = [anchor_img_gray]
    gray2_pyr = [target_img_gray]

    # print('target_img: ', target_img_gray.shape)

    for level in range(nol):
      # print('level: ', level, ', gray1_pyr[0].shape: ', gray1_pyr[0].shape)

      gray1_pyr.insert(0, cv2.resize(gray1_pyr[0], None, fx=1/2, fy=1/2, interpolation=cv2.INTER_AREA))
      gray2_pyr.insert(0, cv2.resize(gray2_pyr[0], None, fx=1/2, fy=1/2, interpolation=cv2.INTER_AREA))

    # Terminate the optimizer if either the max iterations or the threshold are reached
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, iteration, ter_eps )

    # run pyramid ECC
    # pyr_start_time = timeit.default_timer()

    for level in range(nol+1):
      # lvl_start_time = timeit.default_timer()

      grad1 = gray1_pyr[level]
      grad2 = gray2_pyr[level]

      # print('level:', level, ', gray1_pyr[level].shape:', gray1_pyr[level].shape)

      cc, warp_matrix = cv2.findTransformECC(grad1, grad2, warp_matrix, warp_mode, criteria)

      if level < nol:
        # scale up for the next pyramid level
        warp_matrix = warp_matrix * np.array([[1,1,2],[1,1,2],[0.5,0.5,1]], dtype=np.float32)

      # print('Level %i time:'%level, timeit.default_timer() - lvl_start_time)

    # print('Pyramid time (', os.path.basename(target_filepath), '): ', timeit.default_timer() - pyr_start_time)

    # Get the target size from the desired image
    target_shape = anchor_img.shape

    aligned_img = cv2.warpPerspective(
                        target_img,
                        warp_matrix,
                        (target_shape[1], target_shape[0]),
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                        flags=cv2.INTER_AREA + cv2.WARP_INVERSE_MAP)

    aligned_filename = os.path.join(
      os.path.dirname(target_filepath),
      prefix + os.path.basename(target_filepath)
    )

    cv2.imwrite(aligned_filename, aligned_img)
    print('\nDone ECC aligning, written to: ' + os.path.basename(aligned_filename))



  def cancel(self):
    global pool

    self.cancelled = True
    pool.close()
    pool.terminate()
    pool.join()








class ScrollableFrame(tk.Canvas):
  ''' simulate a scrollable frame by using a Frame inside a Canvas '''
  scrollable = False
  scrollbar  = None

  def __init__(self, *args, **kwargs):
    tk.Canvas.__init__(self, *args, **kwargs)
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(0, weight=1)

    self.view_port = tk.Frame(self)
    self.canvas_frame = self.create_window((0,0), window=self.view_port, anchor=tk.NW)
    self.bind('<Configure>', self.on_canvas_configure)

    # handle mouse scroll
    self.bind('<Enter>', self.on_enter)
    self.bind('<Leave>', self.on_leave)


  def on_canvas_configure(self, e):
    req_width  = self.view_port.winfo_reqwidth()
    req_height = self.view_port.winfo_reqheight()

    # set the width of the canvas to the requested width of the inner frame
    self.config(width = req_width)

    # set the inner frame to expand to the available height if needed
    if req_height < e.height:
      self.itemconfig(self.canvas_frame, height=e.height)

    # set the scroll region to the requested size of the inner frame
    if e.height < req_height:
      self.scrollable = True
      self.config(scrollregion=(0, 0, req_width, req_height))
      self.scrollbar.grid()
    else:
      # no scrolling needed
      self.scrollable = False
      self.config(scrollregion=self.bbox(tk.ALL))
      self.scrollbar.grid_remove()


  def on_enter(self, event):
    # bind wheel events when the cursor enters the control
    if self.scrollable == True:
      if platform.system() == 'Linux':
        self.bind_all('<Button-4>', self.on_mouse_wheel)
        self.bind_all('<Button-5>', self.on_mouse_wheel)
      else:
        self.bind_all('<MouseWheel>', self.on_mouse_wheel)

  def on_leave(self, event):
    # unbind wheel events when the cursorl leaves the control
    if platform.system() == 'Linux':
      self.unbind_all('<Button-4>')
      self.unbind_all('<Button-5>')
    else:
      self.unbind_all('<MouseWheel>')

  def on_mouse_wheel(self, event):
    # cross platform scroll wheel event
    if platform.system() == 'Windows':
      self.yview_scroll(int(-1* (event.delta/120)), 'units')
    elif platform.system() == 'Darwin':
      self.yview_scroll(int(-1 * event.delta), 'units')
    else:
      if event.num == 4:
        self.yview_scroll( -1, 'units' )
      elif event.num == 5:
        self.yview_scroll( 1, 'units' )




if __name__ == "__main__":
  mp.freeze_support()
  app = App()
  app.mainloop()

  # global placeholder to work around multiprocessing
  pool = None