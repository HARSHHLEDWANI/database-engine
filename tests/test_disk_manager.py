import os
from src.storage.disk_manager import DiskManager, PAGE_SIZE



TEST_DB = "data/test.db"


def setup_function():
    # Remove old test file before each test
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_write_and_read_survives_reopen():
    dm = DiskManager(TEST_DB)

    page_id = dm.allocate_page()

    data = bytearray(PAGE_SIZE)
    data[0:4] = b'TEST'

    dm.write_page(page_id, data)
    dm.close()

    # reopen
    dm2 = DiskManager(TEST_DB)
    result = dm2.read_page(page_id)

    assert result[0:4] == b'TEST'

    dm2.close()


def test_allocate_page_increases_count():
    dm = DiskManager(TEST_DB)

    initial = dm.num_pages()
    dm.allocate_page()
    dm.allocate_page()

    assert dm.num_pages() == initial + 2

    dm.close()


def test_read_nonexistent_page_returns_zero():
    dm = DiskManager(TEST_DB)

    data = dm.read_page(10)  # page doesn't exist
    assert data == bytearray(PAGE_SIZE)

    dm.close()


def test_write_invalid_size_raises():
    dm = DiskManager(TEST_DB)

    try:
        dm.write_page(1, b"too small")
        assert False  # should not reach here
    except ValueError:
        assert True

    dm.close()