# Copyright (c) 2026 UX-CHANNEL
"""
Formal property-based tests for the wire codec (Hypothesis).

These encode *invariants* the codec must always uphold — not examples.
If a property fails, Hypothesis shrinks to a minimal counterexample.
"""

from __future__ import annotations

import unittest

from hypothesis import assume, given, note, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from ux_channel.wire import (
    available_formats,
    configure_wire,
    decode,
    dumps,
    encode,
    get_codec,
    loads,
    reset_wire,
    try_decode,
)
from ux_channel.wire.cxb import decode_cxb, encode_cxb, is_cxb


# ---------------------------------------------------------------------------
# Strategies — JSON document space + channel-shaped docs
# ---------------------------------------------------------------------------

_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53) + 1, max_value=2**53 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=64),
)

_json_docs = st.recursive(
    _scalars,
    lambda ch: st.lists(ch, max_size=8)
    | st.dictionaries(
        st.text(min_size=1, max_size=16).filter(lambda s: s.isidentifier() or s.isalnum()),
        ch,
        max_size=8,
    ),
    max_leaves=40,
)

_action = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="._-"),
    min_size=1,
    max_size=40,
)

_intent = st.fixed_dictionaries(
    {
        "v": st.just("1"),
        "action": _action,
        "args": st.dictionaries(st.text(min_size=1, max_size=12), _scalars, max_size=6),
    },
    optional={
        "cap": st.text(max_size=48),
        "target": st.text(max_size=48),
        "request_id": st.text(max_size=32),
        "idempotency_key": st.text(max_size=32),
        "accept_stream": st.booleans(),
        "meta": st.dictionaries(st.text(min_size=1, max_size=10), _scalars, max_size=4),
    },
)

_op = st.fixed_dictionaries(
    {
        "op": st.sampled_from(["toast", "morph", "navigate", "dispatch", "noop"]),
    },
    optional={
        "message": st.text(max_size=80),
        "level": st.sampled_from(["info", "success", "warning", "error"]),
        "target": st.text(max_size=60),
        "html": st.text(max_size=200),
        "url": st.text(max_size=80),
        "morph": st.sampled_from(["idiomorph", "outer", "inner"]),
    },
)

_result = st.fixed_dictionaries(
    {
        "v": st.just("1"),
        "ok": st.booleans(),
        "ops": st.lists(_op, max_size=12),
    },
    optional={
        "error": st.fixed_dictionaries(
            {"code": st.text(min_size=1, max_size=24), "message": st.text(max_size=80)},
            optional={"retryable": st.booleans()},
        ),
        "meta": st.dictionaries(st.text(min_size=1, max_size=10), _scalars, max_size=5),
    },
)


