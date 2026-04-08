# 02 — B-Tree Indexing

> Without an index, every query reads every record. With a B-Tree, any record is reachable in O(log n) disk reads.

---

## 🎯 Objective

By the end of this phase you will have:

- A B-Tree implementation where each node is stored as a page on disk
- `insert(key, value)` — adds a key-value pair, splitting nodes as needed
- `search(key)` → value — finds a record by key in O(log n) page reads
- `delete(key)` — removes a key, merging/rebalancing as needed
- The tree persists across process restarts (nodes live in pages on disk)

---

## 🧠 Concepts

---

### Concept 1: Why Index at All?

Without an index, `SELECT * FROM users WHERE id = 99999` requires reading every page in the table — a *full table scan*. For 1 million rows, that could mean thousands of disk reads.

An index is a separate data structure that maps keys to record locations. With an index on `id`, you jump directly to the page containing row 99999 in at most a few reads.

**The trade-off**: Indexes make reads faster but writes slower (you must update both the table and the index on insert/delete). This is exactly why you don't index every column — only the ones you query frequently.

---

### Concept 2: Why B-Tree and Not Binary Search Tree?

A binary search tree (BST) keeps data sorted and searchable in O(log n). But a BST node holds one key. For 1 million keys, the tree is 20 levels deep. On disk, each level is a page read. 20 page reads per lookup is already painful.

**The core problem**: BSTs are designed for RAM, where any pointer dereference is cheap. On disk, every pointer dereference is a seek — expensive.

**B-Tree's answer**: Each node holds many keys (order `t` means up to `2t-1` keys per node). A tree of order 100 with 1 million keys has at most 4 levels. 4 disk reads instead of 20.

```
BST (for 7 keys):          B-Tree (order 2, max 3 keys/node):
        4                           [4]
       / \                        /     \
      2   6                   [1,2,3]   [5,6,7]
     / \ / \
    1  3 5  7
    (7 nodes, 3 levels)     (3 nodes, 2 levels)
```

**General rule**: B-Tree order is chosen so that one node fits exactly in one page. Since a page is 4096 bytes and each key+pointer costs ~12 bytes, a single page can hold ~340 keys. A 3-level B-Tree of order 340 holds 340³ = ~39 million keys. Three disk reads for any lookup.

---

### Concept 3: B-Tree vs B+ Tree

Real databases (PostgreSQL, MySQL InnoDB, SQLite) use **B+ Trees**, not plain B-Trees.

| Property | B-Tree | B+ Tree |
|----------|--------|---------|
| Data in internal nodes | Yes | No |
| Data only in leaves | No | Yes |
| Leaf linked list | No | Yes |
| Range scans | Slow | Fast (follow leaf links) |

In a B+ Tree:
- Internal nodes store only keys (routing information)
- All actual values live in leaf nodes
- Leaf nodes are linked in a doubly-linked list

This makes range queries (`WHERE age BETWEEN 20 AND 30`) very fast — find the start leaf, then walk the linked list.

**You will implement a B+ Tree.** It is more complex than a plain B-Tree but far more useful.

```
B+ Tree structure:

Internal:  [30 | 60]
           /    |    \
Leaves: [10,20] [30,50] [60,70,90]
          ↔       ↔        ↔        (doubly linked)
```

---

### Concept 4: B+ Tree Node Types

**Internal node (non-leaf)**
- Contains `n` keys and `n+1` child pointers
- Children are page IDs
- Does NOT store actual record data
- Purpose: routing only

```
Internal node page layout:
┌────────────────────────────────────────────────────────┐
│ HEADER                                                 │
│   is_leaf: 0   num_keys: 2   parent_page_id: X        │
├────────────────────────────────────────────────────────┤
│ children[0] | key[0] | children[1] | key[1] | children[2] │
│  (page_id)           (page_id)             (page_id)   │
└────────────────────────────────────────────────────────┘
```

**Leaf node**
- Contains `n` key-value pairs
- `value` = page_id + slot_id of the actual record
- Has pointers to next and previous leaf
- IS where data is stored

```
Leaf node page layout:
┌────────────────────────────────────────────────────────┐
│ HEADER                                                 │
│   is_leaf: 1   num_keys: 3   next_leaf: Y   prev: Z   │
├────────────────────────────────────────────────────────┤
│ key[0]→(page4,slot2) | key[1]→(page4,slot3) | ...     │
└────────────────────────────────────────────────────────┘
```

---

### Concept 5: B+ Tree Operations

#### Search

```
search(key, node):
    if node is leaf:
        binary search for key in node.keys
        if found: return node.values[index]
        else: return None
    else:
        find i such that node.keys[i-1] <= key < node.keys[i]
        return search(key, load_page(node.children[i]))
```

