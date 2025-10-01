import os
from typing import BinaryIO
from struct import Struct


def conv_index(mem_index):
    return mem_index - 8704


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

    @staticmethod
    def conv_double(arg):
        return arg[0], arg[1]


class ObjIndex:
    def __init__(self, arg_tuple):
        self.index = arg_tuple[0]
        self.rel_index = arg_tuple[1]

    def __repr__(self):
        return f"ObjIndex(index={self.index}, rel_index={self.rel_index})"

    def __str__(self):
        return self.__repr__()

    @staticmethod
    def conv(arg):
        return arg[0], ObjIndex(arg[1])


class ObjRelated:
    def __init__(self, arg_tuple):
        self.type = arg_tuple[0]
        self.f1 = arg_tuple[1]
        self._f1 = arg_tuple[2]
        self._f2 = arg_tuple[3]
        self._f3 = arg_tuple[4]
        self.person_type_1 = arg_tuple[5]
        self.person_type_2 = arg_tuple[6]
        self.palette_index = arg_tuple[7]
        self._f4 = arg_tuple[8]
        self.flags = arg_tuple[9]

    def __repr__(self):
        return f"ObjRelated(type={self.type}, " \
               f"f1={self.f1}, " \
               f"_f1={self._f1}. " \
               f"_f2={self._f2}. " \
               f"_f3={self._f3}. " \
               f"person_type_1={self.person_type_1}, " \
               f"person_type_2={self.person_type_2}, " \
               f"palette_index={self.palette_index}, " \
               f"_f4={self._f4}. " \
               f"flags=0x{self.flags:04x})"

    def __str__(self):
        return self.__repr__()

    @staticmethod
    def conv(arg):
        return arg[0], ObjRelated(arg[1])


UNIT_TYPE_TO_OBJ = BinStruct(0x1a6d50, 276, "<h", BinStruct.conv_single)
OBJ_INDEXES = BinStruct(0x1a6858, 159, "<hh", ObjIndex.conv)
OBJ_RELATED = BinStruct(0x1a6ad7, 43, "<BBbbbBBBbH", ObjRelated.conv)


def main():
    EXE_PATH = '/home/ddd/.wine/drive_c/GOG Games/Populous 3/D3DPopTB.exe'
    print(f"Size ObjRelated={OBJ_RELATED._fmt.size}")
    with open(EXE_PATH, 'rb', buffering=0) as fd:
        unit_to_obj = UNIT_TYPE_TO_OBJ.parse(fd)
        print(f"unit_to_obj = {unit_to_obj}")
        obj_indexes = OBJ_INDEXES.parse(fd)
        obj_related = OBJ_RELATED.parse(fd)
        for obj_i in obj_indexes:
            print(f"{obj_i} - rel_index_m={obj_i[1].rel_index+3}")
        for obj_r in obj_related:
            print(f"{obj_r}")

main()