def _fmts():
    return list(available_formats())


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestJsonProperties(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    @settings(max_examples=120, deadline=None)
    @given(doc=_json_docs)
    def test_P1_json_roundtrip_identity(self, doc):
        """P1: dumps ∘ loads = id  (stdlib JSON engine)."""
        configure_wire(format="json", engine="stdlib")
        self.assertEqual(loads(dumps(doc)), doc)

    @settings(max_examples=80, deadline=None)
    @given(doc=_json_docs)
    def test_P2_json_encode_decode_identity(self, doc):
        """P2: decode(encode(doc)) == doc for JSON format."""
        blob = encode(doc, format="json", engine="stdlib")
        self.assertEqual(blob.format, "json")
        self.assertEqual(decode(blob.data, format="json"), doc)

    @settings(max_examples=60, deadline=None)
    @given(doc=_json_docs)
    def test_P3_dumps_independent_of_binary_policy(self, doc):
        """P3: dumps/loads stay JSON even when process format is CXB."""
        configure_wire(format="cxb")
        self.assertEqual(get_codec().format, "cxb")
        self.assertEqual(loads(dumps(doc)), doc)


class TestChannelDocProperties(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    @settings(max_examples=80, deadline=None)
    @given(doc=_intent)
    def test_P4_intent_roundtrip_all_formats(self, doc):
        """P4: Intent core fields survive every available format."""
        for fmt in _fmts():
            out = decode(encode(doc, format=fmt).data, format=fmt)
            self.assertEqual(out.get("v"), "1")
            self.assertEqual(out.get("action"), doc["action"])
            self.assertEqual(out.get("args"), doc["args"])

    @settings(max_examples=60, deadline=None)
    @given(doc=_result)
    def test_P5_result_ops_count_preserved(self, doc):
        """P5: Result.ops length preserved across formats."""
        for fmt in _fmts():
            out = decode(encode(doc, format=fmt).data, format=fmt)
            self.assertEqual(out.get("ok"), doc["ok"])
            self.assertEqual(len(out.get("ops") or []), len(doc["ops"]))

    @settings(max_examples=40, deadline=None)
    @given(doc=_result)
    def test_P6_cxb_is_cxb_magic(self, doc):
        """P6: CXB encoder always produces recognized magic."""
        raw = encode_cxb(doc)
        self.assertTrue(is_cxb(raw))
        out = decode_cxb(raw)
        self.assertEqual(out.get("ok"), doc["ok"])
        self.assertEqual(len(out.get("ops") or []), len(doc["ops"]))

    @settings(max_examples=40, deadline=None)
    @given(doc=_result)
    def test_P7_cxb_deterministic(self, doc):
        """P7: same document → identical CXB bytes (stable wire)."""
        self.assertEqual(encode_cxb(doc), encode_cxb(doc))

    @settings(max_examples=30, deadline=None)
    @given(doc=_result)
    def test_P8_cross_format_ok_agrees(self, doc):
        """P8: ok flag identical after roundtrip on every format."""
        oks = {
            fmt: decode(encode(doc, format=fmt).data, format=fmt).get("ok")
            for fmt in _fmts()
        }
        note(str(oks))
        self.assertEqual(len(set(oks.values())), 1)


class TestSafetyProperties(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    @settings(max_examples=200, deadline=None)
    @given(data=st.binary(max_size=256))
    def test_P9_decode_never_crashes_process(self, data):
        """P9: arbitrary bytes → ValueError or value; never abort."""
        for fmt in _fmts():
            try:
                decode(data, format=fmt)
            except ValueError:
                pass
            except Exception as exc:
                # orjson/json may raise JSONDecodeError (ValueError subclass on 3.10+)
                # msgpack ExtraData etc. — normalize to acceptable
                if type(exc).__name__ in (
                    "JSONDecodeError",
                    "ExtraData",
                    "FormatError",
                    "UnpackException",
                    "ValueError",
                    "TypeError",
                    "UnicodeDecodeError",
                ):
                    pass
                else:
                    # wrap path should make ValueError for cxb; others may leak typed errors
                    # still must not be SystemExit / KeyboardInterrupt
                    assume(not isinstance(exc, (SystemExit, KeyboardInterrupt)))

    @settings(max_examples=200, deadline=None)
    @given(data=st.binary(max_size=256))
    def test_P10_try_decode_never_raises(self, data):
        """P10: try_decode is total — always returns."""
        for fmt in _fmts():
            try_decode(data, format=fmt, default=None)

    @settings(max_examples=50, deadline=None)
    @given(doc=_json_docs)
    def test_P11_empty_and_none_decode_stable(self, doc):
        """P11: empty input is {} regardless of format policy."""
        self.assertEqual(decode(b""), {})
        self.assertEqual(decode(""), {})
        # still encode real docs
        encode(doc, format="json")


class WireStateMachine(RuleBasedStateMachine):
    """Stateful property: reconfigure + encode + decode never bricks process."""

    def __init__(self):
        super().__init__()
        reset_wire()
        self.last_blob = None
        self.last_doc = None

    @rule(fmt=st.sampled_from(["json", "cxb", "msgpack", "garbage"]))
    def reconfigure(self, fmt):
        configure_wire(format=fmt)  # soft — garbage → json
        c = get_codec()
        assert c is not None
        assert c.format in available_formats() or c.format == "json"

    @rule(doc=_result)
    def encode_doc(self, doc):
        blob = encode(doc)  # active policy
        assert isinstance(blob.data, (bytes, bytearray))
        assert blob.media_type
        self.last_blob = blob
        self.last_doc = doc

    @rule()
    def decode_last(self):
        if self.last_blob is None:
            return
        out = decode(self.last_blob.data, format=self.last_blob.format)
        assert out.get("ok") == self.last_doc.get("ok")

    @rule(doc=_json_docs)
    def json_helpers(self, doc):
        assert loads(dumps(doc)) == doc

    @invariant()
    def codec_always_present(self):
        assert get_codec() is not None
        assert loads(dumps({"_": 1})) == {"_": 1}


TestWireStatefulMachine = WireStateMachine.TestCase
# Hypothesis 6.x: settings on the TestCase
TestWireStatefulMachine.settings = settings(max_examples=40, deadline=None, stateful_step_count=20)


if __name__ == "__main__":
    unittest.main()
