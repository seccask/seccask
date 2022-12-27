from functools import partial
from struct import Struct
import zlib


def stream_unzip(zipfile_chunks, chunk_size=65536):
    local_file_header_signature = b"\x50\x4b\x03\x04"
    local_file_header_struct = Struct("<H2sHHHIIIHH")
    zip64_compressed_size = 4294967295
    zip64_size_signature = b"\x01\x00"
    central_directory_signature = b"\x50\x4b\x01\x02"

    def next_or_truncated_error(it):
        try:
            return next(it)
        except StopIteration:
            raise TruncatedDataError from None

    def get_byte_readers(iterable):
        # Return functions to return/"replace" bytes from/to the iterable
        # - _yield_all: yields chunks as they come up (often for a "body")
        # - _get_num: returns a single `bytes` of a given length
        # - _return_unused: puts "unused" bytes "back", to be retrieved by a yield/get call

        chunk = b""
        offset = 0
        it = iter(iterable)

        def _yield_all():
            nonlocal chunk, offset

            while True:
                if offset == len(chunk):
                    try:
                        chunk = next(it)
                    except StopIteration:
                        break
                    else:
                        offset = 0
                to_yield = min(len(chunk) - offset, chunk_size)
                offset = offset + to_yield
                yield chunk[offset - to_yield : offset]

        def _yield_num(num):
            nonlocal chunk, offset

            while num:
                if offset == len(chunk):
                    chunk = next_or_truncated_error(it)
                    offset = 0
                to_yield = min(num, len(chunk) - offset, chunk_size)
                offset = offset + to_yield
                num -= to_yield
                yield chunk[offset - to_yield : offset]

        def _get_num(num):
            return b"".join(_yield_num(num))

        def _return_unused(num_unused):
            nonlocal offset
            offset -= num_unused

        return _yield_all, _get_num, _return_unused

    def get_decompressor_none(num_bytes):
        num_decompressed = 0
        num_unused = 0

        def _decompress(compressed_chunk):
            nonlocal num_decompressed, num_unused
            to_yield = min(len(compressed_chunk), num_bytes - num_decompressed)
            num_decompressed += to_yield
            num_unused = len(compressed_chunk) - to_yield
            yield compressed_chunk[:to_yield]

        def _is_done():
            return num_decompressed == num_bytes

        def _num_unused():
            return num_unused

        return _decompress, _is_done, _num_unused

    def get_decompressor_deflate():
        dobj = zlib.decompressobj(wbits=-zlib.MAX_WBITS)

        def _decompress_single(compressed_chunk):
            try:
                return dobj.decompress(compressed_chunk, chunk_size)
            except zlib.error as e:
                raise DeflateError() from e

        def _decompress(compressed_chunk):
            uncompressed_chunk = _decompress_single(compressed_chunk)
            if uncompressed_chunk:
                yield uncompressed_chunk

            while dobj.unconsumed_tail and not dobj.eof:
                uncompressed_chunk = _decompress_single(dobj.unconsumed_tail)
                if uncompressed_chunk:
                    yield uncompressed_chunk

        def _is_done():
            return dobj.eof

        def _num_unused():
            return len(dobj.unused_data)

        return _decompress, _is_done, _num_unused

    def yield_file(yield_all, get_num, return_unused):
        def get_flag_bits(flags):
            for b in flags:
                for i in range(8):
                    yield (b >> i) & 1

        def parse_extra(extra):
            extra_offset = 0
            while extra_offset <= len(extra) - 4:
                extra_signature = extra[extra_offset : extra_offset + 2]
                extra_offset += 2
                (extra_data_size,) = Struct("<H").unpack(
                    extra[extra_offset : extra_offset + 2]
                )
                extra_offset += 2
                extra_data = extra[extra_offset : extra_offset + extra_data_size]
                extra_offset += extra_data_size
                yield (extra_signature, extra_data)

        def get_extra_value(
            extra,
            if_true,
            signature,
            exception_if_missing,
            min_length,
            exception_if_too_short,
        ):
            if if_true:
                try:
                    value = extra[signature]
                except KeyError:
                    raise exception_if_missing()

                if len(value) < min_length:
                    raise exception_if_too_short()
            else:
                value = None

            return value

        def decrypt_weak_decompress(chunks, decompress, is_done, num_unused):
            key_0 = 305419896
            key_1 = 591751049
            key_2 = 878082192
            crc32 = zlib.crc32
            bytes_c = bytes

            def update_keys(byte):
                nonlocal key_0, key_1, key_2
                key_0 = ~crc32(bytes_c((byte,)), ~key_0) & 0xFFFFFFFF
                key_1 = (key_1 + (key_0 & 0xFF)) & 0xFFFFFFFF
                key_1 = ((key_1 * 134775813) + 1) & 0xFFFFFFFF
                key_2 = ~crc32(bytes_c((key_1 >> 24,)), ~key_2) & 0xFFFFFFFF

            def decrypt(chunk):
                chunk = bytearray(chunk)
                for i, byte in enumerate(chunk):
                    temp = key_2 | 2
                    byte ^= ((temp * (temp ^ 1)) >> 8) & 0xFF
                    update_keys(byte)
                    chunk[i] = byte
                return bytes(chunk)

            encryption_header = decrypt(get_num(12))
            check_password_byte = (
                (mod_time >> 8) if has_data_descriptor else (crc_32_expected >> 24)
            )

            if encryption_header[11] != check_password_byte:
                raise IncorrectZipCryptoPasswordError()

            while not is_done():
                yield from decompress(decrypt(next_or_truncated_error(chunks)))

            return_unused(num_unused())

        def decrypt_none_decompress(chunks, decompress, is_done, num_unused):
            while not is_done():
                yield from decompress(next_or_truncated_error(chunks))

            return_unused(num_unused())

        def get_crc_32_expected_from_data_descriptor(is_zip64):
            dd_optional_signature = get_num(4)
            dd_so_far_num = 0 if dd_optional_signature == b"PK\x07\x08" else 4
            dd_so_far = dd_optional_signature[:dd_so_far_num]
            dd_remaining = (20 - dd_so_far_num) if is_zip64 else (12 - dd_so_far_num)
            dd = dd_so_far + get_num(dd_remaining)
            (crc_32_expected,) = Struct("<I").unpack(dd[:4])
            return crc_32_expected

        def get_crc_32_expected_from_file_header():
            return crc_32_expected

        def read_data_and_crc_32_ignore(get_crc_32_expected, chunks):
            yield from chunks
            get_crc_32_expected()

        def read_data_and_crc_32_verify(get_crc_32_expected, chunks):
            crc_32_actual = zlib.crc32(b"")
            for chunk in chunks:
                crc_32_actual = zlib.crc32(chunk, crc_32_actual)
                yield chunk

            if crc_32_actual != get_crc_32_expected():
                raise CRC32IntegrityError()

        (
            version,
            flags,
            compression_raw,
            mod_time,
            mod_date,
            crc_32_expected,
            compressed_size_raw,
            uncompressed_size_raw,
            file_name_len,
            extra_field_len,
        ) = local_file_header_struct.unpack(get_num(local_file_header_struct.size))

        flag_bits = tuple(get_flag_bits(flags))
        if (
            flag_bits[4]  # Enhanced deflating
            or flag_bits[5]  # Compressed patched
            or flag_bits[6]  # Strong encrypted
            or flag_bits[13]  # Masked header values
        ):
            raise UnsupportedFlagsError(flag_bits)

        file_name = get_num(file_name_len)
        extra = dict(parse_extra(get_num(extra_field_len)))

        compression = compression_raw

        if compression not in (0, 8, 9):
            raise UnsupportedCompressionTypeError(compression)

        has_data_descriptor = flag_bits[3]
        is_zip64 = (
            compressed_size_raw == zip64_compressed_size
            and uncompressed_size_raw == zip64_compressed_size
        )
        zip64_extra = get_extra_value(
            extra,
            not has_data_descriptor and is_zip64,
            zip64_size_signature,
            MissingZip64ExtraError,
            16,
            TruncatedZip64ExtraError,
        )

        uncompressed_size = (
            None
            if has_data_descriptor and compression in (8, 9)
            else Struct("<Q").unpack(zip64_extra[:8])[0]
            if is_zip64
            else uncompressed_size_raw
        )

        decompressor = get_decompressor_none(uncompressed_size)

        decompressed_bytes = decrypt_none_decompress(yield_all(), *decompressor)

        get_crc_32_expected = (
            partial(get_crc_32_expected_from_data_descriptor, is_zip64)
            if has_data_descriptor
            else get_crc_32_expected_from_file_header
        )

        crc_checked_bytes = read_data_and_crc_32_verify(
            get_crc_32_expected, decompressed_bytes
        )

        return file_name, uncompressed_size, crc_checked_bytes

    def all():
        yield_all, get_num, return_unused = get_byte_readers(zipfile_chunks)

        while True:
            signature = get_num(len(local_file_header_signature))
            if signature == local_file_header_signature:
                yield yield_file(yield_all, get_num, return_unused)
            elif signature == central_directory_signature:
                for _ in yield_all():
                    pass
                break
            else:
                raise UnexpectedSignatureError(signature)

    for file_name, file_size, unzipped_chunks in all():
        yield file_name, file_size, unzipped_chunks
        for _ in unzipped_chunks:
            raise UnfinishedIterationError()