Disk reads = tree height. For a balanced tree of N keys with order t: height = log_t(N).

#### Insert

1. Search for the leaf where the key belongs.
2. If the leaf has space, insert there. Done.
3. If the leaf is full (has `2t-1` keys):
   - **Split** the leaf into two leaves
   - Promote the middle key up to the parent
   - If the parent is also full, split the parent too (recurse upward)
   - If you reach the root and it's full, create a new root — the tree grows in height by 1

```
Before insert(35):       After insert(35):
[30 | 60]                [30 | 50 | 60]
    |                       /    |    \
[30,40,50] ← full    [30,40] [50] [60,70]
                        split!
```

#### Delete

Delete is the most complex operation. The steps:

1. Find the leaf containing the key.
2. Remove the key from the leaf.
3. If the leaf now has fewer than `t-1` keys (underflow):
   - Try to **borrow** a key from a sibling (rotation)
   - If no sibling can lend, **merge** with a sibling
   - Merging reduces the parent's key count — potentially causing underflow up the tree

**Simplification for your implementation**: Implement lazy deletion. Mark deleted keys with a tombstone flag. Only rebalance during compaction. This is a valid real-world strategy — many systems defer rebalancing.

---

### Concept 6: How PostgreSQL and SQLite Use B+ Trees

**PostgreSQL**
- Uses B+ Trees for all secondary indexes (created with `CREATE INDEX`)
- Each internal node fits in one 8192-byte page
- The root page is stored in the index file's first page
- Internal pages use a special `BTreePageOpaqueData` struct with left/right sibling pointers
- PostgreSQL also stores visibility info (MVCC) in the index for hot tuple optimization

**SQLite**
- The primary key IS the B+ Tree (called a *table B-Tree*)
- There is no separate heap file — rows live directly in the leaf pages
- Secondary indexes are separate B-Trees where leaf values are the primary key (then looked up in the table B-Tree)
- One B-Tree = one SQLite file. A database file contains multiple B-Trees (one per table, one per index)

---

## 🧩 System Design

```
BTree
  │  insert(key, value)
  │  search(key) → value | None
  │  delete(key)
  │  range_scan(lo, hi) → list[value]
  ▼
BTreeNode (stored in Page)
  │  is_leaf: bool
  │  keys: list[int]
  │  children: list[page_id]   ← internal nodes only
  │  values: list[RecordPointer]  ← leaf nodes only
  │  next_leaf: page_id
  │  prev_leaf: page_id
  ▼
DiskManager
  │  (from Phase 1)
```

**RecordPointer**: a (page_id, slot_id) pair that tells you exactly where in the heap file the record lives.

```python
@dataclass
class RecordPointer:
    page_id: int   # 4 bytes
    slot_id: int   # 2 bytes
    # total: 6 bytes per index entry value
```

---

## 🛠️ Step-by-Step Tasks

---

### Task 2.1 — BTreeNode Serialization (60–90 min)

Create `src/index/btree_page.py`.

A B-Tree node must be stored as a page (exactly `PAGE_SIZE` bytes). Design the binary format before writing code.

**Node header (16 bytes):**
```
offset 0:  is_leaf      (1 byte,  0=internal, 1=leaf)
offset 1:  num_keys     (2 bytes, uint16)
offset 3:  parent_id    (4 bytes, uint32, 0=no parent)
offset 7:  next_leaf    (4 bytes, uint32, 0=none) ← leaf only
offset 11: prev_leaf    (4 bytes, uint32, 0=none) ← leaf only
offset 15: reserved     (1 byte)
```

**Key size**: 4 bytes (integer key). Extend to variable-length later if desired.

**Internal node body** (after header):
```
children[0] | key[0] | children[1] | key[1] | ... | children[n]
  4 bytes      4 bytes   4 bytes      4 bytes         4 bytes
```
For `n` keys: `(n+1)*4 + n*4 = (2n+1)*4` bytes.

**Leaf node body** (after header):
```
key[0] | page_id[0] | slot_id[0] | key[1] | page_id[1] | slot_id[1] | ...
 4B        4B           2B          4B         4B           2B
```
Each entry = 10 bytes. For order `t`: up to `2t-1` entries.

**Calculate your order `t`:**
```python
HEADER_SIZE = 16
KEY_SIZE = 4
CHILD_PTR_SIZE = 4
LEAF_ENTRY_SIZE = KEY_SIZE + 4 + 2  # key + page_id + slot_id

# For internal nodes: (2t-1)*4 + 2t*4 + 16 <= 4096
# Solve: t = (4096 - 16) / (8*4) = ~127
# Use t = 100 for safety (generous free space for header evolution)

ORDER = 100  # max keys per node = 2*ORDER - 1 = 199
```

