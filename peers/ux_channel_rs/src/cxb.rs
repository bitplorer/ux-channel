//! CXB — Channel eXchange Binary (CXB1 + CXBZ).
//!
//! Compatible with Python `ux_channel.wire.cxb` pure-Python oracle and the
//! frozen blobs under `conformance/expected/cxb/`.
//!
//! Media type: `application/ux-channel+cxb`
//!
//! Notes:
//! - Freeform maps (`W_FREE`) use MessagePack (`rmp-serde`), matching Python
//!   when `msgpack` is installed. Map key order may differ → encode bytes are
//!   not always sha256-identical to the oracle; decode of oracle blobs is.
//! - Binary wire type (`W_BYTES`) decodes to a JSON array of integers (0–255)
//!   so the result stays JSON-serializable without a parallel binary type.

use crate::op_tags::{op_key_tag, op_tag_key};
use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use serde_json::{Map, Number, Value};
use std::collections::HashMap;
use std::io::{Read, Write};
use thiserror::Error;

pub const MAGIC: &[u8; 4] = b"CXB1";
pub const MAGIC_Z: &[u8; 4] = b"CXBZ";
pub const MEDIA_TYPE: &str = "application/ux-channel+cxb";
pub const FORMAT_NAME: &str = "cxb";

const KIND_INTENT: u8 = 1;
const KIND_RESULT: u8 = 2;
const KIND_DOC: u8 = 3;

const W_NULL: u8 = 0;
const W_FALSE: u8 = 1;
const W_TRUE: u8 = 2;
const W_VARINT: u8 = 3;
const W_F64: u8 = 4;
const W_UTF8: u8 = 5;
const W_BYTES: u8 = 6;
const W_ARRAY: u8 = 7;
const W_MAP: u8 = 8;
const W_FREE: u8 = 9;
const W_INTERN: u8 = 10;
const W_OPMAP: u8 = 11;
const OP_FREE_KEY: u8 = 0xFF;

const MAX_TABLE: usize = 512;
const MAX_TABLE_BYTES: usize = 16 * 1024;
const MAX_NEST: usize = 64;
const MAX_BLOB: usize = 32 * 1024 * 1024;
const MAX_ARRAY: usize = 1_000_000;
const MAX_FIELDS: usize = 100_000;
const INTERN_MAX: usize = 128;
const INTERN_OP_MAX: usize = 96;
const INTERN_MIN_FREQ: usize = 2;
const CXBZ_MIN_PLAIN: usize = 384;
const CXBZ_MIN_SAVE: usize = 48;
const CXBZ_MIN_RATIO: f64 = 1.20;
const CXBZ_LEVEL: u32 = 6;

const I_V: u16 = 1;
const I_ACTION: u16 = 2;
const I_ARGS: u16 = 3;
const I_CAP: u16 = 4;
const I_TARGET: u16 = 5;
const I_REQUEST_ID: u16 = 6;
const I_FORM: u16 = 7;
const I_ACCEPT_STREAM: u16 = 8;
const I_IDEMPOTENCY: u16 = 9;
const I_META: u16 = 10;

const R_V: u16 = 1;
const R_OK: u16 = 2;
const R_OPS: u16 = 3;
const R_ERROR: u16 = 4;
const R_META: u16 = 5;

#[derive(Debug, Error)]
pub enum CxbError {
    #[error("CXB: {0}")]
    Msg(String),
}

impl CxbError {
    fn msg(s: impl Into<String>) -> Self {
        CxbError::Msg(s.into())
    }
}

pub fn is_cxb(data: &[u8]) -> bool {
    data.len() >= 4 && (data.starts_with(MAGIC) || data.starts_with(MAGIC_Z))
}

fn write_varint(buf: &mut Vec<u8>, mut n: u64) {
    while n >= 0x80 {
        buf.push((n as u8 & 0x7F) | 0x80);
        n >>= 7;
    }
    buf.push(n as u8);
}

fn read_varint_at(data: &[u8], i: &mut usize) -> Result<u64, CxbError> {
    let mut n = 0u64;
    let mut shift = 0;
    loop {
        if *i >= data.len() {
            return Err(CxbError::msg("truncated varint"));
        }
        let b = data[*i];
        *i += 1;
        n |= ((b & 0x7F) as u64) << shift;
        if b & 0x80 == 0 {
            break;
        }
        shift += 7;
        if shift > 63 {
            return Err(CxbError::msg("varint overflow"));
        }
    }
    Ok(n)
}

