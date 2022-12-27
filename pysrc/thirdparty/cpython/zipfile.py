"""
! This source file comes from CPython standard library, with modification

Read and write ZIP files.

XXX references to utf-8 need further investigation.
"""
import io
import itertools
import os
import shutil
import stat
import struct
import sys
import threading
import time
import zlib

crc32 = zlib.crc32

__all__ = [
    "BadZipFile",
    "ZIP_STORED",
    "ZipInfo",
    "ZipFile",
    "LargeZipFile",
]


class BadZipFile(Exception):
    pass


class LargeZipFile(Exception):
    """
    Raised when writing a zipfile, the zipfile requires ZIP64 extensions
    and those extensions are disabled.
    """


ZIP64_LIMIT = (1 << 31) - 1
ZIP_FILECOUNT_LIMIT = (1 << 16) - 1
ZIP_MAX_COMMENT = (1 << 16) - 1

# constants for Zip file compression methods
ZIP_STORED = 0
# Other ZIP compression methods not supported

DEFAULT_VERSION = 20
ZIP64_VERSION = 45
BZIP2_VERSION = 46
LZMA_VERSION = 63
# we recognize (but not necessarily support) all features up to that version
MAX_EXTRACT_VERSION = 63

# Below are some formats and associated data for reading/writing headers using
# the struct module.  The names and structures of headers/records are those used
# in the PKWARE description of the ZIP file format:
#     http://www.pkware.com/documents/casestudies/APPNOTE.TXT
# (URL valid as of January 2008)

# The "end of central directory" structure, magic number, size, and indices
# (section V.I in the format document)
structEndArchive = b"<4s4H2LH"
stringEndArchive = b"PK\005\006"
sizeEndCentDir = struct.calcsize(structEndArchive)

# The "central directory" structure, magic number, size, and indices
# of entries in the structure (section V.F in the format document)
structCentralDir = "<4s4B4HL2L5H2L"
stringCentralDir = b"PK\001\002"
sizeCentralDir = struct.calcsize(structCentralDir)

# The "local file header" structure, magic number, size, and indices
# (section V.A in the format document)
structFileHeader = "<4s2B4HL2L2H"
stringFileHeader = b"PK\003\004"
sizeFileHeader = struct.calcsize(structFileHeader)

_FH_SIGNATURE = 0
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11

# The "Zip64 end of central directory locator" structure, magic number, and size
structEndArchive64Locator = "<4sLQL"
stringEndArchive64Locator = b"PK\x06\x07"
sizeEndCentDir64Locator = struct.calcsize(structEndArchive64Locator)

# The "Zip64 end of central directory" record, magic number, size, and indices
# (section V.G in the format document)
structEndArchive64 = "<4sQ2H2L4Q"
stringEndArchive64 = b"PK\x06\x06"
sizeEndCentDir64 = struct.calcsize(structEndArchive64)

_DD_SIGNATURE = 0x08074B50

_EXTRA_FIELD_STRUCT = struct.Struct("<HH")


def _strip_extra(extra, xids):
    # Remove Extra Fields with specified IDs.
    unpack = _EXTRA_FIELD_STRUCT.unpack
    modified = False
    buffer = []
    start = i = 0
    while i + 4 <= len(extra):
        xid, xlen = unpack(extra[i : i + 4])
        j = i + 4 + xlen
        if xid in xids:
            if i != start:
                buffer.append(extra[start:i])
            start = j
            modified = True
        i = j
    if not modified:
        return extra
    return b"".join(buffer)