**Implement:**
```python
class BTreeNode:
    def __init__(self, page_id: int, is_leaf: bool):
        ...

    def serialize(self) -> bytearray:
        # Pack all fields into PAGE_SIZE bytes
        ...

    @classmethod
    def deserialize(cls, page_id: int, data: bytearray) -> 'BTreeNode':
        # Unpack fields from bytes
        ...

    def is_full(self) -> bool:
        return len(self.keys) >= 2 * ORDER - 1
```

**Test:**
```python
def test_internal_node_roundtrip():
    node = BTreeNode(page_id=1, is_leaf=False)
    node.keys = [10, 20, 30]
    node.children = [2, 3, 4, 5]
    raw = node.serialize()
    restored = BTreeNode.deserialize(1, raw)
    assert restored.keys == [10, 20, 30]
    assert restored.children == [2, 3, 4, 5]

def test_leaf_node_roundtrip():
    node = BTreeNode(page_id=1, is_leaf=True)
    node.keys = [5, 15]
    node.values = [RecordPointer(1, 0), RecordPointer(1, 1)]
    raw = node.serialize()
    restored = BTreeNode.deserialize(1, raw)
    assert restored.keys == [5, 15]
    assert restored.values[0] == RecordPointer(1, 0)
```

---

### Task 2.2 — BTree Search (45–60 min)

Create `src/index/btree.py`.

```python
class BTree:
    def __init__(self, disk_manager: DiskManager, root_page_id: int):
        self.dm = disk_manager
        self.root_page_id = root_page_id

    def _load_node(self, page_id: int) -> BTreeNode:
        raw = self.dm.read_page(page_id)
        return BTreeNode.deserialize(page_id, raw)

    def _save_node(self, node: BTreeNode) -> None:
        self.dm.write_page(node.page_id, node.serialize())

    def search(self, key: int) -> RecordPointer | None:
        return self._search(key, self.root_page_id)

    def _search(self, key: int, page_id: int) -> RecordPointer | None:
        node = self._load_node(page_id)
        if node.is_leaf:
            # binary search in node.keys
            # if found, return node.values[index]
            # else return None
            ...
        else:
            # find child index i such that we descend into children[i]
            # return self._search(key, node.children[i])
            ...
```

**Binary search for child index in an internal node:**
```
keys = [10, 20, 30]
children = [c0, c1, c2, c3]
# key < 10  → c0
# 10 <= key < 20 → c1
# 20 <= key < 30 → c2
# key >= 30 → c3
```

Use `bisect.bisect_right(node.keys, key)` from Python's `bisect` module — this returns the correct child index directly.

**Test:**
```python
def test_search_empty_tree():
    # A tree with only a root leaf, no keys
    assert tree.search(42) is None

def test_search_existing_key():
    tree.insert(10, RecordPointer(1, 0))
    tree.insert(20, RecordPointer(1, 1))
    assert tree.search(10) == RecordPointer(1, 0)
    assert tree.search(20) == RecordPointer(1, 1)
    assert tree.search(15) is None
```

---

### Task 2.3 — Insert Without Splits (45 min)

Implement the easy case first: insert into a leaf that has room.

```python
def insert(self, key: int, value: RecordPointer) -> None:
    # Find the leaf where key belongs
    # If the leaf is not full, insert and save
    # If the leaf IS full, call _split_and_insert (Task 2.4)
    ...

def _find_leaf(self, key: int) -> tuple[BTreeNode, list[int]]:
    # Returns (leaf_node, path_of_page_ids_from_root_to_leaf)
    # The path is needed for split propagation
    ...
```

**Test:**
```python
def test_insert_multiple_no_split():
    for i in range(10):  # 10 << ORDER, so no splits
        tree.insert(i * 10, RecordPointer(i, 0))
    for i in range(10):
        assert tree.search(i * 10) is not None
```

---

### Task 2.4 — Node Splitting (90–120 min)

This is the hardest part. Read carefully before implementing.

**Splitting a leaf node:**
```
Full leaf: [10, 20, 30, 40, 50]  (ORDER=3, max keys = 5)
Split at midpoint (index t-1 = 2):
  Left leaf:  [10, 20]
  Right leaf: [30, 40, 50]
  Promote to parent: 30  (first key of right leaf — this is the B+ tree rule)
```

