build:
	: do nothing
install:
	mkdir -p $(DESTDIR)/usr/share/eta/eta-right-click
	mkdir -p $(DESTDIR)/lib/systemd/system
	cp *.py $(DESTDIR)/usr/share/eta/eta-right-click/
	install -Dm644 eta-right-click.systemd  $(DESTDIR)/lib/systemd/system/eta-right-click.service