class ZipInfo(object):
    """Class with attributes describing each file in the ZIP archive."""

    __slots__ = (
        "orig_filename",
        "filename",
        "date_time",
        "comment",
        "extra",
        "create_system",
        "create_version",
        "extract_version",
        "reserved",
        "flag_bits",
        "volume",
        "internal_attr",
        "external_attr",
        "header_offset",
        "CRC",
        "compress_size",
        "file_size",
        "_raw_time",
    )

    def __init__(self, filename="NoName", date_time=(1980, 1, 1, 0, 0, 0)):
        self.init(filename, date_time)

    def init(self, filename, date_time):
        self.orig_filename = filename  # Original file name in archive

        # Terminate the file name at the first null byte.  Null bytes in file
        # names are used as tricks by viruses in archives.
        null_byte = filename.find(chr(0))
        if null_byte >= 0:
            filename = filename[0:null_byte]
        # This is used to ensure paths in generated ZIP files always use
        # forward slashes as the directory separator, as required by the
        # ZIP format specification.
        if os.sep != "/" and os.sep in filename:
            filename = filename.replace(os.sep, "/")

        self.filename = filename  # Normalized file name
        # self.date_time = date_time  # year, month, day, hour, min, sec
        self.date_time = (2020, 1, 1, 1, 1, 1)
        # print(self.filename, self.date_time)

        # if date_time[0] < 1980:
        #     raise ValueError("ZIP does not support timestamps before 1980")

        # Standard values:
        self.comment = b""  # Comment for each file
        self.extra = b""  # ZIP extra data
        if sys.platform == "win32":
            self.create_system = 0  # System which created ZIP archive
        else:
            # Assume everything else is unix-y
            self.create_system = 3  # System which created ZIP archive
        self.create_version = DEFAULT_VERSION  # Version which created ZIP archive
        self.extract_version = DEFAULT_VERSION  # Version needed to extract archive
        self.reserved = 0  # Must be zero
        self.flag_bits = 0  # ZIP flag bits
        self.volume = 0  # Volume number of file header
        self.internal_attr = 0  # Internal attributes
        self.external_attr = 0  # External file attributes
        # Other attributes are set by class ZipFile:
        self.header_offset = 0  # Byte offset to the file header
        self.CRC = 0  # CRC-32 of the uncompressed file
        self.compress_size = 0  # Size of the compressed file
        self.file_size = 0  # Size of the uncompressed file

    def __repr__(self):
        result = ["<%s filename=%r" % (self.__class__.__name__, self.filename)]
        hi = self.external_attr >> 16
        lo = self.external_attr & 0xFFFF
        if hi:
            result.append(" filemode=%r" % stat.filemode(hi))
        if lo:
            result.append(" external_attr=%#x" % lo)
        isdir = self.is_dir()
        if not isdir or self.file_size:
            result.append(" file_size=%r" % self.file_size)
        result.append(">")
        return "".join(result)

    def FileHeader(self, zip64=None):
        """Return the per-file header as a bytes object."""
        dt = self.date_time
        dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
        dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
        if self.flag_bits & 0x08:
            # Set these to zero because we write them after the file data
            CRC = compress_size = file_size = 0
        else:
            CRC = self.CRC
            compress_size = self.compress_size
            file_size = self.file_size

        extra = self.extra

        min_version = 0
        if zip64 is None:
            zip64 = file_size > ZIP64_LIMIT or compress_size > ZIP64_LIMIT
        if zip64:
            fmt = "<HHQQ"
            extra = extra + struct.pack(fmt, 1, struct.calcsize(fmt) - 4, file_size, compress_size)
        if file_size > ZIP64_LIMIT or compress_size > ZIP64_LIMIT:
            if not zip64:
                raise LargeZipFile("Filesize would require ZIP64 extensions")
            # File is larger than what fits into a 4 byte integer,
            # fall back to the ZIP64 extension
            file_size = 0xFFFFFFFF
            compress_size = 0xFFFFFFFF
            min_version = ZIP64_VERSION

        self.extract_version = max(min_version, self.extract_version)
        self.create_version = max(min_version, self.create_version)
        filename, flag_bits = self._encodeFilenameFlags()
        header = struct.pack(
            structFileHeader,
            stringFileHeader,
            self.extract_version,
            self.reserved,
            flag_bits,
            ZIP_STORED,
            dostime,
            dosdate,
            CRC,
            compress_size,
            file_size,
            len(filename),
            len(extra),
        )
        return header + filename + extra

    def _encodeFilenameFlags(self):
        try:
            return self.filename.encode("ascii"), self.flag_bits
        except UnicodeEncodeError:
            return self.filename.encode("utf-8"), self.flag_bits | 0x800

    def _decodeExtra(self):
        # Try to decode the extra field.
        extra = self.extra
        unpack = struct.unpack
        while len(extra) >= 4:
            tp, ln = unpack("<HH", extra[:4])
            if ln + 4 > len(extra):
                raise BadZipFile("Corrupt extra field %04x (size=%d)" % (tp, ln))
            if tp == 0x0001:
                if ln >= 24:
                    counts = unpack("<QQQ", extra[4:28])
                elif ln == 16:
                    counts = unpack("<QQ", extra[4:20])
                elif ln == 8:
                    counts = unpack("<Q", extra[4:12])
                elif ln == 0:
                    counts = ()
                else:
                    raise BadZipFile("Corrupt extra field %04x (size=%d)" % (tp, ln))

                idx = 0

                # ZIP64 extension (large files and/or large archives)
                if self.file_size in (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF):
                    self.file_size = counts[idx]
                    idx += 1

                if self.compress_size == 0xFFFFFFFF:
                    self.compress_size = counts[idx]
                    idx += 1

                if self.header_offset == 0xFFFFFFFF:
                    old = self.header_offset
                    self.header_offset = counts[idx]
                    idx += 1

            extra = extra[ln + 4 :]

    @classmethod
    def from_file(cls, filename, reuse_zinfo=None):
        """Construct an appropriate ZipInfo for a file on the filesystem.

        filename MUST be relative

        # filename should be the path to a file or directory on the filesystem.

        # arcname is the name which it will have within the archive (by default,
        # this will be the same as filename, but without a drive letter and with
        # leading path separators removed).
        """
        if isinstance(filename, os.PathLike):
            filename = os.fspath(filename)
        st = os.stat(filename)
        isdir = stat.S_ISDIR(st.st_mode)
        mtime = time.localtime(st.st_mtime)
        date_time = mtime[0:6]
        if isdir:
            filename += "/"

        if reuse_zinfo is not None:
            reuse_zinfo.init(filename, date_time)
            reuse_zinfo.external_attr = (st.st_mode & 0xFFFF) << 16  # Unix attributes
            if isdir:
                reuse_zinfo.file_size = 0
                reuse_zinfo.external_attr |= 0x10  # MS-DOS directory flag
            else:
                reuse_zinfo.file_size = st.st_size
        else:
            reuse_zinfo = cls(filename, date_time)

        return reuse_zinfo

    def is_dir(self):
        """Return True if this archive member is a directory."""
        return self.filename[-1] == "/"


