#!/bin/bash

ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)

cd ${ROOT_DIR}
PY_FILES=$(find src -name '*.py' | grep -v src/resources/libraries)

for lang in cs sk ; do
	# extract clean list of strings
	xgettext -L python $PY_FILES --no-wrap --foreign-user --package-name=enigma2-plugin-extension-archivczsk --package-version='' --copyright-holder='' -o ${lang}.pot

	# mark obsolete strings
	msgattrib --set-obsolete --ignore-file=${lang}.pot -o locale/${lang}.po locale/${lang}.po
	
	# remove obsolete strings
	msgattrib --no-obsolete -o locale/${lang}.po locale/${lang}.po
	
	# remove clean strings file
	rm ${lang}.pot
	
	# add new strings
	xgettext -L python $PY_FILES --no-wrap --foreign-user --package-name=enigma2-plugin-extension-archivczsk --package-version='' --copyright-holder='' -j -o locale/${lang}.po
done
