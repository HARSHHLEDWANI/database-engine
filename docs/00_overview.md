# 00 — System Overview & Roadmap

> Read this file first. Come back to it whenever you feel lost.

---

## What You Are Building

A file-based relational database engine — from raw bytes on disk to executing SQL-like queries. No database libraries. No ORMs. No shortcuts.

By the end, you will have a system that:

- Stores data in binary files using fixed-size pages
- Indexes data using a B-Tree you write yourself
- Parses and executes `INSERT` and `SELECT` statements
- Recovers from crashes using a Write-Ahead Log
- Caches pages in memory using a buffer pool

This is not a toy. Every design decision you make here mirrors what PostgreSQL, SQLite, and InnoDB do at their core.

---

## Full System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SQL Interface                            │
│              "INSERT INTO users VALUES (1, 'alice')"            │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        Query Engine                             │
│   Parser  →  Planner  →  Executor                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        Index Layer                              │
│                    B-Tree (per table)                           │
└──────────┬─────────────────────────────────────┬───────────────┘
           │                                     │
┌──────────▼──────────┐               ┌──────────▼───────────────┐
│    Buffer Pool      │               │   Transaction Manager     │
│  (in-memory cache)  │               │   (WAL + Recovery)        │
└──────────┬──────────┘               └──────────┬───────────────┘
           │                                     │
┌──────────▼─────────────────────────────────────▼───────────────┐
│                        Disk Manager                             │
│         read_page(id)  /  write_page(id, data)                  │
└─────────────────────────────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   data/*.db     │
                    │  Binary File    │
                    └─────────────────┘
```

Data flows top-down on writes, bottom-up on reads. Each layer has exactly one job.

---

## Folder Structure

```
db_engine/
│
├── src/
│   ├── storage/
│   │   ├── disk_manager.py       # raw page read/write
│   │   ├── page.py               # page layout, header, slots
│   │   └── record.py             # serialize/deserialize rows
│   │
│   ├── index/
│   │   ├── btree.py              # B-Tree node + tree operations
│   │   └── btree_page.py         # B-Tree nodes stored as pages
│   │
│   ├── query/
│   │   ├── lexer.py              # tokenize SQL string
│   │   ├── parser.py             # produce AST from tokens
│   │   └── executor.py           # walk AST, call storage/index
│   │
│   ├── transaction/
│   │   ├── wal.py                # write-ahead log (append-only)
│   │   └── recovery.py           # replay log after crash
│   │
│   ├── buffer/
│   │   └── buffer_pool.py        # LRU page cache
│   │
│   ├── utils/
│   │   └── serializer.py         # int/string encode-decode helpers
│   │
│   └── main.py                   # REPL entry point
│
├── data/                         # all .db and .wal files live here
├── tests/                        # one test file per module
├── docs/                         # this folder
└── learning.md                   # your personal concept journal
```

---

## Technology Choice

You must pick one language. Here are the honest trade-offs:

| Language | Pros | Cons | Recommended For |
|----------|------|------|-----------------|
| **Python** | Fast to write, readable, great for learning flow | Slow, no manual memory layout | Beginners, concept focus |
| **Go** | Fast, explicit, great stdlib, simple concurrency | Less familiar to some | Intermediate, production feel |
| **C** | Full control, closest to real DBs, forces precision | Manual memory, harder to debug | Advanced, maximum depth |
| **Rust** | Memory safe + low-level, modern | Steep learning curve | Advanced + Rust experience |

**Recommendation**: Start in **Python**. The concepts are what matter. If you want to rewrite in Go or C afterward, you'll have the mental model and it will be far easier.

---

## Phase Roadmap

| Phase | File | What You Build | Key Concept |
|-------|------|----------------|-------------|
| 1 | `01_storage_engine.md` | Disk Manager + Pages + Records | Binary I/O |
| 2 | `02_indexing_btree.md` | B-Tree from scratch | Tree traversal |
| 3 | `03_query_engine.md` | Lexer + Parser + Executor | SQL → AST → result |
| 4 | `04_transactions_wal.md` | WAL + crash recovery | Durability |
| 5 | `05_optimization.md` | Buffer pool + query planning | Performance |
| 6 | `06_final_project.md` | Integration + stress testing | Systems thinking |

Do not skip phases. Every phase builds on the previous one.

---

## How to Run and Test

### Running the REPL
```bash
cd db_engine
python src/main.py
```

You should eventually see:
```
db> INSERT INTO users VALUES (1, 'alice', 25);
Inserted.
db> SELECT * FROM users WHERE id = 1;
(1, alice, 25)
db>
```

### Running Tests
```bash
python -m pytest tests/ -v
```

Each phase has its own test file. Write tests as you go — do not defer them.

---

## Final Capabilities (What "Done" Looks Like)

- `INSERT INTO <table> VALUES (...)` — stores rows on disk
- `SELECT * FROM <table>` — full table scan
- `SELECT * FROM <table> WHERE id = <n>` — B-Tree indexed lookup
- Data persists across process restarts
- Crash mid-write is safely recoverable via WAL
- Buffer pool keeps hot pages in memory, evicts cold ones

---

## Ground Rules Before You Start

1. **Read the phase doc before writing any code.** Understand the design, then implement.
2. **Write tests for every function.** If it reads a page, test that the right bytes come back.
3. **Update `learning.md` after each phase.** Writing forces understanding.
4. **Do not use any database libraries.** `sqlite3`, `sqlalchemy`, `psycopg2` are all banned.
5. **Binary files only.** No JSON, no CSV, no text-based storage. Real databases don't use them.

---

## Key Mental Model: Everything Is a Page

Every piece of data in this system — rows, B-Tree nodes, the WAL, the schema — lives inside a page. A page is just `PAGE_SIZE` bytes. The database never reads or writes smaller units than one page. Internalize this before moving on.

```
File = [Page 0][Page 1][Page 2]...[Page N]
         ↑
    File Header
    (DB metadata)
```

---

*Start with `01_storage_engine.md`.*
