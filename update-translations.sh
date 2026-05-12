#!/bin/bash

langs=("tr")

if ! command -v xgettext &> /dev/null
then
	echo "xgettext could not be found."
	echo "you can install the package with 'apt install gettext' command on debian."
	exit
fi


echo "updating pot file"
xgettext -o po/eta-right-click.pot `find src -type f -iname "*.py"`

for lang in ${langs[@]}; do
	if [[ -f po/$lang.po ]]; then
		echo "updating $lang.po"
		msgmerge -o po/$lang.po po/$lang.po po/eta-right-click.pot
	else
		echo "creating $lang.po"
		cp po/eta-right-click.pot po/$lang.po
	fi
done
