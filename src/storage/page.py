import struct

PAGE_SIZE = 4096
HEADER_SIZE = 12
SLOT_SIZE = 4


class Page:
    def __init__(self, page_id: int, data=None):
        self.page_id = page_id

        if data is None:
            self.data = bytearray(PAGE_SIZE)

            # initialize header
            self.num_slots = 0
            self.free_offset = PAGE_SIZE

            self._write_header()
        else:
            self.data = data
            self._read_header()

    # ---------------- HEADER ---------------- #

    def _write_header(self):
        struct.pack_into('>I', self.data, 0, self.page_id)
        struct.pack_into('>H', self.data, 4, self.num_slots)
        struct.pack_into('>H', self.data, 6, self.free_offset)
        struct.pack_into('>I', self.data, 8, 0)  # flags

    def _read_header(self):
        self.page_id = struct.unpack_from('>I', self.data, 0)[0]
        self.num_slots = struct.unpack_from('>H', self.data, 4)[0]
        self.free_offset = struct.unpack_from('>H', self.data, 6)[0]

    # ---------------- CORE ---------------- #

    def add_record(self, record_bytes: bytes) -> int:
        record_len = len(record_bytes)

        # space needed = record + slot
        required_space = record_len + SLOT_SIZE

        if self.free_space() < required_space:
            raise Exception("Page full")

        # records grow backward
        record_offset = self.free_offset - record_len

        # write record
        self.data[record_offset:record_offset + record_len] = record_bytes

        # slots grow forward
        slot_offset = HEADER_SIZE + self.num_slots * SLOT_SIZE

        struct.pack_into('>H', self.data, slot_offset, record_offset)
        struct.pack_into('>H', self.data, slot_offset + 2, record_len)

        # update header values
        self.num_slots += 1
        self.free_offset = record_offset

        self._write_header()

        return self.num_slots - 1

    def get_record(self, slot_id: int):
        if slot_id < 0 or slot_id >= self.num_slots:
            return None

        slot_offset = HEADER_SIZE + slot_id * SLOT_SIZE

        record_offset = struct.unpack_from('>H', self.data, slot_offset)[0]
        record_len = struct.unpack_from('>H', self.data, slot_offset + 2)[0]

        # tombstone (deleted)
        if record_len == 0:
            return None

        return bytes(self.data[record_offset:record_offset + record_len])

    def delete_record(self, slot_id: int):
        if slot_id < 0 or slot_id >= self.num_slots:
            return

        slot_offset = HEADER_SIZE + slot_id * SLOT_SIZE

        # mark as deleted (tombstone)
        struct.pack_into('>H', self.data, slot_offset + 2, 0)

    # ---------------- UTIL ---------------- #

    def free_space(self) -> int:
        slot_end = HEADER_SIZE + self.num_slots * SLOT_SIZE
        return self.free_offset - slot_end

    def to_bytes(self):
        return self.data

    @classmethod
    def from_bytes(cls, page_id: int, data):
        return cls(page_id, data)