**Splitting an internal node:**
```
Full internal: [10, 20, 30, 40, 50]
Split at midpoint (index t-1 = 2):
  Left internal:  [10, 20]          (with their children)
  Right internal: [40, 50]          (with their children)
  Promote to parent: 30             (the middle key is REMOVED from both children)
  Note: in B+ trees, the promoted key is removed from internal nodes (unlike leaf splits)
```

**The algorithm:**

```python
def _insert_recursive(self, key, value, page_id) -> tuple[int, int, RecordPointer] | None:
    """
    Returns None if no split occurred.
    Returns (promoted_key, left_page_id, right_page_id) if split occurred.
    """
    node = self._load_node(page_id)

    if node.is_leaf:
        # Insert into sorted position
        idx = bisect.bisect_left(node.keys, key)
        node.keys.insert(idx, key)
        node.values.insert(idx, value)

        if not node.is_full():
            self._save_node(node)
            return None  # no split
        else:
            return self._split_leaf(node)

    else:
        # Find correct child
        idx = bisect.bisect_right(node.keys, key)
        result = self._insert_recursive(key, value, node.children[idx])

        if result is None:
            return None  # child didn't split

        promoted_key, left_id, right_id = result
        # Insert promoted key and right child pointer into this internal node
        node.keys.insert(idx, promoted_key)
        node.children[idx] = left_id
        node.children.insert(idx + 1, right_id)

        if not node.is_full():
            self._save_node(node)
            return None
        else:
            return self._split_internal(node)
```

**Handling root splits** (in `insert()`):
```python
def insert(self, key, value):
    result = self._insert_recursive(key, value, self.root_page_id)
    if result is not None:
        promoted_key, left_id, right_id = result
        # Create a new root
        new_root = BTreeNode(self.dm.allocate_page(), is_leaf=False)
        new_root.keys = [promoted_key]
        new_root.children = [left_id, right_id]
        self._save_node(new_root)
        self.root_page_id = new_root.page_id
        # Persist the new root page id somewhere (file header or metadata page)
```

**Test (comprehensive):**
```python
def test_insert_triggers_split():
    # Insert 2*ORDER keys to force at least one split
    for i in range(2 * ORDER):
        tree.insert(i, RecordPointer(i, 0))
    # All keys must still be findable
    for i in range(2 * ORDER):
        ptr = tree.search(i)
        assert ptr is not None
        assert ptr.page_id == i

def test_tree_properties_after_splits():
    for i in range(500):
        tree.insert(i, RecordPointer(i // 10, i % 10))
    # Test sorted order via range scan
    results = tree.range_scan(100, 200)
    assert len(results) == 101
    assert results[0].page_id == 10  # key 100 → RecordPointer(10, 0)
```

---

### Task 2.5 — Range Scan (30–45 min)

This is where the leaf linked list pays off.

```python
def range_scan(self, lo: int, hi: int) -> list[RecordPointer]:
    # 1. Find the leaf containing 'lo'
    # 2. Walk forward through leaf.next_leaf pointers
    # 3. Collect all values where lo <= key <= hi
    # 4. Stop when key > hi or next_leaf == 0
    ...
```

This operation is O(k + log n) where k is the number of results — optimal.

---

### Task 2.6 — Delete (60–90 min)

Implement lazy deletion first (simpler, still correct):

```python
def delete(self, key: int) -> bool:
    # Find the leaf containing the key
    # Mark the entry as deleted (e.g., set key = -1 or use a deleted flag)
    # Save the leaf
    # Return True if key was found, False otherwise
    ...
```

Then implement proper deletion with borrowing/merging as a mini challenge.

---

## 💡 Thinking Questions

1. In a B+ Tree of order 100, what is the maximum number of keys you can store in a 3-level tree?
2. Why do we promote the *first key of the right child* during a leaf split, but the *middle key itself* (removed from both sides) during an internal split?
3. Why does search always read exactly `height` pages? Could it ever read more?
4. If you insert keys in sorted order (1, 2, 3, 4, ...), what does the tree look like? Is it still balanced? (This is called a *sequential insertion* problem — think about how real databases handle it.)
5. What is the relationship between B-Tree order and page size? How would you calculate the optimal order for your specific key and pointer sizes?
6. If you lose the root page to disk corruption, can you recover the tree? What does this tell you about how critical the root page is?

---

## ⚠️ Common Mistakes

**Mistake 1: Confusing B-Tree and B+ Tree split semantics**
In a B-Tree, the promoted key is removed from the child and placed in the parent. In a B+ Tree, for leaf splits, the promoted key *stays in the right leaf* AND goes up to the parent. For internal splits, the middle key is removed from both children. These rules are different and mixing them corrupts the tree.

