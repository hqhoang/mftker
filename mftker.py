#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# License : GPLv3 : http://gplv3.fsf.org/


import tkinter as tk
import tkinter.filedialog
import tkinter.font
from tkinter import ttk
from PIL import ImageTk, Image

import os, sys
import configparser

class App(tk.Tk):
   
  
  def __init__(self):
    super().__init__()

    # instance variables
    self.input_photos = [] # list of filenames
    self.widgets = {}      # list of widgets
    self.config  = {}      # configurations
    
    self.load_config()

    
    self.title('MacroFusionTk')
    self.geometry('1600x1000')
    self.resizable(True, True)
    
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)
    
    # set up font and style    
    style = ttk.Style()
    style.theme_settings("default", {"TNotebook.Tab": {"configure": {"padding": [40, 5]}}})
    
    default_font = tk.font.nametofont("TkDefaultFont")
    default_font.configure(size=11)
    
    container = ttk.Frame(self)
    container.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)
    
    
    # create 3 tabs
    nb = ttk.Notebook(container)         
    nb.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    nb.columnconfigure(0, weight=1)
    nb.rowconfigure(0, weight=1)
  
    tab_photos = ttk.Frame(nb)
    tab_masks  = ttk.Frame(nb)
    tab_stack  = ttk.Frame(nb)
    
    tab_photos.grid(column=0, row=0, sticky=(tk.NS, tk.EW))
      
    nb.add(tab_photos, text='Photos')
    nb.add(tab_masks, text='Masks')
    nb.add(tab_stack, text='Stack')
    
    
    # set up Photos/Files tab
    w = self.widgets # shorthand
    
    w['lb_photos'] = tk.Listbox(tab_photos, width=50, selectmode='extended')
    w['lb_photos'].grid(column=0, row=0, sticky=(tk.NS))    
    w['lb_photos'].bind('<<ListboxSelect>>', self.update_input_photo_preview)
        
    w['cv_photo_preview'] = tk.Canvas(tab_photos, background='#ffeeee')
    w['cv_photo_preview'].grid(column=1, row=0, sticky="ns,ew")
    
    tab_photos.rowconfigure(0, weight=1)
    tab_photos.columnconfigure(1, weight=1)
    
    fr_photo_actions = ttk.Frame(tab_photos)
    fr_photo_actions.grid(column=0, row=1, sticky="ew,s")
    
    w['bt_photo_add'] = ttk.Button(fr_photo_actions, text='Add photos', command=self.add_photos)
    w['bt_photo_add'].grid(column=0, row=0, padx=10, pady=10, ipadx=3)
    
    w['bt_photo_remove'] = ttk.Button(fr_photo_actions, text='Remove selected', command=self.remove_photos)
    w['bt_photo_remove'].grid(column=1, row=0, padx=10, pady=10, ipadx=3)
    
    
  def add_photos(self):
    initial_dir = '~'
    
    if 'prefs' in self.config and 'last_opened_location' in self.config['prefs']:
      initial_dir = self.config['prefs']['last_opened_location']
    
    filenames = tk.filedialog.askopenfilenames(title='Add photos', initialdir=initial_dir, filetypes=[
              ('image', '.jpg'),
              ('image', '.jpeg'),
              ('image', '.png'),
              ('image', '.tif'),
              ('image', '.tiff')
            ])
    
    if len(filenames) == 0:
      return
    
    print('Path: ' + os.path.dirname(filenames[0]))
        
    # save the current location
    self.config.set('prefs', 'last_opened_location', os.path.dirname(filenames[0]))    
    
    # update the photo list    
    for filename in filenames:
      self.widgets['lb_photos'].insert('end', os.path.basename(filename))
      self.input_photos.append(filename)

      
  def remove_photos(self):
    selection = self.widgets['lb_photos'].curselection()
    
    for i in reversed(selection):
      self.input_photos.pop(i)
      self.widgets['lb_photos'].delete(i)
            
  
  def update_input_photo_preview(self):
    # preview the last clicked on input photo
    return    
  
  
    
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
    
    
    
    
    
    