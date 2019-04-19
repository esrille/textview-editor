PROGRAM = textview-editor.py
RESOURCES = textview-editor.menu.ui \
	textview-editor.menu.ja_JP.ui textview-editor.ja_JP.json

prefix ?= /usr/local
bindir = $(prefix)/bin
applicationsdir = $(prefix)/share/applications
icondir = $(prefix)/share/icons/hicolor/96x96/apps
resourcedir = $(prefix)/share/$(patsubst %.py,%,$(PROGRAM))

all:

install:
	install -d $(bindir)
	install $(PROGRAM) $(bindir)/$(patsubst %.py,%,$(PROGRAM))
	install -d $(applicationsdir)
	install $(patsubst %.py,%.desktop,$(PROGRAM)) $(applicationsdir)
	install -d $(icondir)
	install $(patsubst %.py,%.png,$(PROGRAM)) $(icondir)
	install -d $(resourcedir)
	install $(RESOURCES) $(resourcedir)

uninstall:
	rm $(bindir)/$(patsubst %.py,%,$(PROGRAM))
	rm $(applicationsdir)/$(patsubst %.py,%.desktop,$(PROGRAM))
	rm $(icondir)/$(patsubst %.py,%.png,$(PROGRAM))
	rm $(addprefix $(resourcedir)/,$(RESOURCES))
	rmdir $(resourcedir)

.PHONY: all install uninstall
