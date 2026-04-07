# 01 — Storage Engine

> You are building the foundation. Everything else sits on top of this.

---

## 🎯 Objective

By the end of this phase you will have:

- A `DiskManager` that reads and writes fixed-size pages to a binary file
- A `Page` structure with a proper header and a slot-based record layout
- A `Record` serializer that encodes/decodes typed row data to/from bytes
- A working test suite that proves data survives a process restart

---

## 🧠 Concepts

---

### Concept 1: The Database Page

**Intuition**

A database file is not a stream of rows. It is a sequence of fixed-size chunks called *pages*. The engine never reads a byte — it reads a page. It never writes a byte — it writes a page. This is the single most important rule in storage engine design.

**Why fixed size?**

- **O(1) seeks**: Page N is always at byte offset `N * PAGE_SIZE`. No scanning, no metadata needed to find it.
- **Alignment with OS I/O**: The OS reads disk in blocks (usually 4096 bytes). A page that matches this size means one database read = one OS read. No waste.
- **Uniform allocation**: Free pages can be reused trivially. No fragmentation accounting.

**Analogy**

A parking garage with identical spaces. Space 47 is always in the same spot. You don't search for it. If a car leaves, that space can be immediately reused by any car because all spaces are the same size.

**How SQLite does it**

SQLite's first page starts with a 100-byte file header:
```
Bytes 0–15:   "SQLite format 3\000"  (magic string)
Bytes 16–17:  Page size in bytes
Bytes 28–31:  Number of pages in the file
...
```
Every subsequent page is exactly `page_size` bytes. Page N is at offset `(N-1) * page_size` (SQLite uses 1-based page numbers).

**How PostgreSQL does it**

PostgreSQL calls pages "blocks". Size is 8192 bytes by default (compile-time constant `BLCKSZ`). Every page begins with `PageHeaderData`:
```c
typedef struct PageHeaderData {
    PageXLogRecPtr pd_lsn;      // WAL position of last change
    uint16         pd_checksum; // page checksum
    uint16         pd_flags;
    LocationIndex  pd_lower;    // start of free space
    LocationIndex  pd_upper;    // end of free space
    LocationIndex  pd_special;  // start of special space
    uint16         pd_pagesize_version;
} PageHeaderData;
```

---

### Concept 2: Page Layout — The Slotted Page

A page is not just a flat array of rows. Rows have variable length. A naive approach (just pack rows sequentially) makes deletion and updates catastrophically complex.

**The slotted page design** solves this. Used by PostgreSQL, SQLite, and virtually every serious database.

```
┌─────────────────────────────────────────────────────────┐
│                   PAGE (4096 bytes)                     │
├─────────────────────────────────────────────────────────┤
│  HEADER (fixed, e.g. 12 bytes)                          │
│    page_id       : 4 bytes                              │
│    num_slots     : 2 bytes                              │
│    free_offset   : 2 bytes  ← where free space starts  │
│    flags         : 4 bytes                              │
├─────────────────────────────────────────────────────────┤
│  SLOT ARRAY (grows →)                                   │
│    slot[0]: (offset=4084, length=12)                    │
│    slot[1]: (offset=4072, length=12)                    │
│    ...                                                  │
├────────────────────────────────────┬────────────────────┤
│           FREE SPACE               │                    │
│                                    │   records grow ←   │
│                                    │  record[1]         │
│                                    │  record[0]         │
└────────────────────────────────────┴────────────────────┘
```

**Key insight**: Slots grow from the top down. Records grow from the bottom up. They meet in the middle. When they collide, the page is full.

This means:
- Deletion = mark a slot as invalid (tombstone). The space is recovered later via *compaction*.
- Updates = write new record at a new location, update slot pointer.
- Record order on page is independent of logical row order.

---

### Concept 3: Record Serialization

A row like `(1, "alice", 25)` must be stored as bytes. This is serialization. The database must know exactly how to decode it back.

**Schema dependency**

