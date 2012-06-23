#
# Thumbs.py -- Thumbnail plugin for fits viewer
# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Jun 22 13:44:53 HST 2012
#]
#
# Copyright (c) 2011-2012, Eric R. Jeschke.  All rights reserved.
# This is open-source software licensed under a BSD license.
# Please see the file LICENSE.txt for details.
#
import FitsImageGtk as FitsImageGtk
import GingaPlugin

import gtk
import time

import Bunch


class Thumbs(GingaPlugin.GlobalPlugin):

    def __init__(self, fv):
        # superclass defines some variables for us, like logger
        super(Thumbs, self).__init__(fv)

        # For thumbnail pane
        self.thumbDict = {}
        self.thumbList = []
        self.thumbRowList = []
        self.thumbNumRows = 20
        self.thumbNumCols = 1
        self.thumbColCount = 0
        # distance in pixels between thumbs
        self.thumbSep = 15
        # max length of thumb on the long side
        self.thumbWidth = 150

        self.keywords = ['OBJECT', 'FRAMEID', 'UT', 'DATE-OBS']

        fv.set_callback('add-image', self.add_image)
        fv.set_callback('delete-channel', self.delete_channel)

    def initialize(self, container):
        width, height = 300, 300
        cm, im = self.fv.cm, self.fv.im

        self.thumb_generator = FitsImageGtk.FitsImageGtk(logger=self.logger)
        self.thumb_generator.configure(200, 200)
        self.thumb_generator.enable_autoscale('on')
        self.thumb_generator.enable_autolevels('on')
        self.thumb_generator.set_zoom_limits(-100, 10)

        sw = gtk.ScrolledWindow()
        sw.set_border_width(2)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        # Create thumbnails pane
        vbox = gtk.VBox(spacing=14)
        vbox.set_border_width(4)
        self.w.thumbs = vbox
        sw.add_with_viewport(vbox)
        sw.show_all()
        self.w.thumbs_scroll = sw
        self.w.thumbs_scroll.connect("size_allocate", self.thumbpane_resized)
        #nb.connect("size_allocate", self.thumbpane_resized)

        # TODO: should this even have it's own scrolled window?
        container.pack_start(sw, fill=True, expand=True)


    def add_image(self, viewer, chname, image):
        noname = 'Noname' + str(time.time())
        name = image.get('name', noname)
        path = image.get('path', None)
        thumbname = name
        if '.' in thumbname:
            thumbname = thumbname.split('.')[0]
            
        # Is this thumbnail already in the list?
        # TODO: does not handle two separate images with the same name!!
        if self.thumbDict.has_key(name):
            return

        # Is there a preference set to avoid making thumbnails?
        chinfo = self.fv.get_channelInfo(chname)
        prefs = chinfo.prefs
        if prefs.has_key('genthumb') and (not prefs['genthumb']):
            return
        
        data = image.get_data()
        # Get metadata for mouse-over tooltip
        header = image.get_header()
        metadata = {}
        for kwd in self.keywords:
            metadata[kwd] = header.get(kwd, 'N/A')

        self.thumb_generator.set_data(data)
        imgwin = self.thumb_generator.get_image_as_widget()

        imgwin.set_property("has-tooltip", True)
        imgwin.connect("query-tooltip", lambda tw, x, y, kbmode, ttw: self.query_thumb(metadata, x, y, ttw))

        vbox = gtk.VBox(spacing=0)
        vbox.pack_start(gtk.Label(thumbname), expand=False,
                        fill=False, padding=0)
        evbox = gtk.EventBox()
        evbox.add(imgwin)
        evbox.connect("button-press-event",
                      lambda w, e: self.fv.switch_name(chname, name,
                                                       path=path))
        vbox.pack_start(evbox, expand=False, fill=False)
        vbox.show_all()

        bnch = Bunch.Bunch(widget=vbox)

        if self.thumbColCount == 0:
            hbox = gtk.HBox(homogeneous=True, spacing=self.thumbSep)
            self.w.thumbs.pack_start(hbox)
            self.thumbRowList.append(hbox)

        else:
            hbox = self.thumbRowList[-1]

        hbox.pack_start(bnch.widget)
        self.thumbColCount = (self.thumbColCount + 1) % self.thumbNumCols

        self.w.thumbs.show_all()
        
        self.thumbDict[name] = bnch
        self.thumbList.append(name)
        # force scroll to bottom of thumbs
        adj_w = self.w.thumbs_scroll.get_vadjustment()
        max = adj_w.get_upper()
        adj_w.set_value(max)

    def rebuild_thumbs(self):
        # Remove old rows
        for hbox in self.thumbRowList:
            children = hbox.get_children()
            for child in children:
                hbox.remove(child)
            self.w.thumbs.remove(hbox)

        # Add thumbs back in by rows
        self.thumbRowList = []
        colCount = 0
        hbox = None
        for name in self.thumbList:
            self.logger.debug("adding thumb for %s" % (name))
            bnch = self.thumbDict[name]
            if colCount == 0:
                hbox = gtk.HBox(homogeneous=True, spacing=self.thumbSep)
                hbox.show()
                self.w.thumbs.pack_start(hbox)
                self.thumbRowList.append(hbox)

            hbox.pack_start(bnch.widget)
            hbox.show_all()
            colCount = (colCount + 1) % self.thumbNumCols

        self.thumbColCount = colCount
        self.w.thumbs.show_all()
        
    def update_thumbs(self, nameList):
        
        # Remove old thumbs that are not in the dataset
        invalid = set(self.thumbList) - set(nameList)
        if len(invalid) > 0:
            for name in invalid:
                self.thumbList.remove(name)
                del self.thumbDict[name]

            self.rebuild_thumbs()


    def thumbpane_resized(self, widget, allocation):
        x, y, width, height = self.w.thumbs_scroll.get_allocation()
        self.logger.debug("rebuilding thumbs width=%d" % (width))

        cols = max(1, width // (self.thumbWidth + self.thumbSep))
        if self.thumbNumCols == cols:
            # If we have not actually changed the possible number of columns
            # then don't do anything
            return False
        self.logger.debug("column count is now %d" % (cols))
        self.thumbNumCols = cols

        self.rebuild_thumbs()
        return False
        
    def query_thumb(self, metadata, x, y, ttw):
        objtext = 'Object: UNKNOWN'
        try:
            objtext = 'Object: ' + metadata['OBJECT']
        except Exception, e:
            self.logger.error("Couldn't determine OBJECT name: %s" % str(e))

        uttext = 'UT: UNKNOWN'
        try:
            uttext = 'UT: ' + metadata['UT']
        except Exception, e:
            self.logger.error("Couldn't determine UT: %s" % str(e))

        name = metadata.get('FRAMEID', 'Noname')
        s = "%s\n%s\n%s" % (name, objtext, uttext)
        ttw.set_text(s)
            
        return True

    def clear(self):
        self.thumbList = []
        self.thumbDict = {}
        self.rebuild_thumbs()
        
    def delete_channel(self, viewer, chinfo):
        """Called when a channel is deleted from the main interface.
        Parameter is chinfo (a bunch)."""
        chname = chinfo.name
        # TODO: delete thumbs for this channel!
        self.logger.info("TODO: delete thumbs for channel '%s'" % (
            chname))
        
    def __str__(self):
        return 'thumbs'
    
#END