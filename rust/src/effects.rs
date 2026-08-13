//! EffectGraph builders — host-side until `project()`. No crypto, no I/O.
//! SPEC: `SPEC/architecture/host-kernel.md` · `effects.md`

use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq)]
pub struct Node {
    pub kind: String,
    pub data: BTreeMap<String, Value>,
    pub children: Vec<Node>,
}

pub type EffectGraph = Vec<Node>;

impl Node {
    fn new(kind: &str, data: BTreeMap<String, Value>, children: Vec<Node>) -> Self {
        Self {
            kind: kind.into(),
            data,
            children,
        }
    }
}

pub fn morph(target: impl Into<String>, html: impl Into<String>) -> Node {
    let mut d = BTreeMap::new();
    d.insert("target".into(), Value::String(target.into()));
    d.insert("html".into(), Value::String(html.into()));
    Node::new("morph", d, vec![])
}

pub fn toast(message: impl Into<String>) -> Node {
    toast_level(message, "info")
}

pub fn toast_level(message: impl Into<String>, level: impl Into<String>) -> Node {
    let mut d = BTreeMap::new();
    d.insert("message".into(), Value::String(message.into()));
    d.insert("level".into(), Value::String(level.into()));
    Node::new("toast", d, vec![])
}

pub fn navigate(href: impl Into<String>, replace: bool) -> Node {
    let mut d = BTreeMap::new();
    d.insert("href".into(), Value::String(href.into()));
    d.insert("replace".into(), Value::Bool(replace));
    Node::new("navigate", d, vec![])
}

pub fn seq(nodes: impl IntoIterator<Item = Node>) -> Node {
    Node::new("seq", BTreeMap::new(), nodes.into_iter().collect())
}

pub fn after(ms: i64, nodes: impl IntoIterator<Item = Node>, timer_id: &str) -> Node {
    let mut d = BTreeMap::new();
    d.insert("ms".into(), Value::from(ms));
    d.insert("id".into(), Value::String(timer_id.into()));
    Node::new("after", d, nodes.into_iter().collect())
}

pub fn dispatch_event(name: impl Into<String>, detail: Option<Value>) -> Node {
    let mut d = BTreeMap::new();
    d.insert("name".into(), Value::String(name.into()));
    if let Some(v) = detail {
        d.insert("detail".into(), v);
    }
    Node::new("dispatch", d, vec![])
}

pub fn invoke(r#ref: impl Into<String>, method: impl Into<String>, args: Value, body: Vec<Node>) -> Node {
    let mut d = BTreeMap::new();
    d.insert("ref".into(), Value::String(r#ref.into()));
    d.insert("method".into(), Value::String(method.into()));
    d.insert("args".into(), args);
    Node::new("invoke", d, body)
}

pub fn graph(nodes: impl IntoIterator<Item = Node>) -> EffectGraph {
    nodes.into_iter().collect()
}
