#!/usr/bin/env python

"""
    This file is part of Spike Guard.

    Spike Guard is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Spike Guard is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Spike Guard.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os
import shutil
import tarfile
import zlib
import subprocess
import urllib2
import argparse


URL_MAIN = "http://db.local.clamav.net/main.cvd"
URL_DAILY = "http://db.local.clamav.net/daily.cvd"


def download_file(url):
    """
    Downloads a file.
    Source: https://stackoverflow.com/questions/22676/how-do-i-download-a-file-over-http-using-python
    """
    file_name = url.split('/')[-1]
    u = urllib2.urlopen(url)
    outfile = open(file_name, 'wb')
    meta = u.info()
    file_size = int(meta.getheaders("Content-Length")[0])
    print "Downloading: %s Bytes: %s" % (file_name, file_size)

    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break

        file_size_dl += len(buffer)
        outfile.write(buffer)
        status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
        status = status + chr(8) * (len(status) + 1)
        print status,

    outfile.close()


def zlib_decompress(path, outpath):
    d = zlib.decompressobj(zlib.MAX_WBITS + 16)
    input = open(path, "rb")
    output = open(outpath, "wb")
    if not input or not output:
        print "[!] Error decompressing signatures."
        sys.exit(-1)

    while True:
        chunk = input.read(2048)
        if not chunk:
            break
        uncompressed = d.decompress(chunk)
        output.write(uncompressed)

    input.close()
    output.close()
    os.remove(path)


def update_signatures(url):
    # Download CVD file
    download_file(url)
    file_name = url.split('/')[-1]
    file_basename = file_name.split('.')[-2]

    # Extract signatures
    f = open(file_name, "rb")
    if not f or len(f.read(512)) != 512:  # Skip the CVD header
        print "[!] Error reading main.cvd!"
        sys.exit(-1)

    g = open("%s.tar.gz" % file_basename, "wb")
    if not g:
        f.close()
        print "[!] Error writing to %s.tar.gz!" % file_basename
        sys.exit(-1)

    # Create a copy of the virus definitions without the ClamAV header (it becomes a valid TGZ file)
    while True:
        data = f.read(2048)
        if not data:
            break
        g.write(data)

    f.close()
    g.close()

    # Excract the signatures
    zlib_decompress("%s.tar.gz" % file_basename, "%s.tar" % file_basename)
    tar = tarfile.open("%s.tar" % file_basename)
    tar.extract("%s.ndb" % file_basename)
    os.chmod("%s.ndb" % file_basename, 700)
    tar.close()
    os.remove("%s.tar" % file_basename)
    subprocess.call([sys.executable, "./clamav_to_yara.py", "-f", "%s.ndb" % file_basename, "-o", "clamav.yara"])
    os.remove("%s.ndb" % file_basename)

# Work in the script's directory
os.chdir(os.path.dirname(sys.argv[0]))

parser = argparse.ArgumentParser(description="Updates ClamAV signatures for plugin_clamav.")
parser.add_argument("--main", action="store_true", help="Update ClamAV's main signature file.")
args = parser.parse_args()

if not os.path.exists("clamav.main.yara"):
    args.main = True

if args.main:
    if os.path.exists("clamav.main.yara"):
        os.remove("clamav.main.yara")
    update_signatures(URL_MAIN)
    shutil.copy("clamav.yara", "clamav.main.yara")

try:
    os.remove("clamav.yara")
except OSError:
    pass

update_signatures(URL_DAILY)
try:
    os.remove("../../bin/yara_rules/clamav.yarac")
except OSError:
    pass
shutil.move("clamav.yara", "../../bin/yara_rules")