You cannot deserialize a record without knowing its schema. The schema tells you:
- How many fields
- What type each field is
- How long each field is (for fixed-length types)

**Fixed-length vs variable-length fields**

| Type | Length | Strategy |
|------|--------|----------|
| INTEGER (4 bytes) | Fixed | Write raw bytes |
| FLOAT (8 bytes) | Fixed | Write raw bytes |
| CHAR(10) | Fixed | Pad with nulls |
| VARCHAR | Variable | Prefix with 2-byte length |

**Byte order matters**

You must pick and stick to one endianness. Use **big-endian** (network byte order) — it's the standard for binary formats. Python's `struct` module uses `>` prefix for big-endian.

```python
import struct
# Encode integer 42 as 4 bytes, big-endian
data = struct.pack('>i', 42)   # b'\x00\x00\x00*'
# Decode it back
value = struct.unpack('>i', data)[0]  # 42
```

**How SQLite handles types**

SQLite uses a clever variable-length type system called *serial types*. Each value is prefixed by a type code that encodes both the type and the length in a single integer. This is space-efficient but complex. For your engine, use fixed-format records with a known schema — simpler and equally educational.

---

### Concept 4: The Disk Manager

The disk manager is the only layer that touches the file system. Everything above it works with page IDs and byte buffers — it never calls `open()` or `seek()` directly.

**Responsibilities**

1. Open or create the database file
2. `read_page(page_id)` → bytes
3. `write_page(page_id, data)` → void
4. `allocate_page()` → new page_id
5. Track total page count

**File header (Page 0)**

Page 0 is special — it stores database-level metadata, not user rows. You can't use it for records.

```
Page 0 layout:
  bytes 0–3:   magic number (e.g. 0xDB_EN_01_00)
  bytes 4–7:   page_size
  bytes 8–11:  num_pages (total pages in file)
  bytes 12–15: schema_root_page (where schema info lives)
  bytes 16–19: first_free_page (free list head)
  rest:        reserved (zeroed)
```

---

## 🧩 System Design

```
DiskManager
    │  read_page(id) → bytes
    │  write_page(id, bytes)
    │  allocate_page() → id
    ▼
Page
    │  from_bytes(bytes) → Page
    │  to_bytes() → bytes
    │  add_record(bytes) → slot_id
    │  get_record(slot_id) → bytes
    │  delete_record(slot_id)
    ▼
Record
    │  serialize(row, schema) → bytes
    │  deserialize(bytes, schema) → row
```

These three classes are independent. `Page` does not call `DiskManager`. `Record` does not know about pages. Clean separation.

---

## 🛠️ Step-by-Step Tasks

---

### Task 1.1 — DiskManager (45–60 min)

Create `src/storage/disk_manager.py`.

**Implement:**

```python
PAGE_SIZE = 4096

class DiskManager:
    def __init__(self, filepath: str):
        # Open file in r+b if exists, else create with wb then reopen r+b
        # Initialize page 0 (file header) if new file
        ...

    def read_page(self, page_id: int) -> bytearray:
        # Seek to page_id * PAGE_SIZE
        # Read PAGE_SIZE bytes
        # If page doesn't exist, return bytearray(PAGE_SIZE)  ← zero-filled
        ...

    def write_page(self, page_id: int, data: bytes | bytearray) -> None:
        # Validate len(data) == PAGE_SIZE
        # Seek to page_id * PAGE_SIZE
        # Write data
        # Flush (f.flush() then os.fsync — important for durability)
        ...

    def allocate_page(self) -> int:
        # Increment num_pages in the file header
        # Return the new page_id
        # Do NOT write any data to the new page — let the caller do that
        ...

    def num_pages(self) -> int:
        # Read from file header
        ...

    def close(self) -> None:
        ...
```

**Constraints:**
- `write_page` must raise if `len(data) != PAGE_SIZE`
- `read_page` on a non-existent page returns zeroed bytes, does not raise
- After `allocate_page()`, the file header must reflect the new count durably