fn zigzag_encode(n: i64) -> u64 {
    ((n << 1) ^ (n >> 63)) as u64
}

fn zigzag_decode(n: u64) -> i64 {
    ((n >> 1) as i64) ^ (-((n & 1) as i64))
}

fn crc32_payload(data: &[u8]) -> u32 {
    crc32fast::hash(data)
}

fn is_payload_key(k: &str) -> bool {
    matches!(
        k,
        "html" | "body" | "text" | "cap" | "bytes" | "payload" | "data"
    )
}

fn free_dumps(obj: &Value) -> Result<Vec<u8>, CxbError> {
    rmp_serde::to_vec_named(obj).map_err(|e| CxbError::msg(format!("msgpack: {e}")))
}

fn free_loads(data: &[u8]) -> Result<Value, CxbError> {
    if data.is_empty() {
        return Ok(Value::Null);
    }
    if let Ok(v) = rmp_serde::from_slice::<Value>(data) {
        return Ok(v);
    }
    let s = std::str::from_utf8(data).map_err(|_| CxbError::msg("freeform utf8"))?;
    serde_json::from_str(s).map_err(|e| CxbError::msg(format!("freeform json: {e}")))
}

struct StrTable {
    strs: Vec<String>,
    index: HashMap<String, u16>,
    nbytes: usize,
}

impl StrTable {
    fn new() -> Self {
        Self {
            strs: vec![],
            index: HashMap::new(),
            nbytes: 0,
        }
    }
    fn try_intern(&mut self, s: &str, allow: &HashMap<String, ()>) -> Option<u16> {
        if s.is_empty() || s.len() > INTERN_MAX || !allow.contains_key(s) {
            return None;
        }
        if let Some(&i) = self.index.get(s) {
            return Some(i);
        }
        if self.strs.len() >= MAX_TABLE || self.nbytes + s.len() > MAX_TABLE_BYTES {
            return None;
        }
        let i = self.strs.len() as u16;
        self.strs.push(s.to_string());
        self.index.insert(s.to_string(), i);
        self.nbytes += s.len();
        Some(i)
    }
    fn write_to(&self, buf: &mut Vec<u8>) {
        write_varint(buf, self.strs.len() as u64);
        for s in &self.strs {
            write_varint(buf, s.len() as u64);
            buf.extend_from_slice(s.as_bytes());
        }
    }
}

fn note_str(freq: &mut HashMap<String, usize>, s: &str, max_len: usize) {
    if !s.is_empty() && s.len() <= max_len {
        *freq.entry(s.to_string()).or_insert(0) += 1;
    }
}

fn collect_freq(doc: &Map<String, Value>, freq: &mut HashMap<String, usize>) {
    for key in ["v", "action", "target", "request_id", "idempotency_key"] {
        if let Some(Value::String(s)) = doc.get(key) {
            note_str(freq, s, INTERN_MAX);
        }
    }
    if let Some(Value::Array(ops)) = doc.get("ops") {
        for op in ops {
            if let Value::Object(d) = op {
                for (k, v) in d {
                    if is_payload_key(k) {
                        continue;
                    }
                    if let Value::String(s) = v {
                        note_str(freq, s, INTERN_OP_MAX);
                    }
                }
            }
        }
    }
}

fn allow_from_freq(freq: &HashMap<String, usize>) -> HashMap<String, ()> {
    let mut ranked: Vec<_> = freq
        .iter()
        .filter(|(_, &c)| c >= INTERN_MIN_FREQ)
        .map(|(s, &c)| (c, -(s.len() as isize), s.clone()))
        .collect();
    ranked.sort_by(|a, b| b.cmp(a));
    let mut allow = HashMap::new();
    let mut nbytes = 0usize;
    for (_, _, s) in ranked {
        if allow.len() >= MAX_TABLE {
            break;
        }
        if nbytes + s.len() > MAX_TABLE_BYTES {
            continue;
        }
        nbytes += s.len();
        allow.insert(s, ());
    }
    allow
}

