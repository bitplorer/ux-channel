//! web.v1 / agent.v1 drivers. No DOM — surfaces register their own packs.
//!
//! SPEC: `SPEC/architecture/profiles/web.v1.md` (safeHref) + ADR 0003 / 0004.

use crate::apply::{ApplyCtx, DriverFn};
use serde_json::{json, Value};
use std::collections::HashMap;

/// Block javascript:/data:/vbscript:/file: and protocol-relative URLs.
pub fn safe_href(href: Option<&str>) -> Option<String> {
    let h = href?.trim();
    if h.is_empty() || h.starts_with("//") {
        return None;
    }
    let path = h.split('?').next().unwrap_or(h);
    let path = path.split('#').next().unwrap_or(path);
    if let Some(idx) = path.find(':') {
        let scheme = path[..idx].to_ascii_lowercase();
        if matches!(
            scheme.as_str(),
            "javascript" | "data" | "vbscript" | "file"
        ) {
            return None;
        }
        if !matches!(scheme.as_str(), "http" | "https" | "mailto" | "tel")
            && scheme.chars().all(|c| c.is_ascii_alphabetic())
        {
            return None;
        }
    }
    Some(h.to_string())
}

/// Log/test web.v1 pack (toast, morph, navigate, dispatch, invoke).
/// `timer.set` / `timer.clear` / `seq` are kernel ops, not driver methods.
pub fn make_web_drivers() -> HashMap<String, DriverFn> {
    let mut m: HashMap<String, DriverFn> = HashMap::new();
    m.insert(
        "toast".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "toast",
                op.get("message").cloned().unwrap_or(Value::Null),
                op.get("level").cloned().unwrap_or_else(|| json!("info")),
            ]));
        }),
    );
    m.insert(
        "morph".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "morph",
                op.get("target").cloned().unwrap_or(Value::Null),
                op.get("html").cloned().unwrap_or(Value::Null),
            ]));
        }),
    );
    m.insert(
        "navigate".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            if ctx.result_ok == Some(false) {
                return;
            }
            let href = op.get("href").and_then(|v| v.as_str());
            let Some(h) = safe_href(href) else {
                return;
            };
            ctx.log.push(json!([
                "navigate",
                h,
                op.get("replace").and_then(|v| v.as_bool()).unwrap_or(false),
            ]));
        }),
    );
    m.insert(
        "push_url".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            let href = op.get("href").and_then(|v| v.as_str());
            let Some(h) = safe_href(href) else {
                return;
            };
            ctx.log.push(json!([
                "push_url",
                h,
                op.get("replace").and_then(|v| v.as_bool()).unwrap_or(false),
            ]));
        }),
    );
    m.insert(
        "reload".into(),
        Box::new(|_op, ctx: &mut ApplyCtx| {
            if ctx.result_ok == Some(false) {
                return;
            }
            ctx.log.push(json!(["reload"]));
        }),
    );
    m.insert(
        "focus".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "focus",
                op.get("target").cloned().unwrap_or(Value::Null),
                op.get("select").and_then(|v| v.as_bool()).unwrap_or(false),
            ]));
        }),
    );
    m.insert(
        "set_text".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "set_text",
                op.get("target").cloned().unwrap_or(Value::Null),
                op.get("text").cloned().unwrap_or(Value::Null),
            ]));
        }),
    );
    m.insert(
        "dispatch".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "dispatch",
                op.get("name").cloned().unwrap_or(Value::Null),
                op.get("detail").cloned().unwrap_or(Value::Null),
            ]));
        }),
    );
    m.insert(
        "invoke".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "invoke",
                op.get("ref").cloned().unwrap_or(Value::Null),
                op.get("method").cloned().unwrap_or(Value::Null),
                op.get("args").cloned().unwrap_or(Value::Null),
            ]));
        }),
    );
    m
}

/// agent.v1 pack: `log` + `tool` (named callbacks).
pub fn make_agent_drivers(
    tools: HashMap<String, Box<dyn Fn(&Value) -> Value + Send + Sync>>,
) -> HashMap<String, DriverFn> {
    let tools = std::sync::Arc::new(tools);
    let mut m: HashMap<String, DriverFn> = HashMap::new();
    let tools_log = tools.clone();
    m.insert(
        "tool".into(),
        Box::new(move |op, ctx: &mut ApplyCtx| {
            let name = op.get("name").and_then(|v| v.as_str()).unwrap_or("");
            match tools_log.get(name) {
                None => ctx.log.push(json!(["tool_missing", name])),
                Some(fn_) => {
                    let args = op.get("args").cloned().unwrap_or_else(|| json!({}));
                    let out = fn_(&args);
                    ctx.log.push(json!(["tool", name, out]));
                }
            }
        }),
    );
    m.insert(
        "log".into(),
        Box::new(|op, ctx: &mut ApplyCtx| {
            ctx.log.push(json!([
                "log",
                op.get("message").cloned().unwrap_or(Value::Null),
                op.get("level").cloned().unwrap_or(Value::Null),
            ]));
        }),
    );
    m
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_href_blocks_javascript() {
        assert!(safe_href(Some("javascript:alert(1)")).is_none());
        assert!(safe_href(Some("//evil.example")).is_none());
        assert!(safe_href(Some("https://ok.example/x")).is_some());
        assert!(safe_href(Some("/relative")).is_some());
    }

    #[test]
    fn navigate_skipped_when_result_not_ok() {
        let mut ctx = ApplyCtx {
            gen: 1,
            session_id: "s".into(),
            log: vec![],
            timers: Default::default(),
            result_ok: Some(false),
            reject: None,
        };
        let drivers = make_web_drivers();
        drivers["navigate"](&json!({"op": "navigate", "href": "/x"}), &mut ctx);
        assert!(ctx.log.is_empty());
    }
}
