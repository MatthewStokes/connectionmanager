#!/usr/bin/env python

from gi.repository import Gtk, Gdk
from StringIO import StringIO

import gobject
import gconf
import os.path
import json


#   ConnectionManager 3 - Simple GUI app for Gnome 3 that provides a menu 
#   for initiating SSH/Telnet/Custom Apps connections. 
#   Copyright (C) 2011  Stefano Ciancio
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

VERSION='0.2'

# TreeStore object:
# Type, Name, Host, Profile, Protocol
treestore = Gtk.TreeStore(str, str, str, str, str)
Root = treestore.append(None, ['__folder__', 'Root', None, '', ''])


# I/O class
class ConfIO(str):

	json_output = ""

	def __init__(self, conf_file):
		self.configuration_file = conf_file

	# Decode JSON configuration
	def custom_decode(self, dct, parent=Root):

		if 'Root' in dct:
			dct = dct['Root']
		
		for child in dct:
			child = child[0]

			if child['Type'] == '__item__' or \
				 child['Type'] == '__app__' or \
				 child['Type'] == '__sep__' :
				treestore.append(parent, [child['Type'], child['Name'], 
							child['Host'], child['Profile'], child['Protocol']])

			if child['Type'] == '__folder__' :
				parent_prec = parent
				parent = treestore.append(parent, ['__folder__', 
							child['Name'], None, None, None])
				self.custom_decode(child['Children'], parent)
				parent = parent_prec

		return treestore


	def get_item(self, t, iter):
		return '[{"Type":'+json.dumps(str(t.get_value(iter, 0)))+','+ \
		'"Name":'+json.dumps(str(t.get_value(iter, 1)))+','+ \
		'"Host":'+json.dumps(str(t.get_value(iter, 2)))+','+ \
		'"Profile":'+json.dumps(str(t.get_value(iter, 3)))+','+ \
		'"Protocol":'+json.dumps(str(t.get_value(iter, 4)))+','+ \
		'"Children":[]' \
		'}]'

	def get_folder(self, t, iter):
		return '"Type":'+json.dumps(str(t.get_value(iter, 0)))+','+ \
		'"Name":'+json.dumps(str(t.get_value(iter, 1)))+','+ \
		'"Host":'+json.dumps(str(t.get_value(iter, 2)))+','+ \
		'"Profile":'+json.dumps(str(t.get_value(iter, 3)))+','+ \
		'"Protocol":'+json.dumps(str(t.get_value(iter, 4)))+','+ \
		'"Children":'


	def is_folder(self, treestore, iter):
		if treestore.get_value (iter, 0) == '__folder__':
			return True
		else:
			return False


	# Encode JSON configuration
	def custom_encode(self, t, iter):

		# If node has children
		if t.iter_has_child(iter):
	
			# Foreach child ...
			for index in range(0, t.iter_n_children(iter)):
			
				# Child pointer
				child = t.iter_nth_child(iter, index)
				if not self.is_folder(t, child):
					# Item
					self.json_output += self.get_item(t, child)
					if index+1 != t.iter_n_children(iter):
						self.json_output += ","
				else:
					# Folder
					self.json_output += "[{"+self.get_folder(t, child)+"["
					self.custom_encode(t, child)
					self.json_output += "]}]"
					if index+1 != t.iter_n_children(iter):
						self.json_output += ","

		return self.json_output


	# Read configuration
	def read(self):
		configuration = ""
		if (os.path.exists(self.configuration_file) and 
			os.path.isfile(self.configuration_file)):

			in_file = open(self.configuration_file,"r")
			configuration = self.custom_decode(json.load(in_file))
			in_file.close()
		
		else:
			print "Configuration file not exists"
			configuration = self.custom_decode(json.loads('{"Root": []}'))

		return configuration

	# Write configuration
	def write(self, treestore1):

		self.json_output = ''
		self.custom_encode(treestore1, Root)
		self.json_output = '{"Root": ['+self.json_output+']}'

		out_file = open(self.configuration_file,"w")
		json.dump(json.loads(self.json_output), out_file, indent=2)
		out_file.close()