fn write_value(
    buf: &mut Vec<u8>,
    tab: &mut StrTable,
    allow: &HashMap<String, ()>,
    v: &Value,
    intern_ok: bool,
    depth: usize,
) -> Result<(), CxbError> {
    if depth > MAX_NEST {
        return Err(CxbError::msg("CXB nest too deep"));
    }
    match v {
        Value::Null => buf.push(W_NULL),
        Value::Bool(false) => buf.push(W_FALSE),
        Value::Bool(true) => buf.push(W_TRUE),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                buf.push(W_VARINT);
                write_varint(buf, zigzag_encode(i));
            } else if let Some(u) = n.as_u64() {
                if u <= i64::MAX as u64 {
                    buf.push(W_VARINT);
                    write_varint(buf, zigzag_encode(u as i64));
                } else {
                    buf.push(W_F64);
                    buf.extend_from_slice(&(u as f64).to_be_bytes());
                }
            } else if let Some(f) = n.as_f64() {
                buf.push(W_F64);
                buf.extend_from_slice(&f.to_be_bytes());
            } else {
                return Err(CxbError::msg("unsupported number"));
            }
        }
        Value::String(s) => {
            if intern_ok {
                if let Some(idx) = tab.try_intern(s, allow) {
                    buf.push(W_INTERN);
                    buf.extend_from_slice(&idx.to_be_bytes());
                    return Ok(());
                }
            }
            buf.push(W_UTF8);
            write_varint(buf, s.len() as u64);
            buf.extend_from_slice(s.as_bytes());
        }
        Value::Array(arr) => {
            if arr.len() > MAX_ARRAY {
                return Err(CxbError::msg("CXB array too large"));
            }
            buf.push(W_ARRAY);
            write_varint(buf, arr.len() as u64);
            for item in arr {
                write_value(buf, tab, allow, item, true, depth + 1)?;
            }
        }
        Value::Object(_) => {
            let blob = free_dumps(v)?;
            if blob.len() > MAX_BLOB {
                return Err(CxbError::msg("CXB freeform too large"));
            }
            buf.push(W_FREE);
            write_varint(buf, blob.len() as u64);
            buf.extend_from_slice(&blob);
        }
    }
    Ok(())
}

fn write_field(
    buf: &mut Vec<u8>,
    tab: &mut StrTable,
    allow: &HashMap<String, ()>,
    tag: u16,
    v: &Value,
    intern_ok: bool,
) -> Result<(), CxbError> {
    buf.extend_from_slice(&tag.to_be_bytes());
    write_value(buf, tab, allow, v, intern_ok, 0)
}

fn write_op(
    buf: &mut Vec<u8>,
    tab: &mut StrTable,
    allow: &HashMap<String, ()>,
    op: &Value,
) -> Result<(), CxbError> {
    let Value::Object(d) = op else {
        return write_value(buf, tab, allow, op, true, 0);
    };
    if d.len() > 255 {
        return write_value(buf, tab, allow, op, false, 0);
    }
    buf.push(W_OPMAP);
    buf.push(d.len() as u8);
    for (ks, v) in d {
        let tag = op_key_tag(ks);
        if (1..=63).contains(&tag) {
            buf.push(tag);
        } else {
            buf.push(OP_FREE_KEY);
            write_varint(buf, ks.len() as u64);
            buf.extend_from_slice(ks.as_bytes());
        }
        let mut intern = !is_payload_key(ks);
        if let Value::String(s) = v {
            if s.len() > INTERN_OP_MAX {
                intern = false;
            }
        }
        write_value(buf, tab, allow, v, intern, 1)?;
    }
    Ok(())
}

fn is_intent(doc: &Map<String, Value>) -> bool {
    doc.contains_key("action") && !doc.contains_key("ops")
}

fn is_result(doc: &Map<String, Value>) -> bool {
    doc.contains_key("ops") || (doc.contains_key("ok") && !doc.contains_key("action"))
}

fn maybe_cxbz(plain: Vec<u8>) -> Vec<u8> {
    if plain.len() < CXBZ_MIN_PLAIN {
        return plain;
    }
    let mut enc = ZlibEncoder::new(Vec::new(), Compression::new(CXBZ_LEVEL));
    if enc.write_all(&plain).is_err() {
        return plain;
    }
    let Ok(comp) = enc.finish() else {
        return plain;
    };
    let zlen = comp.len() + 4;
    let saved = plain.len() as isize - zlen as isize;
    if saved >= CXBZ_MIN_SAVE as isize && (plain.len() as f64 / zlen as f64) >= CXBZ_MIN_RATIO {
        let mut out = Vec::with_capacity(zlen);
        out.extend_from_slice(MAGIC_Z);
        out.extend_from_slice(&comp);
        return out;
    }
    plain
}

