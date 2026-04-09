from src.storage.page import Page

def test_add_and_get_record():
    page = Page(1)
    slot = page.add_record(b'hello')
    assert page.get_record(slot) == b'hello'


def test_delete_record():
    page = Page(1)
    slot = page.add_record(b'hello')
    page.delete_record(slot)
    assert page.get_record(slot) is None


def test_multiple_records():
    page = Page(1)
    s1 = page.add_record(b'one')
    s2 = page.add_record(b'two')

    assert page.get_record(s1) == b'one'
    assert page.get_record(s2) == b'two'


def test_serialization_roundtrip():
    page = Page(1)
    page.add_record(b'abc')
    page.add_record(b'def')

    raw = page.to_bytes()
    restored = Page.from_bytes(1, raw)

    assert restored.get_record(0) == b'abc'
    assert restored.get_record(1) == b'def'