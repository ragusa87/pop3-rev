import os
from typing import BinaryIO
from struct import Struct


def conv_index(mem_index):
    return mem_index + 8704


class BinStruct:
    def __init__(self, location, count, fmt, conv_func=None):
        self._location = location
        self._count = count
        self._fmt = Struct(fmt)
        self._conv_func = conv_func if conv_func else BinStruct._def_conv

    def parse(self, fd: BinaryIO):
        fd.seek(conv_index(self._location), os.SEEK_SET)
        buf = fd.read(self._fmt.size * self._count)
        return list(self._conv_func(obj) for obj in zip(range(0, self._count), self._fmt.iter_unpack(buf)))

    @staticmethod
    def _def_conv(arg):
        return arg

    @staticmethod
    def conv_single(arg):
        return arg[0], arg[1][0]


UNIT_TYPE_TO_OBJ = BinStruct(0x1a6d50, 276, "<h", BinStruct.conv_single)
OBJ_INDEXES = BinStruct(0x1a6858, 319, "<h", BinStruct.conv_single)


def main():
    EXE_PATH = '/home/ddd/.wine/drive_c/GOG Games/Populous 3/D3DPopTB.exe'
    with open(EXE_PATH, 'rb', buffering=0) as fd:
        unit_to_obj = UNIT_TYPE_TO_OBJ.parse(fd)
        print(f"unit_to_obj = {unit_to_obj}")
        obj_indexes = OBJ_INDEXES.parse(fd)
        print(f"obj_indexes = {obj_indexes}")

main()
