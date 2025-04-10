#!/bin/sh

log_file="/tmp/archivCZSK_install_dep.txt"

DEP_PY2="rtmpdump python-importlib python-pickle python-html python-threading python-json python-zlib python-compression python-requests python-codecs python-email python-pycrypto python-pycryptodome python-beautifulsoup4"
DEP_PY3="rtmpdump python3-pickle python3-html python3-threading python3-json python3-compression python3-requests python3-codecs python3-email python3-pycryptodome python3-beautifulsoup4"

run()
{
	echo "Script started at `date`"

	if [ `python -V | cut -d ' ' -f 2 | cut -d '.' -f1` = 3 ]; then
		echo "Detected system based on python3"
		PKGS=$DEP_PY3
	else
		echo "Detected system based on python2"
		PKGS=$DEP_PY2
	fi

	if [ -f /usr/bin/dpkg ] ; then
		echo "Detected deb based system"
		LOCK_FILE="/var/lib/dpkg/lock"
		PKG_SYSTEM="apt-get"
		UPDATE_CMD="apt-get -y update"
		INSTALL_CMD="apt-get -y -f install"
		GET_PKGS="apt-cache --generate pkgnames"
	else
		echo "Detected ipk based system"
		LOCK_FILE="/run/opkg.lock"
		PKG_SYSTEM="opkg"
		UPDATE_CMD="opkg update"
		INSTALL_CMD="opkg install"
		GET_PKGS="opkg list"
	fi

	for i in `seq 60`; do
		sleep 1

		if [ "$PKG_SYSTEM" = "opkg" ] ; then
			if [ -f $LOCK_FILE ] ; then
				LOCKED=1
			else
				LOCKED=0
			fi
		else
			if [ "`dpkg -i $LOCK_FILE 2>&1 | grep locked`" = "" ]; then
				LOCKED=0
			else
				LOCKED=1
			fi
		fi

		if [ $LOCKED = 1 ] ; then
			echo "Package system locked. Waiting ..."
		else
			echo "Package system not locked. Let's continue ..."
			break
		fi
	done

	# now package system is either unlocked or not and then everything will fail
	# but we don't want to wait here forever ...

	echo "Running $PKG_SYSTEM update"
	$UPDATE_CMD

	echo "Required packages: $PKGS"

	# get only available packages, because otherwise installation will fail
	TO_INSTALL=$($GET_PKGS | cut -d ' ' -f1 | grep -x -F `for p in $PKGS ; do echo -n "-e $p " ; done` | xargs echo)

	# check, because python-pycrypto and python-pycryptodome can't be installed at the same time
	if [ ! -z `echo $TO_INSTALL | grep -o -w 'python-pycryptodome'` ] ; then
		# if pycryptodome is available, then don't try to install pycrypto
		TO_INSTALL=$(for p in ${TO_INSTALL} ; do if [ $p != python-pycrypto ] ; then echo -n "$p " ; fi ; done | xargs echo)
	fi

	echo "Trying to install: $TO_INSTALL"
	$INSTALL_CMD $TO_INSTALL

	echo "$PKG_SYSTEM finished"
}

run > $log_file 2>&1