/// Encode a JSON document as CXB (Intent / Result / generic).
pub fn encode_cxb(doc: &Value) -> Result<Vec<u8>, CxbError> {
    let Value::Object(map) = doc else {
        return Err(CxbError::msg("CXB root must be object"));
    };
    let mut freq = HashMap::new();
    collect_freq(map, &mut freq);
    let allow = allow_from_freq(&freq);
    let mut tab = StrTable::new();
    let mut fields = Vec::new();
    let mut nfields: u16 = 0;
    let kind: u8;

    if is_intent(map) {
        kind = KIND_INTENT;
        for (k, tag, intern) in [
            ("v", I_V, true),
            ("action", I_ACTION, true),
            ("args", I_ARGS, false),
            ("cap", I_CAP, false),
            ("target", I_TARGET, true),
            ("request_id", I_REQUEST_ID, true),
            ("form", I_FORM, false),
            ("idempotency_key", I_IDEMPOTENCY, true),
            ("meta", I_META, false),
        ] {
            if let Some(v) = map.get(k) {
                write_field(&mut fields, &mut tab, &allow, tag, v, intern)?;
                nfields += 1;
            }
        }
        if let Some(v) = map.get("accept_stream") {
            if v.as_bool() == Some(true) {
                fields.extend_from_slice(&I_ACCEPT_STREAM.to_be_bytes());
                fields.push(W_TRUE);
                nfields += 1;
            }
        }
    } else if is_result(map) {
        kind = KIND_RESULT;
        if let Some(v) = map.get("v") {
            write_field(&mut fields, &mut tab, &allow, R_V, v, true)?;
            nfields += 1;
        }
        if let Some(v) = map.get("ok") {
            write_field(&mut fields, &mut tab, &allow, R_OK, v, false)?;
            nfields += 1;
        }
        if let Some(ops) = map.get("ops") {
            fields.extend_from_slice(&R_OPS.to_be_bytes());
            let Value::Array(list) = ops else {
                return Err(CxbError::msg("ops must be array"));
            };
            fields.push(W_ARRAY);
            write_varint(&mut fields, list.len() as u64);
            for op in list {
                write_op(&mut fields, &mut tab, &allow, op)?;
            }
            nfields += 1;
        }
        if let Some(v) = map.get("error") {
            if !v.is_null() {
                write_field(&mut fields, &mut tab, &allow, R_ERROR, v, false)?;
                nfields += 1;
            }
        }
        if let Some(v) = map.get("meta") {
            if !v.is_null() {
                write_field(&mut fields, &mut tab, &allow, R_META, v, false)?;
                nfields += 1;
            }
        }
    } else {
        kind = KIND_DOC;
        nfields = 0;
    }

    let mut out = Vec::new();
    out.extend_from_slice(MAGIC);
    out.push(kind);
    tab.write_to(&mut out);
    out.extend_from_slice(&nfields.to_be_bytes());
    out.extend_from_slice(&fields);

    let mut ext: Vec<(&String, &Value)> = Vec::new();
    for (ks, v) in map {
        let skip = match kind {
            KIND_INTENT => matches!(
                ks.as_str(),
                "v" | "action"
                    | "args"
                    | "cap"
                    | "target"
                    | "request_id"
                    | "form"
                    | "accept_stream"
                    | "idempotency_key"
                    | "meta"
            ),
            KIND_RESULT => matches!(ks.as_str(), "v" | "ok" | "ops" | "error" | "meta"),
            _ => false,
        };
        if !skip {
            ext.push((ks, v));
        }
    }
    write_varint(&mut out, ext.len() as u64);
    for (ks, v) in ext {
        write_varint(&mut out, ks.len() as u64);
        out.extend_from_slice(ks.as_bytes());
        write_value(&mut out, &mut tab, &allow, v, false, 0)?;
    }

    let crc = crc32_payload(&out[4..]);
    out.extend_from_slice(b"~CRC");
    out.extend_from_slice(&crc.to_be_bytes());
    Ok(maybe_cxbz(out))
}

struct Dec<'a> {
    data: &'a [u8],
    i: usize,
    table: Vec<String>,
    depth: usize,
}

impl<'a> Dec<'a> {
    fn need(&self, n: usize) -> Result<(), CxbError> {
        if self.i + n > self.data.len() {
            Err(CxbError::msg("CXB truncated"))
        } else {
            Ok(())
        }
    }
    fn u8(&mut self) -> Result<u8, CxbError> {
        self.need(1)?;
        let b = self.data[self.i];
        self.i += 1;
        Ok(b)
    }
    fn u16(&mut self) -> Result<u16, CxbError> {
        self.need(2)?;
        let v = u16::from_be_bytes([self.data[self.i], self.data[self.i + 1]]);
        self.i += 2;
        Ok(v)
    }
    fn varint(&mut self) -> Result<u64, CxbError> {
        read_varint_at(self.data, &mut self.i)
    }
}

