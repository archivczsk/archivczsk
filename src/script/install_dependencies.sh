#!/bin/sh

log_file="/tmp/archivCZSK_install_dep.txt"

DEP_PY2="rtmpdump python-importlib python-pickle python-html python-threading python-json python-zlib python-compression python-requests python-codecs python-email python-pycryptodome python-beautifulsoup4"
DEP_PY3="rtmpdump python3-pickle python3-html python3-threading python3-json python3-compression python3-requests python3-codecs python3-email python3-pycryptodome python3-beautifulsoup4"

run()
{
	echo "Script started at `date`"

	if [ -z `grep libpython3 /usr/bin/enigma2` ] ; then
		echo "Detected system based on python2"
		PKGS=$DEP_PY2
	else
		echo "Detected system based on python3"
		PKGS=$DEP_PY3
	fi
	
	if [ -f /usr/bin/dpkg ] ; then
		echo "Detected deb based system"
		LOCK_FILE="/var/lib/dpkg/lock"
		PKG_SYSTEM="apt-get"
	else
		echo "Detected ipk based system"
		LOCK_FILE="/run/opkg.lock"
		PKG_SYSTEM="opkg"
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

	echo "Installing packages ..."
	echo "Required packages: $PKGS"

	# get only available packages, because otherwise installation will fail
	if [ "$PKG_SYSTEM" = "opkg" ] ; then
		opkg update
		TO_INSTALL=$(opkg list | cut -d ' ' -f1 | grep -x -F `for p in $PKGS ; do echo -n "-e $p " ; done` | xargs echo)
		echo "Trying to install: $TO_INSTALL"
		opkg install $TO_INSTALL
	else
		apt-get -y update
		TO_INSTALL=$(apt-cache --generate pkgnames | grep -x -F `for p in $PKGS ; do echo -n "-e $p " ; done` | xargs echo)
		echo "Trying to install: $TO_INSTALL"
		apt-get -y -f install $TO_INSTALL
	fi

	echo "$PKG_SYSTEM finished"
}

run > $log_file 2>&1