class _SharedFile:
    def __init__(self, file, pos, close, lock, writing):
        self._file = file
        self._pos = pos
        self._close = close
        self._lock = lock
        self._writing = writing
        self.seekable = file.seekable
        self.tell = file.tell

    def seek(self, offset, whence=0):
        with self._lock:
            if self._writing():
                raise ValueError(
                    "Can't reposition in the ZIP file while "
                    "there is an open writing handle on it. "
                    "Close the writing handle before trying to read."
                )
            self._file.seek(offset, whence)
            self._pos = self._file.tell()
            return self._pos

    def read(self, n=-1):
        with self._lock:
            if self._writing():
                raise ValueError(
                    "Can't read from the ZIP file while there "
                    "is an open writing handle on it. "
                    "Close the writing handle before trying to read."
                )
            self._file.seek(self._pos)
            data = self._file.read(n)
            self._pos = self._file.tell()
            return data

    def close(self):
        if self._file is not None:
            fileobj = self._file
            self._file = None
            self._close(fileobj)


# Provide the tell method for unseekable stream
class _Tellable:
    def __init__(self, fp):
        self.fp = fp
        self.offset = 0

    def write(self, data):
        n = self.fp.write(data)
        self.offset += n
        return n

    def tell(self):
        return self.offset

    def flush(self):
        self.fp.flush()

    def close(self):
        self.fp.close()