fn read_value(d: &mut Dec<'_>) -> Result<Value, CxbError> {
    if d.depth > MAX_NEST {
        return Err(CxbError::msg("CXB nest too deep"));
    }
    d.depth += 1;
    let w = d.u8()?;
    let res = match w {
        W_NULL => Ok(Value::Null),
        W_FALSE => Ok(Value::Bool(false)),
        W_TRUE => Ok(Value::Bool(true)),
        W_VARINT => Ok(Value::Number(zigzag_decode(d.varint()?).into())),
        W_F64 => {
            d.need(8)?;
            let bytes: [u8; 8] = d.data[d.i..d.i + 8].try_into().unwrap();
            d.i += 8;
            let f = f64::from_be_bytes(bytes);
            Ok(Number::from_f64(f)
                .map(Value::Number)
                .unwrap_or(Value::Null))
        }
        W_UTF8 => {
            let ln = d.varint()? as usize;
            if ln > MAX_BLOB {
                return Err(CxbError::msg("CXB string too large"));
            }
            d.need(ln)?;
            let s = std::str::from_utf8(&d.data[d.i..d.i + ln])
                .map_err(|_| CxbError::msg("utf8"))?
                .to_string();
            d.i += ln;
            Ok(Value::String(s))
        }
        W_BYTES => {
            let ln = d.varint()? as usize;
            if ln > MAX_BLOB {
                return Err(CxbError::msg("CXB bytes too large"));
            }
            d.need(ln)?;
            // JSON-safe representation of binary (not a latent base64 type).
            let bytes = d.data[d.i..d.i + ln].to_vec();
            d.i += ln;
            Ok(Value::Array(
                bytes
                    .into_iter()
                    .map(|b| Value::Number(b.into()))
                    .collect(),
            ))
        }
        W_ARRAY => {
            let n = d.varint()? as usize;
            if n > MAX_ARRAY {
                return Err(CxbError::msg("CXB array too large"));
            }
            let mut arr = Vec::with_capacity(n);
            for _ in 0..n {
                arr.push(read_value(d)?);
            }
            Ok(Value::Array(arr))
        }
        W_MAP => {
            let n = d.varint()? as usize;
            if n > MAX_ARRAY {
                return Err(CxbError::msg("CXB map too large"));
            }
            let mut obj = Map::new();
            for _ in 0..n {
                let k = read_value(d)?;
                let v = read_value(d)?;
                let ks = match k {
                    Value::String(s) => s,
                    other => other.to_string(),
                };
                obj.insert(ks, v);
            }
            Ok(Value::Object(obj))
        }
        W_FREE => {
            let ln = d.varint()? as usize;
            if ln > MAX_BLOB {
                return Err(CxbError::msg("CXB freeform too large"));
            }
            d.need(ln)?;
            let blob = &d.data[d.i..d.i + ln];
            d.i += ln;
            free_loads(blob)
        }
        W_INTERN => {
            let idx = d.u16()? as usize;
            d.table
                .get(idx)
                .cloned()
                .map(Value::String)
                .ok_or_else(|| CxbError::msg("bad intern index"))
        }
        W_OPMAP => {
            let n = d.u8()? as usize;
            let mut obj = Map::new();
            for _ in 0..n {
                let tag = d.u8()?;
                let key = if tag == OP_FREE_KEY {
                    let ln = d.varint()? as usize;
                    d.need(ln)?;
                    let s = std::str::from_utf8(&d.data[d.i..d.i + ln])
                        .map_err(|_| CxbError::msg("op free key utf8"))?
                        .to_string();
                    d.i += ln;
                    s
                } else {
                    op_tag_key(tag)
                        .ok_or_else(|| CxbError::msg(format!("unknown op tag {tag}")))?
                        .to_string()
                };
                let v = read_value(d)?;
                obj.insert(key, v);
            }
            Ok(Value::Object(obj))
        }
        other => Err(CxbError::msg(format!("unknown wire type {other}"))),
    };
    d.depth -= 1;
    res
}

