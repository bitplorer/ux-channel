//! Load conformance/vectors/arch project fixtures through Rust project().

use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use ux_channel_rs::effects::{graph, morph, seq, toast, Node};
use ux_channel_rs::project::project;

fn arch_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../conformance/vectors/arch")
}

fn node_from(v: &Value) -> Node {
    let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
    let data = v.get("data").cloned().unwrap_or_else(|| json!({}));
    let children = v
        .get("children")
        .and_then(|c| c.as_array())
        .map(|a| a.iter().map(node_from).collect())
        .unwrap_or_default();
    match kind {
        "toast" => toast(data.get("message").and_then(|m| m.as_str()).unwrap_or("")),
        "morph" => morph(
            data.get("target").and_then(|m| m.as_str()).unwrap_or(""),
            data.get("html").and_then(|m| m.as_str()).unwrap_or(""),
        ),
        "seq" => seq(children),
        _ => Node {
            kind: kind.into(),
            data: data
                .as_object()
                .map(|o| o.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
                .unwrap_or_default(),
            children,
        },
    }
}

#[test]
fn project_vectors() {
    let dir = arch_dir();
    let mut n = 0;
    for entry in fs::read_dir(&dir).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let doc: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        if doc["kind"] != "project" {
            continue;
        }
        n += 1;
        let nodes: Vec<Node> = doc["nodes"]
            .as_array()
            .unwrap()
            .iter()
            .map(node_from)
            .collect();
        let g = graph(nodes);
        let hello = doc.get("hello").cloned().unwrap_or_else(|| json!({}));
        let effects = doc["effects"].as_str().unwrap_or("auto");
        let ops = project(&g, &hello, effects).unwrap();
        let expect = doc["expect_ops"].as_array().cloned().unwrap();
        assert_eq!(ops, expect, "vector {}", doc["id"]);
    }
    assert!(n >= 3, "expected project vectors, got {n}");
}