# Main class
class ConnectionManager(Gtk.Window):

	modified = False
	status_conf = Gtk.Label('<span size="10000" color="green">Configuration saved</span>')
	status_conf.set_use_markup(True)

	tv = Gtk.TreeView()
	bad_path = None

	def fixTree(self, model, path, iter, user_data):
		piter = model.iter_parent(iter)

		if piter:
			if (self.is_item(piter) or self.is_sep(piter)):
				self.bad_path = model.get_path(iter)
			
		elif (self.treestore.get_value(iter, 1) != 'Root'): # Root
			self.bad_path = model.get_path(iter)

	def checkValidity(self):
		model, iter = self.tv.get_selection().get_selected()

		self.bad_path = None
		treestore.foreach(self.fixTree, '')
		
		if self.bad_path:
			dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
				Gtk.ButtonsType.OK, "Configuration Error! ")
			dialog.format_secondary_text("The destination is not a folder. \
This involves loss of information, it is recommended to cancel it.")
			dialog.show_all()
			response = dialog.run()
			if response == Gtk.ResponseType.OK:
				dialog.destroy()
				return False


	def drag_drop_cb(self, treeview, dragcontext, x, y, time):
		gobject.timeout_add(50, self.checkValidity)
		self.set_conf_modified(True)

	## ------------------------------------------------------


	def __init__(self):
		Gtk.Window.__init__(self, title="ConnectionManager 3 - Preferences")

		self.set_default_size(450, 400)
		self.connect("delete-event", self.on_click_me_close)

		# ---------------------------------------------
		# Define input
		self.treestore = Gtk.TreeStore(str, str, str, str)
		# ---------------------------------------------	

		conf_file = os.getenv("HOME") + "/.connmgr"
		self.configuration = ConfIO(conf_file)

		# Read Configuration
		self.treestore = self.configuration.read()

		# ---------------------------------------------


		# TreeView
		self.tv.set_model(self.treestore)
		self.tv.set_reorderable(True)
		# self.tv.expand_all()
		self.tv.set_level_indentation(5)
		self.tv.set_show_expanders(True)

		# Signal on TreeView
		self.tv.connect("button_press_event", self.treeview_clicked)
		self.tv.connect("drag_drop", self.drag_drop_cb)

		renderer = [0, 1, 2, 3];
		column = [0, 1, 2, 3];
		title = ["Title"]

		# Design field
		for index, item in enumerate(title):
			renderer[index+1] = Gtk.CellRendererText()
			column[index+1] = Gtk.TreeViewColumn(item, renderer[index+1], text=index+1)
			self.tv.append_column(column[index+1])
	
		# Buttons
		button1 = Gtk.Button("Add Host")
		button1.connect("clicked", self.on_click_me_addhost)
		button2 = Gtk.Button("Add App")
		button2.connect("clicked", self.on_click_me_addapp)
		button3 = Gtk.Button("Add Separator")
		button3.connect("clicked", self.on_click_me_addsep)
		button4 = Gtk.Button("Add SubMenu")
		button4.connect("clicked", self.on_click_me_addmenu)
		button5 = Gtk.Button("Remove")
		button5.connect("clicked", self.on_click_me_remove)
		button6 = Gtk.Button("Save Conf")
		button6.connect("clicked", self.on_click_me_saveconf)
		button7 = Gtk.Button("Close")
		button7.connect("clicked", self.on_click_me_close)

		# Specific Buttons
		SpecButtons = Gtk.VButtonBox(spacing=6)
		SpecButtons.set_layout(3)
		SpecButtons.add(button1)
		SpecButtons.add(button2)
		SpecButtons.add(button3)
		SpecButtons.add(button4)
		SpecButtons.add(button5)
		SpecButtons.add(button6)
	
		ExtButtons = Gtk.HButtonBox(margin_right=15, margin_bottom=6)
		ExtButtons.set_layout(4)
		ExtButtons.add(button7)
		# ButtonBox
	
		# UI design
		scrolled_window = Gtk.ScrolledWindow(hadjustment=None, vadjustment=None)
		scrolled_window.add_with_viewport(self.tv)

		mybox = Gtk.HBox()
		mybox.pack_start(scrolled_window, True, True, 6)
		mybox.pack_start(SpecButtons, False, False, 6)
	