class ZipExtFile(io.BufferedIOBase):
    """File-like object for reading an archive member.
       Is returned by ZipFile.open().
    """

    # Max size supported by decompressor.
    MAX_N = 1 << 31 - 1

    # Read from compressed files in 4k blocks.
    MIN_READ_SIZE = 4096

    # Chunk size to read during seek
    MAX_SEEK_READ = 1 << 24

    def __init__(self, fileobj, mode, zipinfo, decrypter=None, close_fileobj=False):
        self._fileobj = fileobj
        self._decrypter = decrypter
        self._close_fileobj = close_fileobj

        self._compress_left = zipinfo.compress_size
        self._left = zipinfo.file_size

        self._eof = False
        self._readbuffer = b""
        self._offset = 0

        self.newlines = None

        # Adjust read size for encrypted files since the first 12 bytes
        # are for the encryption/password information.
        if self._decrypter is not None:
            self._compress_left -= 12

        self.mode = mode
        self.name = zipinfo.filename

        if hasattr(zipinfo, "CRC"):
            self._expected_crc = zipinfo.CRC
            self._running_crc = crc32(b"")
        else:
            self._expected_crc = None

        self._seekable = False
        # try:
        #     if fileobj.seekable():
        #         self._orig_compress_start = fileobj.tell()
        #         self._orig_compress_size = zipinfo.compress_size
        #         self._orig_file_size = zipinfo.file_size
        #         self._orig_start_crc = self._running_crc
        #         self._seekable = True
        # except AttributeError:
        #     pass

    def __repr__(self):
        result = ["<%s.%s" % (self.__class__.__module__, self.__class__.__qualname__)]
        if not self.closed:
            result.append(" name=%r mode=%r" % (self.name, self.mode))
        else:
            result.append(" [closed]")
        result.append(">")
        return "".join(result)

    def readline(self, limit=-1):
        """Read and return a line from the stream.

        If limit is specified, at most limit bytes will be read.
        """

        if limit < 0:
            # Shortcut common case - newline found in buffer.
            i = self._readbuffer.find(b"\n", self._offset) + 1
            if i > 0:
                line = self._readbuffer[self._offset : i]
                self._offset = i
                return line

        return io.BufferedIOBase.readline(self, limit)

    def peek(self, n=1):
        """Returns buffered bytes without advancing the position."""
        if n > len(self._readbuffer) - self._offset:
            chunk = self.read(n)
            if len(chunk) > self._offset:
                self._readbuffer = chunk + self._readbuffer[self._offset :]
                self._offset = 0
            else:
                self._offset -= len(chunk)

        # Return up to 512 bytes to reduce allocation overhead for tight loops.
        return self._readbuffer[self._offset : self._offset + 512]

    def readable(self):
        return True

    def read(self, n=-1):
        """Read and return up to n bytes.
        If the argument is omitted, None, or negative, data is read and returned until EOF is reached.
        """
        if n is None or n < 0:
            buf = self._readbuffer[self._offset :]
            self._readbuffer = b""
            self._offset = 0
            while not self._eof:
                buf += self._read1(self.MAX_N)
            return buf

        end = n + self._offset
        if end < len(self._readbuffer):
            buf = self._readbuffer[self._offset : end]
            self._offset = end
            return buf

        n = end - len(self._readbuffer)
        buf = self._readbuffer[self._offset :]
        self._readbuffer = b""
        self._offset = 0
        while n > 0 and not self._eof:
            data = self._read1(n)
            if n < len(data):
                self._readbuffer = data
                self._offset = n
                buf += data[:n]
                break
            buf += data
            n -= len(data)
        return buf

    def _update_crc(self, newdata):
        # Update the CRC using the given data.
        if self._expected_crc is None:
            # No need to compute the CRC if we don't have a reference value
            return
        self._running_crc = crc32(newdata, self._running_crc)
        # Check the CRC if we're at the end of the file
        if self._eof and self._running_crc != self._expected_crc:
            raise BadZipFile("Bad CRC-32 for file %r" % self.name)

    def read1(self, n):
        """Read up to n bytes with at most one read() system call."""

        if n is None or n < 0:
            buf = self._readbuffer[self._offset :]
            self._readbuffer = b""
            self._offset = 0
            while not self._eof:
                data = self._read1(self.MAX_N)
                if data:
                    buf += data
                    break
            return buf

        end = n + self._offset
        if end < len(self._readbuffer):
            buf = self._readbuffer[self._offset : end]
            self._offset = end
            return buf

        n = end - len(self._readbuffer)
        buf = self._readbuffer[self._offset :]
        self._readbuffer = b""
        self._offset = 0
        if n > 0:
            while not self._eof:
                data = self._read1(n)
                if n < len(data):
                    self._readbuffer = data
                    self._offset = n
                    buf += data[:n]
                    break
                if data:
                    buf += data
                    break
        return buf

    def _read1(self, n):
        # Read up to n compressed bytes with at most one read() system call,
        # decrypt and decompress them.
        if self._eof or n <= 0:
            return b""

        # Read from file.
        data = self._read2(n)

        self._eof = self._compress_left <= 0

        data = data[: self._left]
        self._left -= len(data)
        if self._left <= 0:
            self._eof = True
        self._update_crc(data)
        return data

    def _read2(self, n):
        if self._compress_left <= 0:
            return b""

        n = max(n, self.MIN_READ_SIZE)
        n = min(n, self._compress_left)

        data = self._fileobj.read(n)
        self._compress_left -= len(data)
        if not data:
            raise EOFError

        if self._decrypter is not None:
            data = self._decrypter(data)
        return data

    def close(self):
        try:
            if self._close_fileobj:
                self._fileobj.close()
        finally:
            super().close()

    def seekable(self):
        return self._seekable

    def seek(self, offset, whence=0):
        if not self._seekable:
            raise io.UnsupportedOperation("underlying stream is not seekable")
        curr_pos = self.tell()
        if whence == 0:  # Seek from start of file
            new_pos = offset
        elif whence == 1:  # Seek from current position
            new_pos = curr_pos + offset
        elif whence == 2:  # Seek from EOF
            new_pos = self._orig_file_size + offset
        else:
            raise ValueError(
                "whence must be os.SEEK_SET (0), " "os.SEEK_CUR (1), or os.SEEK_END (2)"
            )

        if new_pos > self._orig_file_size:
            new_pos = self._orig_file_size

        if new_pos < 0:
            new_pos = 0

        read_offset = new_pos - curr_pos
        buff_offset = read_offset + self._offset

        if buff_offset >= 0 and buff_offset < len(self._readbuffer):
            # Just move the _offset index if the new position is in the _readbuffer
            self._offset = buff_offset
            read_offset = 0
        elif read_offset < 0:
            # Position is before the current position. Reset the ZipExtFile
            self._fileobj.seek(self._orig_compress_start)
            self._running_crc = self._orig_start_crc
            self._compress_left = self._orig_compress_size
            self._left = self._orig_file_size
            self._readbuffer = b""
            self._offset = 0
            self._eof = False
            read_offset = new_pos

        while read_offset > 0:
            read_len = min(self.MAX_SEEK_READ, read_offset)
            self.read(read_len)
            read_offset -= read_len

        return self.tell()

    def tell(self):
        if not self._seekable:
            raise io.UnsupportedOperation("underlying stream is not seekable")
        filepos = self._orig_file_size - self._left - len(self._readbuffer) + self._offset
        return filepos