class UnzipError(Exception):
    pass


class InvalidOperationError(UnzipError):
    pass


class UnfinishedIterationError(InvalidOperationError):
    pass


class UnzipValueError(UnzipError, ValueError):
    pass


class DataError(UnzipValueError):
    pass


class UncompressError(UnzipValueError):
    pass


class DeflateError(UncompressError):
    pass


class UnsupportedFeatureError(DataError):
    pass


class UnsupportedFlagsError(UnsupportedFeatureError):
    pass


class UnsupportedCompressionTypeError(UnsupportedFeatureError):
    pass


class TruncatedDataError(DataError):
    pass


class UnexpectedSignatureError(DataError):
    pass


class MissingExtraError(DataError):
    pass


class MissingZip64ExtraError(MissingExtraError):
    pass


class MissingAESExtraError(MissingExtraError):
    pass


class TruncatedExtraError(DataError):
    pass


class TruncatedZip64ExtraError(TruncatedExtraError):
    pass


class TruncatedAESExtraError(TruncatedExtraError):
    pass


class InvalidExtraError(TruncatedExtraError):
    pass


class InvalidAESKeyLengthError(TruncatedExtraError):
    pass


class IntegrityError(DataError):
    pass


class HMACIntegrityError(IntegrityError):
    pass


class CRC32IntegrityError(IntegrityError):
    pass


class PasswordError(UnzipValueError):
    pass


class MissingPasswordError(UnzipValueError):
    pass


class MissingZipCryptoPasswordError(MissingPasswordError):
    pass


class MissingAESPasswordError(MissingPasswordError):
    pass


class IncorrectPasswordError(PasswordError):
    pass


class IncorrectZipCryptoPasswordError(IncorrectPasswordError):
    pass


class IncorrectAESPasswordError(IncorrectPasswordError):
    pass
