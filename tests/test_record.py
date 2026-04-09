from src.storage.record import RecordSerializer


def test_serialize_deserialize_roundtrip():
    schema = [('id', 'int'), ('name', 'str'), ('age', 'int')]
    ser = RecordSerializer(schema)

    row = (1, 'alice', 25)

    encoded = ser.serialize(row)
    decoded = ser.deserialize(encoded)

    assert decoded == row


def test_variable_length_string():
    schema = [('id', 'int'), ('bio', 'str')]
    ser = RecordSerializer(schema)

    row = (42, 'a' * 200)

    encoded = ser.serialize(row)
    decoded = ser.deserialize(encoded)

    assert decoded == row


def test_multiple_rows():
    schema = [('id', 'int'), ('name', 'str')]
    ser = RecordSerializer(schema)

    rows = [
        (1, 'alice'),
        (2, 'bob'),
        (3, 'charlie')
    ]

    for row in rows:
        assert ser.deserialize(ser.serialize(row)) == row