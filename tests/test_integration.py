from src.storage.disk_manager import DiskManager
from src.storage.page import Page
from src.storage.record import RecordSerializer
import os

TEST_DB = "data/test.db"


def setup_function():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_full_storage_cycle():
    schema = [('id', 'int'), ('name', 'str'), ('age', 'int')]
    ser = RecordSerializer(schema)

    # ---------- WRITE ----------
    dm = DiskManager(TEST_DB)

    page_id = dm.allocate_page()
    page = Page(page_id)

    row1 = (1, 'alice', 25)
    row2 = (2, 'bob', 30)

    page.add_record(ser.serialize(row1))
    page.add_record(ser.serialize(row2))

    dm.write_page(page_id, page.to_bytes())
    dm.close()

    # ---------- READ ----------
    dm = DiskManager(TEST_DB)

    raw = dm.read_page(page_id)
    page = Page.from_bytes(page_id, raw)

    result1 = ser.deserialize(page.get_record(0))
    result2 = ser.deserialize(page.get_record(1))

    dm.close()

    # ---------- ASSERT ----------
    assert result1 == row1
    assert result2 == row2