class _ZipWriteFile(io.BufferedIOBase):
    def __init__(self, zf, zinfo, zip64):
        self._zinfo = zinfo
        self._zip64 = zip64
        self._zipfile = zf
        self._file_size = 0
        self._compress_size = 0
        self._crc = 0

    @property
    def _fileobj(self):
        return self._zipfile.fp

    def writable(self):
        return True

    def write(self, data):
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        nbytes = len(data)
        self._file_size += nbytes
        self._crc = crc32(data, self._crc)
        self._fileobj.write(data)
        return nbytes

    def close(self):
        if self.closed:
            return
        try:
            super().close()
            # Update header info
            self._zinfo.compress_size = self._file_size
            self._zinfo.CRC = self._crc
            self._zinfo.file_size = self._file_size

            # Write updated header info
            if self._zinfo.flag_bits & 0x08:
                # Write CRC and file sizes after the file data
                fmt = "<LLQQ" if self._zip64 else "<LLLL"
                self._fileobj.write(
                    struct.pack(
                        fmt,
                        _DD_SIGNATURE,
                        self._zinfo.CRC,
                        self._zinfo.compress_size,
                        self._zinfo.file_size,
                    )
                )
                self._zipfile.start_dir = self._fileobj.tell()
            else:
                if not self._zip64:
                    if self._file_size > ZIP64_LIMIT:
                        raise RuntimeError("File size unexpectedly exceeded ZIP64 limit")
                    if self._compress_size > ZIP64_LIMIT:
                        raise RuntimeError("Compressed size unexpectedly exceeded ZIP64 limit")
                # Seek backwards and write file header (which will now include
                # correct CRC and file sizes)

                # Preserve current position in file
                self._zipfile.start_dir = self._fileobj.tell()
                self._fileobj.seek(self._zinfo.header_offset)
                self._fileobj.write(self._zinfo.FileHeader(self._zip64))
                self._fileobj.seek(self._zipfile.start_dir)

            # Successfully written: Add file to our caches
            # self._zipfile.filelist.append(self._zinfo)
            self._zipfile.file_count += 1
            # self._zipfile.NameToInfo[self._zinfo.filename] = self._zinfo
        finally:
            self._zipfile._writing = False


