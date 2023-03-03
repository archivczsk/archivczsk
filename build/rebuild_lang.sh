#!/bin/bash

ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)

cd ${ROOT_DIR}
PY_FILES=$(find src -name '*.py' | grep -v src/resources/libraries)

for lang in cs sk ; do
	# extract clean list of strings
	xgettext -L python $PY_FILES --no-wrap --foreign-user --package-name=enigma2-plugin-extension-archivczsk --package-version='' --copyright-holder='' -o ${lang}.pot
	
	# merge old translated strings to clean list
	msgmerge -U --no-wrap -N --backup=none --lang=${lang} locale/${lang}.po ${lang}.pot
	
	# remove clean strings file
	rm ${lang}.pot
done
