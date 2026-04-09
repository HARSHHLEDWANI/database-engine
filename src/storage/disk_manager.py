import os
import struct
from typing import Union

PAGE_SIZE = 4096
MAGIC = b'\xDBEN\x01'


class DiskManager:
    def __init__(self, filepath: str):
        self.filepath = filepath

        # Create file if it doesn't exist
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                pass  # just create empty file

            # reopen in r+b mode
            self.file = open(filepath, 'r+b')

            # initialize file header (page 0)
            self._write_file_header(1)  # page 0 exists → num_pages = 1
        else:
            self.file = open(filepath, 'r+b')

            # validate header
            header = self._read_file_header()
            if header['page_size'] != PAGE_SIZE:
                raise ValueError("Page size mismatch")

    # ---------------- FILE HEADER ---------------- #

    def _write_file_header(self, num_pages: int) -> None:
        header = bytearray(PAGE_SIZE)

        struct.pack_into('>4s', header, 0, MAGIC)
        struct.pack_into('>I', header, 4, PAGE_SIZE)
        struct.pack_into('>I', header, 8, num_pages)

        self.write_page(0, header)

    def _read_file_header(self) -> dict:
        raw = self.read_page(0)

        magic = struct.unpack_from('>4s', raw, 0)[0]
        if magic != MAGIC:
            raise ValueError("Not a valid database file")

        return {
            'page_size': struct.unpack_from('>I', raw, 4)[0],
            'num_pages': struct.unpack_from('>I', raw, 8)[0],
        }

    # ---------------- CORE METHODS ---------------- #

    def read_page(self, page_id: int) -> bytearray:
        offset = page_id * PAGE_SIZE
        self.file.seek(0, os.SEEK_END)
        file_size = self.file.tell()

        # If page doesn't exist → return zero-filled page
        if offset >= file_size:
            return bytearray(PAGE_SIZE)

        self.file.seek(offset)
        data = self.file.read(PAGE_SIZE)

        # Pad if short read
        if len(data) < PAGE_SIZE:
            data += b'\x00' * (PAGE_SIZE - len(data))

        return bytearray(data)

    def write_page(self, page_id: int, data: Union[bytes , bytearray]) -> None:
        if len(data) != PAGE_SIZE:
            raise ValueError("Data must be exactly one page (4096 bytes)")

        offset = page_id * PAGE_SIZE
        self.file.seek(offset)
        self.file.write(data)

        # Flush to OS buffer
        self.file.flush()
        os.fsync(self.file.fileno())

    def allocate_page(self) -> int:
        header = self._read_file_header()
        new_page_id = header['num_pages']

        # increment page count
        new_count = new_page_id + 1
        self._write_file_header(new_count)

        return new_page_id

    def num_pages(self) -> int:
        return self._read_file_header()['num_pages']

    def close(self) -> None:
        self.file.close()