//! Pure `project(graph, hello, effects) -> ops[]`. Classic floor is permanent.
//! SPEC: `SPEC/architecture/project.md`

use crate::effects::{EffectGraph, Node};
use serde_json::{json, Value};

pub fn project(graph: &EffectGraph, peer_hello: &Value, effects: &str) -> Result<Vec<Value>, String> {
    if effects != "auto" && effects != "classic" {
        return Err("effects must be \"auto\" or \"classic\"".into());
    }
    let profiles = string_set(peer_hello.get("profiles"));
    let features = string_set(peer_hello.get("features"));
    let allow_rich = effects == "auto"
        && (features.iter().any(|f| f == "seq" || f == "invoke")
            || profiles.iter().any(|p| p == "web.v1" || p == "agent.v1"));
    let classic_only = effects == "classic" || !allow_rich;
    let drop_chrome = profiles.iter().any(|p| p == "agent.v1")
        && !profiles.iter().any(|p| p == "web.v1");
    let mut out = Vec::new();
    for node in graph {
        out.extend(lower(node, classic_only, drop_chrome));
    }
    Ok(out)
}

fn string_set(v: Option<&Value>) -> Vec<String> {
    match v {
        Some(Value::Array(a)) => a
            .iter()
            .filter_map(|x| x.as_str().map(|s| s.to_string()))
            .collect(),
        _ => Vec::new(),
    }
}

fn lower(node: &Node, classic_only: bool, drop_chrome: bool) -> Vec<Value> {
    match node.kind.as_str() {
        "seq" => {
            if classic_only {
                node.children
                    .iter()
                    .flat_map(|ch| lower(ch, true, drop_chrome))
                    .collect()
            } else {
                let kids: Vec<Value> = node
                    .children
                    .iter()
                    .flat_map(|ch| lower(ch, false, drop_chrome))
                    .collect();
                vec![json!({"op": "seq", "ops": kids})]
            }
        }
        "after" => {
            let ms = node
                .data
                .get("ms")
                .and_then(|v| v.as_i64())
                .unwrap_or(0);
            let tid = node
                .data
                .get("id")
                .and_then(|v| v.as_str())
                .unwrap_or("t");
            let body: Vec<Value> = node
                .children
                .iter()
                .flat_map(|ch| lower(ch, classic_only, drop_chrome))
                .collect();
            if classic_only {
                if ms <= 0 {
                    body
                } else {
                    vec![]
                }
            } else {
                vec![json!({"op": "timer.set", "id": tid, "ms": ms, "ops": body})]
            }
        }
        "invoke" => {
            if classic_only {
                return node
                    .children
                    .iter()
                    .flat_map(|ch| lower(ch, true, drop_chrome))
                    .collect();
            }
            let mut op = json!({
                "op": "invoke",
                "ref": node.data.get("ref").cloned().unwrap_or(Value::Null),
                "method": node.data.get("method").cloned().unwrap_or(Value::Null),
                "args": node.data.get("args").cloned().unwrap_or_else(|| json!({})),
            });
            if !node.children.is_empty() {
                let kids: Vec<Value> = node
                    .children
                    .iter()
                    .flat_map(|ch| lower(ch, false, drop_chrome))
                    .collect();
                op["ops"] = json!(kids);
            }
            vec![op]
        }
        "morph" | "navigate" if drop_chrome => vec![],
        "morph" => vec![json!({
            "op": "morph",
            "target": node.data.get("target").cloned().unwrap_or(Value::Null),
            "html": node.data.get("html").cloned().unwrap_or(Value::Null),
        })],
        "toast" => {
            let mut op = json!({
                "op": "toast",
                "message": node.data.get("message").cloned().unwrap_or(Value::Null),
                "level": node.data.get("level").cloned().unwrap_or_else(|| json!("info")),
            });
            if let Some(d) = node.data.get("duration_ms") {
                op["duration_ms"] = d.clone();
            }
            vec![op]
        }
        "navigate" => vec![json!({
            "op": "navigate",
            "href": node.data.get("href").cloned().unwrap_or(Value::Null),
            "replace": node.data.get("replace").and_then(|v| v.as_bool()).unwrap_or(false),
        })],
        "dispatch" => {
            let mut op = json!({
                "op": "dispatch",
                "name": node.data.get("name").cloned().unwrap_or(Value::Null),
            });
            if let Some(t) = node.data.get("target") {
                op["target"] = t.clone();
            }
            if let Some(d) = node.data.get("detail") {
                op["detail"] = d.clone();
            }
            vec![op]
        }
        _ => vec![],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::effects::{graph, seq, toast};

    #[test]
    fn classic_floor_without_hello() {
        let g = graph([seq([toast("a"), toast("b")])]);
        let ops = project(&g, &json!({}), "auto").unwrap();
        assert_eq!(ops[0]["op"], "toast");
        assert_eq!(ops[1]["op"], "toast");
        assert_eq!(ops.len(), 2);
    }

    #[test]
    fn auto_web_keeps_seq() {
        let g = graph([seq([toast("a"), toast("b")])]);
        let hello = json!({"profiles": ["web.v1"], "features": ["seq"]});
        let ops = project(&g, &hello, "auto").unwrap();
        assert_eq!(ops[0]["op"], "seq");
        assert_eq!(ops[0]["ops"].as_array().unwrap().len(), 2);
    }

    #[test]
    fn classic_mode_flattens_even_with_hello() {
        let g = graph([seq([toast("a"), toast("b")])]);
        let hello = json!({"profiles": ["web.v1"], "features": ["seq"]});
        let ops = project(&g, &hello, "classic").unwrap();
        assert_eq!(ops.len(), 2);
        assert_eq!(ops[0]["op"], "toast");
    }

    #[test]
    fn agent_only_drops_morph() {
        use crate::effects::morph;
        let g = graph([seq([toast("ok"), morph("#x", "<b>no</b>")])]);
        let hello = json!({"profiles": ["agent.v1"], "features": ["seq"]});
        let ops = project(&g, &hello, "auto").unwrap();
        assert_eq!(ops[0]["op"], "seq");
        let kids = ops[0]["ops"].as_array().unwrap();
        assert_eq!(kids.len(), 1);
        assert_eq!(kids[0]["op"], "toast");
    }
}

#[cfg(test)]
mod prop_tests {
    use super::*;
    use crate::effects::{graph, seq, toast};
    use proptest::prelude::*;

    fn kinds(ops: &[Value]) -> Vec<String> {
        let mut out = Vec::new();
        fn walk(list: &[Value], out: &mut Vec<String>) {
            for op in list {
                if let Some(k) = op.get("op").and_then(|v| v.as_str()) {
                    out.push(k.to_string());
                }
                if let Some(Value::Array(kids)) = op.get("ops") {
                    walk(kids, out);
                }
            }
        }
        walk(ops, &mut out);
        out
    }

    proptest! {
        #[test]
        fn classic_never_emits_seq(msg in ".{1,16}") {
            let g = graph([seq([toast(&msg)])]);
            let hello = json!({"profiles": ["web.v1"], "features": ["seq"]});
            let ops = project(&g, &hello, "classic").unwrap();
            prop_assert!(!kinds(&ops).iter().any(|k| k == "seq"));
            prop_assert!(kinds(&ops).iter().any(|k| k == "toast"));
        }

        #[test]
        fn empty_hello_is_floor(msg in ".{1,16}") {
            let g = graph([seq([toast(&msg)])]);
            let ops = project(&g, &json!({}), "auto").unwrap();
            prop_assert!(!kinds(&ops).iter().any(|k| k == "seq"));
        }
    }
}