**Test (write this before the implementation):**

```python
# tests/test_disk_manager.py
def test_write_and_read_survives_reopen():
    dm = DiskManager("data/test.db")
    page_id = dm.allocate_page()
    data = bytearray(PAGE_SIZE)
    data[0:4] = b'TEST'
    dm.write_page(page_id, data)
    dm.close()

    dm2 = DiskManager("data/test.db")
    result = dm2.read_page(page_id)
    assert result[0:4] == b'TEST'
    dm2.close()
```

---

### Task 1.2 — File Header (20–30 min)

Page 0 is your file header. Implement two private methods:

```python
def _write_file_header(self, num_pages: int) -> None:
    header = bytearray(PAGE_SIZE)
    # magic bytes at offset 0
    struct.pack_into('>4s', header, 0, b'\xDBEN\x01')
    # page_size at offset 4
    struct.pack_into('>I', header, 4, PAGE_SIZE)
    # num_pages at offset 8
    struct.pack_into('>I', header, 8, num_pages)
    self.write_page(0, header)

def _read_file_header(self) -> dict:
    raw = self.read_page(0)
    magic = struct.unpack_from('>4s', raw, 0)[0]
    if magic != b'\xDBEN\x01':
        raise ValueError("Not a valid db file")
    return {
        'page_size': struct.unpack_from('>I', raw, 4)[0],
        'num_pages': struct.unpack_from('>I', raw, 8)[0],
    }
```

**Test:** Open an existing file, verify magic bytes and page count are correct.

---

### Task 1.3 — Page Structure (60–90 min)

Create `src/storage/page.py`.

**Header layout** (12 bytes):
```
offset 0: page_id      (4 bytes, uint32)
offset 4: num_slots    (2 bytes, uint16)
offset 6: free_offset  (2 bytes, uint16)  ← offset from page start where free space ends (records side)
offset 8: flags        (4 bytes, uint32)  ← reserved for now
```

**Slot format** (4 bytes per slot):
```
offset 0: record_offset  (2 bytes, uint16) ← byte offset within page
offset 2: record_length  (2 bytes, uint16) ← 0 means deleted (tombstone)
```

**Implement:**

```python
HEADER_SIZE = 12
SLOT_SIZE = 4

class Page:
    def __init__(self, page_id: int, data: bytearray = None):
        # If data is None, create a fresh bytearray(PAGE_SIZE)
        # Parse header from data
        ...

    def add_record(self, record_bytes: bytes) -> int:
        # Check if enough free space exists
        # Write record at the end of used record space (growing ←)
        # Add a new slot entry (growing →)
        # Update num_slots and free_offset in header
        # Return slot_id (index into slot array)
        ...

    def get_record(self, slot_id: int) -> bytes | None:
        # Read slot_id-th slot entry
        # If length == 0, return None (deleted)
        # Seek to offset, read length bytes
        # Return bytes
        ...

    def delete_record(self, slot_id: int) -> None:
        # Set the slot's length to 0 (tombstone)
        # Do NOT actually zero the bytes — real DBs don't either
        ...

    def free_space(self) -> int:
        # Total free bytes = (start of first record) - (end of slot array)
        # = free_offset - (HEADER_SIZE + num_slots * SLOT_SIZE)
        ...

    def to_bytes(self) -> bytearray:
        # Serialize entire page to bytearray(PAGE_SIZE)
        ...

    @classmethod
    def from_bytes(cls, page_id: int, data: bytearray) -> 'Page':
        ...
```

**Test:**