**Mistake 2: Not updating leaf sibling pointers after a split**
After splitting leaf L into L and L', you must update:
- `L.next_leaf = L'.page_id`
- `L'.prev_leaf = L.page_id`
- If L had a right sibling R: `R.prev_leaf = L'.page_id` and `L'.next_leaf = R.page_id`

Forgetting this breaks range scans.

**Mistake 3: Root splits not updating the tree's root_page_id**
After a root split, the new root has a new page_id. If you don't persist this, the next process restart loads the old root and your tree is disconnected.

**Mistake 4: Off-by-one in child index during search**
The standard formula: for a node with keys `[k0, k1, k2]` and children `[c0, c1, c2, c3]`, key `k` goes to child `c_i` where `i = number of keys strictly less than k`. Use `bisect_right` not `bisect_left` for this.

**Mistake 5: Modifying a node in memory but forgetting to save it**
Every time you modify a node, you must call `_save_node(node)`. Not `write_page` directly — your helper should handle serialization. If you forget, the change lives only in RAM and is lost on restart.

**Mistake 6: Allocating a page but not initializing it**
`allocate_page()` returns a page_id but the page on disk is uninitialized (zeros). If you load it and don't write a valid node, `deserialize` will read garbage.

---

## 🧪 Mini Challenges

1. **Visualization**: Write a `print_tree(tree)` function that prints the B-Tree level by level in ASCII. This is invaluable for debugging splits.

2. **Full deletion with rebalancing**: Implement proper delete with borrow-from-sibling and merge-with-sibling. This is the hardest algorithm in this project.

3. **Duplicate keys**: Modify the tree to support duplicate keys (e.g., a secondary index on a non-unique column). One approach: store values as a list per key. Another: append a sequence number to make all keys unique.

4. **Benchmarking**: Insert 100,000 sequential keys and 100,000 random keys. Measure the tree height in both cases. Are they the same? Why or why not?

5. **Bulk loading**: Look up "B-Tree bulk loading" — a technique to build a B-Tree directly from sorted data in O(n) instead of O(n log n) insertions. Implement it.

---

## 📦 Deliverable

At the end of Phase 2, the following must work:

```python
from storage.disk_manager import DiskManager
from index.btree import BTree
from index.btree_page import BTreeNode, RecordPointer

dm = DiskManager("data/index.db")
root_page = dm.allocate_page()
tree = BTree(dm, root_page)

# Insert 1000 keys
for i in range(1000):
    tree.insert(i * 10, RecordPointer(i, 0))

# Point lookup
ptr = tree.search(500)
assert ptr == RecordPointer(50, 0)

# Range scan
results = tree.range_scan(100, 200)
assert len(results) == 11  # keys 100,110,...,200

# Persistence
dm.close()
dm2 = DiskManager("data/index.db")
tree2 = BTree(dm2, root_page)
assert tree2.search(500) == RecordPointer(50, 0)
dm2.close()
```

---

## 🔍 Debugging Guide

**Problem**: `search(key)` returns `None` after inserting  
**Cause**: Either the insert didn't save the node, or a split corrupted the routing  
**Fix**: Print the tree after every insert using your visualization function

**Problem**: Tree structure looks wrong after many inserts  
**Cause**: A split is creating nodes but not correctly linking parent pointers  
**Fix**: After every 10th insert, walk the entire tree and assert: every key in a child node is within the range defined by the parent's keys

**Problem**: Range scan returns wrong number of results  
**Cause**: `next_leaf` pointers are not updated during splits  
**Fix**: After a leaf split, print all leaf nodes' `next_leaf` and `prev_leaf` values. They should form a complete chain.

**Problem**: Tree height keeps growing but never balances  
**Cause**: Split is creating nodes with wrong key counts  
**Fix**: Assert that after every split, both resulting nodes have between `ORDER-1` and `2*ORDER-1` keys.

**Problem**: Second session loads the wrong root  
**Cause**: `root_page_id` is stored in a variable, not persisted to the file header  
**Fix**: Store `root_page_id` in the DiskManager's file header. Update it whenever the root changes.

---

## 📘 What to Write in Your learning.md

After completing this phase, add entries for:

1. **Why B-Trees exist** — the problem they solve, comparison to BST and hash maps
2. **B-Tree vs B+ Tree** — exact differences, why databases use B+ Trees
3. **Node splitting** — leaf split vs internal split, what gets promoted and why
4. **Persistence** — how tree nodes map to pages, how the root page_id is tracked
5. **Range scans** — why the leaf linked list makes range scans O(k + log n)
6. **Your experience** — what was the hardest part, what bugs you hit, how you fixed them

---

*When this phase is done and all tests pass, move to `03_query_engine.md`.*