#		# Options Label
#		options = Gtk.Label('<span size="20000">Under Construction</span>')
#		options.set_justify(2)
#		options.set_use_markup(True)

	
		# About Label
		label_about = Gtk.Label('<span size="30000">ConnectionManager 3</span>\n<span>Version: '+VERSION+'\n\nSimple GUI app for Gnome 3 that provides\n a menu for initiating SSH/Telnet/Custom Apps connections.\n\nhttps://github.com/sciancio/connectionmanager\n\nCopyright 2011 Stefano Ciancio</span>')
		label_about.set_justify(2)
		label_about.set_use_markup(True)
			          
		# Notebook
		notebook = Gtk.Notebook()
		notebook.set_tab_pos(2)
		notebook.set_scrollable(True)

		notebook.append_page(mybox, Gtk.Label("Hosts"))
#		notebook.append_page(options, Gtk.Label("Options"))
		notebook.append_page(label_about, Gtk.Label("About"))
		notebook.set_current_page(0)

		# External Box
		ExtBox = Gtk.VBox()
		ExtBox.pack_start(notebook, True, True, 0)
		ExtBox.pack_start(self.status_conf, False, False, 0)
		ExtBox.pack_end(ExtButtons, False, False, 0)

		self.add(ExtBox)

	def set_conf_modified(self, status):
		self.modified = status
		if self.modified:
			self.status_conf.set_text('<span size="10000" color="red">Configuration unsaved</span>')
		else:
			self.status_conf.set_text('<span size="10000" color="green">Configuration saved</span>')
		self.status_conf.set_use_markup(True)
		self.status_conf.set_justify(Gtk.Justification.LEFT)


	# Add Element (item, separator, folder)
	def __addElement(self, newrow):
		model, current_iter = self.tv.get_selection().get_selected()
		if current_iter: 
		
			if self.is_folder(current_iter):
			
				if newrow[0] == '__folder__' or newrow[0] == '__item__' or newrow[0] == '__app__':
					response, row = self.item_dialog(newrow)
					if response:
						new_iter = self.treestore.insert_after(current_iter, None, row)
						self.set_conf_modified(True)
				if newrow[0] == '__sep__':
						new_iter = self.treestore.insert_after(current_iter, None, newrow)
						self.set_conf_modified(True)

			if self.is_item(current_iter) or self.is_app(current_iter) or self.is_sep(current_iter):
				if newrow[0] == '__folder__' or newrow[0] == '__item__' or newrow[0] == '__app__':
					response, row = self.item_dialog(newrow)
					if response:
						new_iter = self.treestore.insert_after(None, current_iter, row)
						self.set_conf_modified(True)
				if newrow[0] == '__sep__':
					new_iter = self.treestore.insert_after(None, current_iter, newrow)
					self.set_conf_modified(True)

		else:
			dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
					Gtk.ButtonsType.OK, "Please, select an element")
			dialog.show_all()
			response = dialog.run()
			if response == Gtk.ResponseType.OK:
				dialog.destroy()
				return True
			

	# Add Host
	def on_click_me_addhost(self, button):
		newrow = ['__item__', 'New Host ...', '-AX ...', 'Default', 'ssh']
		self.__addElement(newrow)

	# Add App
	def on_click_me_addapp(self, button):
		newrow = ['__app__', 'New App ...', '', '', '']
		self.__addElement(newrow)
	
	
	# Add Separator
	def on_click_me_addsep(self, button):
		newrow = ['__sep__', '_____________________', '', '', '']
		self.__addElement(newrow)

	# Add SubMenu
	def on_click_me_addmenu(self, button):
		newrow = ['__folder__', 'New Folder ...', '', '', '']
		self.__addElement(newrow)
	

	# Remove element (item or folder)
	def on_click_me_remove(self, button):
		model, current_iter = self.tv.get_selection().get_selected()

		if current_iter:
			if model.iter_parent(current_iter) == None:
				return

			if self.is_folder(current_iter):
				dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.WARNING,
				Gtk.ButtonsType.YES_NO, "Are you sure remove folder?")

				response = dialog.run()
				if response == Gtk.ResponseType.YES:
					self.treestore.remove(current_iter)
					self.set_conf_modified(True)

				dialog.destroy()
			
			else:
				self.treestore.remove(current_iter)
				self.set_conf_modified(True)
				
		else: 
			dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
					Gtk.ButtonsType.OK, "Please, select an element")
			dialog.show_all()
			response = dialog.run()
			if response == Gtk.ResponseType.OK:
				dialog.destroy()
				return True



	# Save configuration
	def on_click_me_saveconf(self, button):
		self.configuration.write(self.treestore)
		self.set_conf_modified(False)

	# Close
	def on_click_me_close(self, button, event=None):

		if self.modified:

			dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.WARNING,
			Gtk.ButtonsType.NONE, "Save changes to configuration before closing?")
			dialog.format_secondary_text(
			"If you don't save, changes will be permanently lost.")

			dialog.add_button("Close without Saving", Gtk.ResponseType.CLOSE)
			dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
			dialog.add_button("Save&Close", Gtk.ResponseType.OK)
			response = dialog.run()
			if response == Gtk.ResponseType.OK:
				self.configuration.write(self.treestore)
				Gtk.main_quit()

			elif response == Gtk.ResponseType.CANCEL:
				dialog.destroy()
				return True
			
			elif response == Gtk.ResponseType.CLOSE:
				Gtk.main_quit()

			dialog.destroy()
		
		else:
			Gtk.main_quit()
		


	def is_folder(self, iter):
		if self.treestore.get_value (iter, 0) == '__folder__':
			return True
		else:
			return False

	def is_item(self, iter):
		if self.treestore.get_value (iter, 0) == '__item__':
			return True
		else:
			return False

	def is_app(self, iter):
		if self.treestore.get_value (iter, 0) == '__app__':
			return True
		else:
			return False

	def is_sep(self, iter):
		if self.treestore.get_value (iter, 0) == '__sep__':
			return True
		else:
			return False


	def item_dialog(self, row):

		model, current_iter = self.tv.get_selection().get_selected()

		dialog = Gtk.Dialog("Connection Details", self, 0,
		(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
		Gtk.STOCK_OK, Gtk.ResponseType.OK))

		dialog.set_default_size(150, 100)
		dialog.set_modal(True)

		box = dialog.get_content_area()
		box.set_border_width(8)

		label1 = Gtk.Label("Title")
		entry1 = Gtk.Entry()
		entry1.set_text(row[1])
	
		label2 = Gtk.Label("Host")
		entry2 = Gtk.Entry()
		entry2.set_text(row[2])
	
		# Profile Combo ----------------------------
		label3 = Gtk.Label("Profile")

		# GConf key for retrieving a list of terminal profiles.
		GnomeTermProfiles = "/apps/gnome-terminal/global/profile_list"
		# GConf key template to get visible name for a profile.
		GnomeTermProfName = "/apps/gnome-terminal/profiles/%s/visible_name"

		client = gconf.client_get_default ()
		names = client.get_list(GnomeTermProfiles, 1)
	
		entry3 = Gtk.ComboBoxText()
		for index, item in enumerate(names):
			profile = client.get_string(GnomeTermProfName.replace('%s', item))
			entry3.append_text(profile)
			if profile == row[3]:
				entry3.set_active(index)
		
		entry3.set_entry_text_column(0)
		# ----------------------------
		
		label4 = Gtk.Label("Protocol")
		entry4 = Gtk.ComboBoxText()
		protocol = ['ssh', 'telnet']
		for index, item in enumerate(protocol):
			entry4.append_text(item)
			if item == row[4]:
				entry4.set_active(index)
		
		entry4.set_entry_text_column(0)

		label5 = Gtk.Label("Command")
		entry5 = Gtk.Entry()
		entry5.set_text(row[2])
		button5 = Gtk.Button("Choose File")
		button5.connect("clicked", self.on_choose_file, entry5)

		check7 = Gtk.CheckButton("Execute in shell")
		if row[4] == 'True':
			check7.set_active(True)


		if row[0] == '__folder__':
			table = Gtk.Table(1, 2, True, 
			margin_right=15, margin_bottom=15, margin_top=15)
			table.attach(label1, 0, 1, 0, 1)
			table.attach(entry1, 1, 2, 0, 1)

		if row[0] == '__item__':
			table = Gtk.Table(4, 2, True, 
				margin_right=15, margin_bottom=15,
				margin_top=15)
			table.set_row_spacings(6)
			table.set_col_spacings(6)
	
			table.attach(label1, 0, 1, 0, 1)
			table.attach(entry1, 1, 2, 0, 1)
	
			table.attach(label2, 0, 1, 1, 2)
			table.attach(entry2, 1, 2, 1, 2)
	
			table.attach(label3, 0, 1, 2, 3)
			table.attach(entry3, 1, 2, 2, 3)
			table.attach(label4, 0, 1, 3, 4)
			table.attach(entry4, 1, 2, 3, 4)

		if row[0] == '__app__':
			table = Gtk.Table(4, 2, True, 
				margin_right=15, margin_bottom=15,
				margin_top=15)
			table.set_row_spacings(6)
			table.set_col_spacings(6)
	
			table.attach(label1, 0, 1, 0, 1)
			table.attach(entry1, 1, 2, 0, 1)
	
			table.attach(label5, 0, 1, 1, 2)
			table.attach(entry5, 1, 2, 1, 2)
			table.attach(button5, 1, 2, 2, 3)
			table.attach(check7, 1, 2, 3, 4)

		box.add(table)
		dialog.show_all()

		while 1:
			response = dialog.run()
			if response == Gtk.ResponseType.OK:
		
				if row[0] == '__folder__':
					newrow = [row[0], entry1.get_text(), row[2], row[3], row[4]]
					if entry1.get_text() != '':
						dialog.destroy()
						return True, newrow
					else:
						edialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
							Gtk.ButtonsType.OK, "You must enter a title")
						edialog.show_all()
						eresponse = edialog.run()
						if eresponse == Gtk.ResponseType.OK:
							edialog.destroy()
					
				if row[0] == '__item__':
					newrow = [row[0], entry1.get_text(), entry2.get_text(), 
						entry3.get_active_text(), entry4.get_active_text()]
					if entry1.get_text() != '' and entry2.get_text() != '':
						dialog.destroy()
						return True, newrow
					else:
						edialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
							Gtk.ButtonsType.OK, "You must enter a title/host")
						edialog.show_all()
						eresponse = edialog.run()
						if eresponse == Gtk.ResponseType.OK:
							edialog.destroy()

				if row[0] == '__app__':
					newrow = [row[0], entry1.get_text(), entry5.get_text(), 
						row[3], str(check7.get_active())]
					if entry1.get_text() != '' and entry5.get_text() != '':
						dialog.destroy()
						return True, newrow
					else:
						edialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
							Gtk.ButtonsType.OK, "You must enter a title/command")
						edialog.show_all()
						eresponse = edialog.run()
						if eresponse == Gtk.ResponseType.OK:
							edialog.destroy()
		
			if response == Gtk.ResponseType.CANCEL:
				newrow = row
				dialog.destroy()
				return False, row



	def treeview_clicked(self, treeview, event=None):
		if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
			model, current_iter = treeview.get_selection().get_selected()

			# Root
			if model.iter_parent(current_iter) == None:
				return
			
			# Separator
			if model.get_value(current_iter, 0) == '__sep__':
				return


			currentrow = [str(model.get_value(current_iter, 0)), 
				str(model.get_value(current_iter, 1)),
				str(model.get_value(current_iter, 2)),
				str(model.get_value(current_iter, 3)),
				str(model.get_value(current_iter, 4))]
		
			response, newrow = self.item_dialog(currentrow)
		
			if response:
				model.set_value(current_iter, 1, newrow[1])
				model.set_value(current_iter, 2, newrow[2])
				model.set_value(current_iter, 3, newrow[3])
				model.set_value(current_iter, 4, newrow[4])
				self.set_conf_modified(True)

			return True

	def on_choose_file(self, widget, entry):
		dialog = Gtk.FileChooserDialog("Please choose a file", self,
			Gtk.FileChooserAction.OPEN,
			(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
			Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

		response = dialog.run()
		if response == Gtk.ResponseType.OK:
			entry.set_text(dialog.get_filename())

		dialog.destroy()


win = ConnectionManager() 
win.show_all()
Gtk.main()