```python
def test_add_and_retrieve_record():
    page = Page(page_id=1)
    record = b'\x00\x00\x00\x01alice\x00\x00\x00\x19'  # raw bytes
    slot_id = page.add_record(record)
    assert page.get_record(slot_id) == record

def test_delete_marks_tombstone():
    page = Page(page_id=1)
    slot_id = page.add_record(b'hello')
    page.delete_record(slot_id)
    assert page.get_record(slot_id) is None

def test_page_serialization_roundtrip():
    page = Page(page_id=2)
    page.add_record(b'record_one')
    page.add_record(b'record_two')
    raw = page.to_bytes()
    restored = Page.from_bytes(2, bytearray(raw))
    assert restored.get_record(0) == b'record_one'
    assert restored.get_record(1) == b'record_two'
```

---

### Task 1.4 — Record Serializer (45–60 min)

Create `src/storage/record.py`.

**Schema definition:**

```python
# A schema is a list of (field_name, field_type) tuples
# Supported types: 'int' (4 bytes), 'str' (variable, 2-byte length prefix)

SCHEMA = [('id', 'int'), ('name', 'str'), ('age', 'int')]
```

**Implement:**

```python
class RecordSerializer:
    def __init__(self, schema: list[tuple[str, str]]):
        self.schema = schema

    def serialize(self, row: tuple) -> bytes:
        # Encode each field according to its type
        # int → struct.pack('>i', value)
        # str → struct.pack('>H', len(encoded)) + encoded  (2-byte length prefix)
        ...

    def deserialize(self, data: bytes) -> tuple:
        # Decode each field in order
        # Return as a tuple matching the schema
        ...
```

**Test:**

```python
def test_serialize_deserialize_roundtrip():
    schema = [('id', 'int'), ('name', 'str'), ('age', 'int')]
    ser = RecordSerializer(schema)
    row = (1, 'alice', 25)
    encoded = ser.serialize(row)
    decoded = ser.deserialize(encoded)
    assert decoded == row

def test_variable_length_strings():
    schema = [('id', 'int'), ('bio', 'str')]
    ser = RecordSerializer(schema)
    row = (42, 'a' * 200)
    assert ser.deserialize(ser.serialize(row)) == row
```

---

### Task 1.5 — Integration Test (30 min)

Write an end-to-end test that:

1. Creates a DiskManager
2. Allocates a page
3. Serializes a row to bytes using RecordSerializer
4. Adds that record to a Page
5. Writes the page to disk
6. Closes the DiskManager
7. Reopens the file
8. Reads the page back
9. Deserializes the record
10. Asserts the row matches the original

This test is your **checkpoint**. If it passes, your storage engine is correct.

---

## 💡 Thinking Questions

Answer these before coding each task. Write your answers in `learning.md`.

1. Why is `PAGE_SIZE = 4096` specifically? What happens if you use 3000?
2. A row is 5000 bytes. Your page size is 4096. What do you do? (Look up: overflow pages)
3. You delete 10 records from a page. The page reports 40 bytes free. But the deleted records take up 200 bytes. Why isn't that space reclaimed? What must happen for it to be reclaimed?
4. Why does `write_page` call `fsync` and not just `flush`? What is the difference?
5. Two records in a page have slot IDs 0 and 1. After deleting slot 0, what is slot 1's ID? Does it change?
6. What is the minimum number of bytes needed for a valid empty page?

---

## ⚠️ Common Mistakes

**Mistake 1: Using text mode for the file**
`open(path, 'r')` is wrong. You are writing raw bytes. Always use `'r+b'` or `'wb'`.

**Mistake 2: Not seeking before read/write**
The file cursor position is state. After writing page 3, it is at offset `4 * PAGE_SIZE`. If you then try to read page 1 without seeking, you'll read garbage.

**Mistake 3: Writing less than PAGE_SIZE bytes**
If `write_page` writes 100 bytes to offset 0, then page 1 starts at offset 100, not 4096. The entire offset math breaks. Always pad to exactly PAGE_SIZE.

**Mistake 4: Forgetting to update the file header after `allocate_page`**
If you crash after allocating but before updating the header, the next open will think fewer pages exist and overwrite your data.

