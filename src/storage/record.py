import struct


class RecordSerializer:
    def __init__(self, schema):
        """
        schema: list of (field_name, field_type)
        Example: [('id', 'int'), ('name', 'str'), ('age', 'int')]
        """
        self.schema = schema

    def serialize(self, row):
        """
        Convert tuple → bytes
        """
        result = bytearray()

        for (field_name, field_type), value in zip(self.schema, row):
            if field_type == 'int':
                result += struct.pack('>i', value)

            elif field_type == 'str':
                encoded = value.encode('utf-8')
                length = len(encoded)

                result += struct.pack('>H', length)  # 2-byte length
                result += encoded

            else:
                raise ValueError(f"Unsupported type: {field_type}")

        return bytes(result)

    def deserialize(self, data):
        """
        Convert bytes → tuple
        """
        values = []
        offset = 0

        for field_name, field_type in self.schema:
            if field_type == 'int':
                value = struct.unpack_from('>i', data, offset)[0]
                offset += 4

            elif field_type == 'str':
                length = struct.unpack_from('>H', data, offset)[0]
                offset += 2

                value = data[offset:offset + length].decode('utf-8')
                offset += length

            else:
                raise ValueError(f"Unsupported type: {field_type}")

            values.append(value)

        return tuple(values)