class ZipFile:
    """ Class with methods to open, read, write, close, list zip files.

    z = ZipFile(file, mode="r", compression=ZIP_STORED, allowZip64=True,
                compresslevel=None)

    file: Either the path to the file, or a file-like object.
          If it is a path, the file will be opened and closed by ZipFile.
    mode: The mode can be either read 'r', write 'w', exclusive create 'x',
          or append 'a'.
    compression: ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib),
                 ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma).
    allowZip64: if True ZipFile will create files with ZIP64 extensions when
                needed, otherwise it will raise an exception when this would
                be necessary.
    compresslevel: None (default for the given compression type) or an integer
                   specifying the level to pass to the compressor.
                   When using ZIP_STORED or ZIP_LZMA this keyword has no effect.
                   When using ZIP_DEFLATED integers 0 through 9 are accepted.
                   When using ZIP_BZIP2 integers 1 through 9 are accepted.

    """

    fp = None  # Set here since __del__ checks it
    _windows_illegal_name_trans_table = None

    def __init__(
        self, file, mode="r", allowZip64=True,
    ):
        """Open the ZIP file with mode read 'r', write 'w', exclusive create 'x',
        or append 'a'."""
        if mode not in ("r", "w", "x", "a"):
            raise ValueError("ZipFile requires mode 'r', 'w', 'x', or 'a'")

        self._allowZip64 = allowZip64
        self._didModify = False
        self.debug = 0  # Level of printing: 0 through 3
        # self.NameToInfo = {}  # Find file info given name
        # self.filelist = []  # List of ZipInfo instances for archive
        self.file_count = 0
        self.mode = mode
        self.pwd = None
        self._comment = b""
        self._public_zinfo = None

        # Check if we were passed a file-like object
        if isinstance(file, os.PathLike):
            file = os.fspath(file)
        if isinstance(file, str):
            # No, it's a filename
            self._filePassed = 0
            self.filename = file
            modeDict = {
                "r": "rb",
                "w": "w+b",
                "x": "x+b",
                "a": "r+b",
                "r+b": "w+b",
                "w+b": "wb",
                "x+b": "xb",
            }
            filemode = modeDict[mode]
            while True:
                try:
                    self.fp = io.open(file, filemode)
                except OSError:
                    if filemode in modeDict:
                        filemode = modeDict[filemode]
                        continue
                    raise
                break
        else:
            self._filePassed = 1
            self.fp = file
            self.filename = getattr(file, "name", None)
        self._fileRefCnt = 1
        self._lock = threading.RLock()
        self._seekable = False
        self._writing = False

        try:
            if mode == "r":
                raise NotImplementedError("only supports write action")
            elif mode in ("w", "x"):
                # set the modified flag so central directory gets written
                # even if no files are added to the archive
                self._didModify = True
                try:
                    self.start_dir = self.fp.tell()
                except (AttributeError, OSError):
                    self.fp = _Tellable(self.fp)
                    self.start_dir = 0
                    self._seekable = False
                else:
                    # Some file-like objects can provide tell() but not seek()
                    try:
                        self.fp.seek(self.start_dir)
                    except (AttributeError, OSError):
                        self._seekable = False
            elif mode == "a":
                raise NotImplementedError("only supports write action")
            else:
                raise ValueError("Mode must be 'r', 'w', 'x', or 'a'")
        except:
            fp = self.fp
            self.fp = None
            self._fpclose(fp)
            raise

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __repr__(self):
        result = ["<%s.%s" % (self.__class__.__module__, self.__class__.__qualname__)]
        if self.fp is not None:
            if self._filePassed:
                result.append(" file=%r" % self.fp)
            elif self.filename is not None:
                result.append(" filename=%r" % self.filename)
            result.append(" mode=%r" % self.mode)
        else:
            result.append(" [closed]")
        result.append(">")
        return "".join(result)

    def setpassword(self, pwd):
        """Set default password for encrypted files."""
        if pwd and not isinstance(pwd, bytes):
            raise TypeError("pwd: expected bytes, got %s" % type(pwd).__name__)
        if pwd:
            self.pwd = pwd
        else:
            self.pwd = None

    @property
    def comment(self):
        """The comment text associated with the ZIP file."""
        return self._comment

    @comment.setter
    def comment(self, comment):
        if not isinstance(comment, bytes):
            raise TypeError("comment: expected bytes, got %s" % type(comment).__name__)
        # check for valid comment length
        if len(comment) > ZIP_MAX_COMMENT:
            import warnings

            warnings.warn(
                "Archive comment is too long; truncating to %d bytes" % ZIP_MAX_COMMENT,
                stacklevel=2,
            )
            comment = comment[:ZIP_MAX_COMMENT]
        self._comment = comment
        self._didModify = True

    def read(self, name, pwd=None):
        """Return file bytes for name."""
        with self.open(name, "r", pwd) as fp:
            return fp.read()

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):
        """Return file-like object for 'name'.

        name is a string for the file name within the ZIP file, or a ZipInfo
        object.

        mode should be 'r' to read a file already in the ZIP file, or 'w' to
        write to a file newly added to the archive.

        pwd is the password to decrypt files (only used for reading).

        When writing, if the file size is not known in advance but may exceed
        2 GiB, pass force_zip64 to use the ZIP64 format, which can handle large
        files.  If the size is known in advance, it is best to pass a ZipInfo
        instance for name, with zinfo.file_size set.
        """
        if mode not in {"r", "w"}:
            raise ValueError('open() requires mode "r" or "w"')
        if pwd and not isinstance(pwd, bytes):
            raise TypeError("pwd: expected bytes, got %s" % type(pwd).__name__)
        if pwd and (mode == "w"):
            raise ValueError("pwd is only supported for reading files")
        if not self.fp:
            raise ValueError("Attempt to use ZIP archive that was already closed")

        # Make sure we have an info object
        if isinstance(name, ZipInfo):
            # 'name' is already an info object
            zinfo = name
        elif mode == "w":
            zinfo = ZipInfo(name)
        else:
            raise ValueError()

        if mode == "w":
            return self._open_to_write(zinfo, force_zip64=force_zip64)

        if self._writing:
            raise ValueError(
                "Can't read from the ZIP file while there "
                "is an open writing handle on it. "
                "Close the writing handle before trying to read."
            )

        # Open for reading:
        self._fileRefCnt += 1
        zef_file = _SharedFile(
            self.fp, zinfo.header_offset, self._fpclose, self._lock, lambda: self._writing,
        )
        try:
            # Skip the file header:
            fheader = zef_file.read(sizeFileHeader)
            if len(fheader) != sizeFileHeader:
                raise BadZipFile("Truncated file header")
            fheader = struct.unpack(structFileHeader, fheader)
            if fheader[_FH_SIGNATURE] != stringFileHeader:
                raise BadZipFile("Bad magic number for file header")

            fname = zef_file.read(fheader[_FH_FILENAME_LENGTH])
            if fheader[_FH_EXTRA_FIELD_LENGTH]:
                zef_file.read(fheader[_FH_EXTRA_FIELD_LENGTH])

            if zinfo.flag_bits & 0x20:
                # Zip 2.7: compressed patched data
                raise NotImplementedError("compressed patched data (flag bit 5)")

            if zinfo.flag_bits & 0x40:
                # strong encryption
                raise NotImplementedError("strong encryption (flag bit 6)")

            if zinfo.flag_bits & 0x800:
                # UTF-8 filename
                fname_str = fname.decode("utf-8")
            else:
                fname_str = fname.decode("cp437")

            if fname_str != zinfo.orig_filename:
                raise BadZipFile(
                    "File name in directory %r and header %r differ." % (zinfo.orig_filename, fname)
                )

            return ZipExtFile(zef_file, mode, zinfo, None, True)
        except:
            zef_file.close()
            raise

    def _open_to_write(self, zinfo, force_zip64=False):
        if force_zip64 and not self._allowZip64:
            raise ValueError(
                "force_zip64 is True, but allowZip64 was False when opening " "the ZIP file."
            )
        if self._writing:
            raise ValueError(
                "Can't write to the ZIP file while there is "
                "another write handle open on it. "
                "Close the first handle before opening another."
            )

        # Sizes and CRC are overwritten with correct data after processing the file
        if not hasattr(zinfo, "file_size"):
            zinfo.file_size = 0
        zinfo.compress_size = 0
        zinfo.CRC = 0

        zinfo.flag_bits = 0x00
        if not self._seekable:
            zinfo.flag_bits |= 0x08

        if not zinfo.external_attr:
            zinfo.external_attr = 0o600 << 16  # permissions: ?rw-------

        # Compressed size can be larger than uncompressed size
        zip64 = self._allowZip64 and (force_zip64 or zinfo.file_size * 1.05 > ZIP64_LIMIT)

        if self._seekable:
            self.fp.seek(self.start_dir)
        zinfo.header_offset = self.fp.tell()

        self._writecheck(zinfo)
        self._didModify = True

        self.fp.write(zinfo.FileHeader(zip64))

        self._writing = True
        return _ZipWriteFile(self, zinfo, zip64)

    @classmethod
    def _sanitize_windows_name(cls, arcname, pathsep):
        """Replace bad characters and remove trailing dots from parts."""
        table = cls._windows_illegal_name_trans_table
        if not table:
            illegal = ':<>|"?*'
            table = str.maketrans(illegal, "_" * len(illegal))
            cls._windows_illegal_name_trans_table = table
        arcname = arcname.translate(table)
        # remove trailing dots
        arcname = (x.rstrip(".") for x in arcname.split(pathsep))
        # rejoin, removing empty parts.
        arcname = pathsep.join(x for x in arcname if x)
        return arcname

    def _writecheck(self, zinfo):
        """Check for errors before writing a file to the archive."""
        # if zinfo.filename in self.NameToInfo:
        #     import warnings

        #     warnings.warn("Duplicate name: %r" % zinfo.filename, stacklevel=3)
        if self.mode not in ("w", "x", "a"):
            raise ValueError("write() requires mode 'w', 'x', or 'a'")
        if not self.fp:
            raise ValueError("Attempt to write ZIP archive that was already closed")
        if not self._allowZip64:
            requires_zip64 = None
            if self.file_count >= ZIP_FILECOUNT_LIMIT:
                requires_zip64 = "Files count"
            elif zinfo.file_size > ZIP64_LIMIT:
                requires_zip64 = "Filesize"
            elif zinfo.header_offset > ZIP64_LIMIT:
                requires_zip64 = "Zipfile size"
            if requires_zip64:
                raise LargeZipFile(requires_zip64 + " would require ZIP64 extensions")

    def write(self, filename):
        """Put the bytes from filename into the archive under the name
        arcname."""
        if not self.fp:
            raise ValueError("Attempt to write to ZIP archive that was already closed")
        if self._writing:
            raise ValueError("Can't write to ZIP archive while an open writing handle exists")

        if self._public_zinfo is None:
            self._public_zinfo = ZipInfo.from_file(filename)
        else:
            self._public_zinfo = ZipInfo.from_file(filename, self._public_zinfo)

        if self._public_zinfo.is_dir():
            self._public_zinfo.compress_size = 0
            self._public_zinfo.CRC = 0

            with self._lock:
                if self._seekable:
                    self.fp.seek(self.start_dir)
                self._public_zinfo.header_offset = self.fp.tell()  # Start of header bytes

                self._writecheck(self._public_zinfo)
                self._didModify = True

                # self.filelist.append(zinfo)
                self.file_count += 1
                # self.NameToInfo[zinfo.filename] = zinfo
                self.fp.write(self._public_zinfo.FileHeader(False))
                self.start_dir = self.fp.tell()
        else:
            with open(filename, "rb") as src, self.open(self._public_zinfo, "w") as dest:
                shutil.copyfileobj(src, dest, 1024 * 8)

    def __del__(self):
        """Call the "close()" method in case the user forgot."""
        self.close()

    def close(self):
        """Close the file, and for mode 'w', 'x' and 'a' write the ending
        records."""
        if self.fp is None:
            return

        if self._writing:
            raise ValueError(
                "Can't close the ZIP file while there is "
                "an open writing handle on it. "
                "Close the writing handle before closing the zip."
            )

        try:
            if self.mode in ("w", "x", "a") and self._didModify:  # write ending records
                with self._lock:
                    if self._seekable:
                        self.fp.seek(self.start_dir)
                    self._write_end_record()
        finally:
            fp = self.fp
            self.fp = None
            self._fpclose(fp)

    def _write_end_record(self):
        for _ in itertools.repeat(None, self.file_count):
            zinfo: ZipInfo = self._public_zinfo
            dt = zinfo.date_time
            dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
            dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
            extra = []
            if zinfo.file_size > ZIP64_LIMIT or zinfo.compress_size > ZIP64_LIMIT:
                extra.append(zinfo.file_size)
                extra.append(zinfo.compress_size)
                file_size = 0xFFFFFFFF
                compress_size = 0xFFFFFFFF
            else:
                file_size = zinfo.file_size
                compress_size = zinfo.compress_size

            if zinfo.header_offset > ZIP64_LIMIT:
                extra.append(zinfo.header_offset)
                header_offset = 0xFFFFFFFF
            else:
                header_offset = zinfo.header_offset

            extra_data = zinfo.extra
            min_version = 0
            if extra:
                # Append a ZIP64 field to the extra's
                extra_data = _strip_extra(extra_data, (1,))
                extra_data = (
                    struct.pack("<HH" + "Q" * len(extra), 1, 8 * len(extra), *extra) + extra_data
                )

                min_version = ZIP64_VERSION

            extract_version = max(min_version, zinfo.extract_version)
            create_version = max(min_version, zinfo.create_version)
            try:
                filename, flag_bits = zinfo._encodeFilenameFlags()
                centdir = struct.pack(
                    structCentralDir,
                    stringCentralDir,
                    create_version,
                    zinfo.create_system,
                    extract_version,
                    zinfo.reserved,
                    flag_bits,
                    ZIP_STORED,
                    dostime,
                    dosdate,
                    zinfo.CRC,
                    compress_size,
                    file_size,
                    len(filename),
                    len(extra_data),
                    len(zinfo.comment),
                    0,
                    zinfo.internal_attr,
                    zinfo.external_attr,
                    header_offset,
                )
            except DeprecationWarning:
                print(
                    (
                        structCentralDir,
                        stringCentralDir,
                        create_version,
                        zinfo.create_system,
                        extract_version,
                        zinfo.reserved,
                        zinfo.flag_bits,
                        ZIP_STORED,
                        dostime,
                        dosdate,
                        zinfo.CRC,
                        compress_size,
                        file_size,
                        len(zinfo.filename),
                        len(extra_data),
                        len(zinfo.comment),
                        0,
                        zinfo.internal_attr,
                        zinfo.external_attr,
                        header_offset,
                    ),
                    file=sys.stderr,
                )
                raise
            self.fp.write(centdir)
            self.fp.write(filename)
            self.fp.write(extra_data)
            self.fp.write(zinfo.comment)

        pos2 = self.fp.tell()
        # Write end-of-zip-archive record
        centDirCount = self.file_count
        centDirSize = pos2 - self.start_dir
        centDirOffset = self.start_dir

        endrec = struct.pack(
            structEndArchive,
            stringEndArchive,
            0,
            0,
            centDirCount,
            centDirCount,
            centDirSize,
            centDirOffset,
            len(self._comment),
        )
        self.fp.write(endrec)
        self.fp.write(self._comment)
        self.fp.flush()

    def _fpclose(self, fp):
        assert self._fileRefCnt > 0
        self._fileRefCnt -= 1
        if not self._fileRefCnt and not self._filePassed:
            fp.close()