**Mistake 5: Not flushing to disk**
`f.write()` writes to an OS buffer. `f.flush()` moves it to the OS cache. `os.fsync(f.fileno())` forces it to physical disk. For durability, you need `fsync`. For tests, `flush()` is enough.

**Mistake 6: Slot offset confusion**
Slots store the byte offset of the record *within the page*, not the offset in the file. These are different numbers.

**Mistake 7: Variable-length records without length prefixes**
If you store `"alice"` as raw bytes with no prefix, you cannot know where `"alice"` ends and the next field begins during deserialization.

---

## 🧪 Mini Challenges

1. **Compaction**: Write a `compact(page)` function that rewrites all non-deleted records contiguously, reclaiming space from tombstoned slots. This is called a *page vacuum* in PostgreSQL.

2. **Page fill factor**: Add a method `fill_percentage(page) → float` that returns what percentage of the page's record area is used. Real databases use this to decide when to split pages.

3. **Overflow detection**: Modify `add_record` to raise a specific `PageFullError` exception rather than silently failing. The caller should handle this by allocating a new page.

4. **Checksum**: Add a 4-byte CRC32 checksum to the page header. Verify it on `from_bytes`. This is how PostgreSQL detects disk corruption.

---

## 📦 Deliverable

At the end of Phase 1, you must be able to run:

```python
from storage.disk_manager import DiskManager
from storage.page import Page
from storage.record import RecordSerializer

dm = DiskManager("data/my.db")
schema = [('id', 'int'), ('name', 'str'), ('age', 'int')]
ser = RecordSerializer(schema)

page_id = dm.allocate_page()
page = Page(page_id=page_id)
page.add_record(ser.serialize((1, 'alice', 25)))
page.add_record(ser.serialize((2, 'bob', 30)))
dm.write_page(page_id, page.to_bytes())
dm.close()

# Reopen
dm = DiskManager("data/my.db")
raw = dm.read_page(page_id)
page = Page.from_bytes(page_id, raw)
print(ser.deserialize(page.get_record(0)))  # (1, 'alice', 25)
print(ser.deserialize(page.get_record(1)))  # (2, 'bob', 30)
dm.close()
```

---

## 🔍 Debugging Guide

**Problem**: `read_page` returns all zeros even after writing  
**Cause**: You wrote to one file but read from another, or forgot to `flush()`  
**Fix**: Assert the file path is the same. Call `f.flush()` after every write in tests.

**Problem**: `Page.from_bytes` raises struct error  
**Cause**: The header bytes are wrong size or wrong format string  
**Fix**: Print `hex(data[0:12])` and compare manually against what you packed.

**Problem**: `get_record` returns wrong bytes  
**Cause**: Slot offset is relative to the page, but you're using it as a file offset  
**Fix**: All slot offsets are `0–4095`. If you see values > 4095, something is wrong.

**Problem**: Second record overwrites first  
**Cause**: `free_offset` is not being updated after each `add_record`  
**Fix**: After writing a record, update `free_offset` to `record_offset` (the new lower bound).

**Problem**: Records are written in wrong byte order  
**Cause**: Using `struct.pack('i', ...)` (native endian) instead of `struct.pack('>i', ...)`  
**Fix**: Always prefix format strings with `>` for big-endian consistency.

---

## 📘 What to Write in Your learning.md

After completing this phase, add entries for:

1. **The Page Concept** — What is it, why fixed size, how SQLite/Postgres use it
2. **Slotted Page Design** — Why slots, how they enable variable-length records
3. **Binary Serialization** — struct module, endianness, why length prefixes matter
4. **DiskManager Role** — Why isolate file I/O into one class
5. **Your implementation** — What you built, any design choices you made, what surprised you

Template entry:
```markdown
### Concept: <name>
**What it is:** ...
**Why it exists:** ...
**How it works:** ...
**Real-world usage:** ...
**My implementation:** ...
**Edge cases:** ...
```

---

*When this phase is done and all tests pass, move to `02_indexing_btree.md`.*
