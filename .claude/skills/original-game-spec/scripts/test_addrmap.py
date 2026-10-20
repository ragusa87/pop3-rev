import pytest

from addrmap import MAP_PATH, AddrMap

SAMPLE = [
    "# kind\td3d\tpoptb\tvotes\n",
    "code\t4ed8a0\t4afc70\t1\n",
    "data\t89d178\t885710\t372\n",
    "data\t89d1c8\t885760\t125\n",
    "data\t8a0000\t123456\t1\n",
]


def test_exact_code_and_data():
    m = AddrMap(SAMPLE)
    assert m.to_poptb(0x4ED8A0) == 0x4AFC70
    assert m.to_poptb(0x89D1C8) == 0x885760


def test_field_inside_struct_uses_closest_anchor_below():
    assert AddrMap(SAMPLE).to_poptb(0x89D1C8 + 0xC65 + 0x10) == 0x885760 + 0xC65 + 0x10


def test_single_vote_entries_are_not_anchors():
    assert AddrMap(SAMPLE).to_poptb(0x8A0004) == 0x8A0004 - 0x17A68


def test_below_every_anchor_raises():
    with pytest.raises(KeyError):
        AddrMap(SAMPLE).to_poptb(0x400000)


def test_shipped_map_game_state():
    m = AddrMap.load(MAP_PATH)
    for d3d in (0x89D188, 0x89D1C8, 0x8E0428, 0x890390, 0x89C6F0):
        assert m.to_poptb(d3d) == d3d - 0x17A68