fn intent_tag_key(tag: u16) -> Option<&'static str> {
    match tag {
        I_V => Some("v"),
        I_ACTION => Some("action"),
        I_ARGS => Some("args"),
        I_CAP => Some("cap"),
        I_TARGET => Some("target"),
        I_REQUEST_ID => Some("request_id"),
        I_FORM => Some("form"),
        I_ACCEPT_STREAM => Some("accept_stream"),
        I_IDEMPOTENCY => Some("idempotency_key"),
        I_META => Some("meta"),
        _ => None,
    }
}

fn result_tag_key(tag: u16) -> Option<&'static str> {
    match tag {
        R_V => Some("v"),
        R_OK => Some("ok"),
        R_OPS => Some("ops"),
        R_ERROR => Some("error"),
        R_META => Some("meta"),
        _ => None,
    }
}

fn unwrap_frame(data: &[u8]) -> Result<Vec<u8>, CxbError> {
    if data.starts_with(MAGIC) {
        return Ok(data.to_vec());
    }
    if data.starts_with(MAGIC_Z) {
        let mut dec = ZlibDecoder::new(&data[4..]);
        let mut plain = Vec::new();
        dec.read_to_end(&mut plain)
            .map_err(|e| CxbError::msg(format!("CXBZ decompress: {e}")))?;
        if plain.starts_with(MAGIC) {
            return Ok(plain);
        }
        let mut full = Vec::with_capacity(4 + plain.len());
        full.extend_from_slice(MAGIC);
        full.extend_from_slice(&plain);
        return Ok(full);
    }
    Err(CxbError::msg("not CXB"))
}

/// Decode CXB1/CXBZ bytes to a JSON Value.
pub fn decode_cxb(data: &[u8]) -> Result<Value, CxbError> {
    let frame = unwrap_frame(data)?;
    if frame.len() < 12 {
        return Err(CxbError::msg("frame too short"));
    }
    if &frame[frame.len() - 8..frame.len() - 4] != b"~CRC" {
        return Err(CxbError::msg("missing ~CRC"));
    }
    let want = u32::from_be_bytes(frame[frame.len() - 4..].try_into().unwrap());
    let got = crc32_payload(&frame[4..frame.len() - 8]);
    if want != got {
        return Err(CxbError::msg(format!(
            "CRC mismatch want={want:08x} got={got:08x}"
        )));
    }
    let body = &frame[..frame.len() - 8];
    let mut d = Dec {
        data: body,
        i: 4,
        table: vec![],
        depth: 0,
    };
    let kind = d.u8()?;
    let ntable = d.varint()? as usize;
    d.table.clear();
    for _ in 0..ntable {
        let ln = d.varint()? as usize;
        d.need(ln)?;
        let s = std::str::from_utf8(&d.data[d.i..d.i + ln])
            .map_err(|_| CxbError::msg("table utf8"))?
            .to_string();
        d.i += ln;
        d.table.push(s);
    }
    let nfields = d.u16()? as usize;
    if nfields > MAX_FIELDS {
        return Err(CxbError::msg("too many fields"));
    }
    let mut obj = Map::new();
    for _ in 0..nfields {
        let tag = d.u16()?;
        let v = read_value(&mut d)?;
        let key = match kind {
            KIND_INTENT => intent_tag_key(tag),
            KIND_RESULT => result_tag_key(tag),
            _ => None,
        };
        if let Some(k) = key {
            obj.insert(k.to_string(), v);
        } else {
            obj.insert(format!("_tag_{tag}"), v);
        }
    }
    let next = d.varint()? as usize;
    for _ in 0..next {
        let ln = d.varint()? as usize;
        d.need(ln)?;
        let k = std::str::from_utf8(&d.data[d.i..d.i + ln])
            .map_err(|_| CxbError::msg("ext key utf8"))?
            .to_string();
        d.i += ln;
        let v = read_value(&mut d)?;
        obj.insert(k, v);
    }
    Ok(Value::Object(obj))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn roundtrip_minimal_intent() {
        let doc = json!({"v":"1","action":"Counter.inc","args":{}});
        let blob = encode_cxb(&doc).unwrap();
        assert!(is_cxb(&blob));
        let again = decode_cxb(&blob).unwrap();
        assert_eq!(again["action"], "Counter.inc");
        assert_eq!(again["v"], "1");
    }

    #[test]
    fn rejects_bad_crc() {
        let doc = json!({"v":"1","action":"X","args":{}});
        let mut blob = encode_cxb(&doc).unwrap();
        let last = blob.len() - 1;
        blob[last] ^= 0xff;
        assert!(decode_cxb(&blob).is_err());
    }
}
