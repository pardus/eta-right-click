build:
	: do nothing
install:
	mkdir -p $(DESTDIR)/usr/share/eta/eta-right-click
	mkdir -p $(DESTDIR)/lib/systemd/system
	mkdir -p $(DESTDIR)/etc/pardus/
	cp *.py $(DESTDIR)/usr/share/eta/eta-right-click/
	install -Dm644 eta-right-click.systemd  $(DESTDIR)/lib/systemd/system/eta-right-click.service
	install -Dm644 default.conf $(DESTDIR)/etc/pardus/eta-right-click.conf