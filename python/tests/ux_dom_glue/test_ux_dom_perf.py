"""UxDom glue performance helpers."""

from __future__ import annotations

from ux_channel_ux_dom import CompileCache, batch_inject, inject_uids_cached, structure_hash


def _tree(n=5):
    return {
        "tag": "div",
        "children": [{"tag": "span", "key": str(i), "children": []} for i in range(n)],
    }


def test_structure_hash_stable():
    a = structure_hash(_tree())
    b = structure_hash(_tree())
    assert a == b


def test_compile_cache_hits():
    cache = CompileCache(maxsize=32)
    t = _tree()
    cache.inject(t, prefix="p")
    cache.inject(t, prefix="p")
    assert cache.hits >= 1
    assert cache.misses >= 1


def test_inject_uids_cached():
    ann1, sm1 = inject_uids_cached(_tree(), prefix="z")
    ann2, sm2 = inject_uids_cached(_tree(), prefix="z")
    assert set(sm1.uids) == set(sm2.uids)
    assert ann1["attrs"]["data-channel-id"]


def test_batch_inject():
    out = batch_inject([_tree(2), _tree(3)], prefix="b")
    assert len(out) == 2
    assert out[0][1].uids
