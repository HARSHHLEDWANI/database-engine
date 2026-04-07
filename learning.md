# Database Engine — Learning Journal

> One concept at a time. Built from scratch.

---

### Concept: Database Pages

**What it is:**
A *page* (also called a *block*) is the fundamental unit of storage in a database. All data — rows, indexes, metadata — is stored inside pages. The database never reads or writes individual bytes from disk; it always reads/writes whole pages at a time.

**Why it exists:**
Disks are slow. Reading one byte takes almost as long as reading 4096 bytes because the disk has to seek to the location and spin up. Databases exploit this by packaging data into fixed-size chunks (pages) that match or align with the OS's I/O unit. This makes every disk read as "worth it" as possible.

Also: having a fixed size makes math simple. Page #5 is always at byte offset `5 * PAGE_SIZE`. No need to scan for it.

**How it works:**
1. A database file is divided into equal-sized chunks called pages.
2. Each page has a fixed size (typically 4096 or 8192 bytes).
3. Pages are numbered from 0 (or 1). Page N starts at byte offset `N * PAGE_SIZE`.
4. A page contains a header (metadata) + the actual data (rows/records).
5. The database reads/writes exactly one page at a time via `seek` + `read`/`write`.

**Real-world usage:**
- **SQLite**: Default page size is 4096 bytes. Configurable via `PRAGMA page_size`.
- **PostgreSQL**: Default block size is 8192 bytes (set at compile time via `--with-blocksize`).
- **InnoDB (MySQL)**: Uses 16384-byte pages by default.

**My implementation:**
*(To be filled as we build)*

**Edge cases:**
- Page size must be a power of 2 (aligns with OS memory pages and disk sectors).
- The very first page (page 0) is usually reserved for the *file header* — database metadata.
- If a row is larger than a page, databases use overflow pages (linked chain).

**Diagram (text-based):**
```
Database File on Disk
┌──────────────────────────────────────────────────┐
│  Page 0 (File Header)  │  offset: 0              │
│  ─ db version          │                         │
│  ─ page size           │                         │
│  ─ root page number    │                         │
├────────────────────────┤  offset: 4096           │
│  Page 1 (Data Page)    │                         │
│  ─ [header]            │                         │
│  ─ [row 1][row 2]...   │                         │
├────────────────────────┤  offset: 8192           │
│  Page 2 (Data Page)    │                         │
│  ...                   │                         │
└──────────────────────────────────────────────────┘

Page Layout (single page):
┌──────────────────────────────────────────────────┐
│ HEADER (fixed size)                              │
│  - page_id: u32                                  │
│  - num_records: u16                              │
│  - free_space_offset: u16                        │
├──────────────────────────────────────────────────┤
│ RECORDS (variable, packed from top)              │
│  [record_1][record_2][record_3]...               │
│                             [free space]         │
└──────────────────────────────────────────────────┘
```

---
