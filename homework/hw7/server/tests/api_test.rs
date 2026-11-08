//! 系統測試（Web API 測試）：不開真的 port，直接把 HTTP Request 丟進 Router

use axum::{
    body::Body,
    http::{Request, StatusCode},
    Router,
};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use todo_server::{app, todo::Store};
use tower::ServiceExt;

fn new_app() -> Router {
    app(Arc::new(Mutex::new(Store::new())))
}

async fn send(app: &Router, method: &str, uri: &str, body: Option<Value>) -> (StatusCode, Value) {
    let mut req = Request::builder().method(method).uri(uri);
    let body = match body {
        Some(v) => {
            req = req.header("content-type", "application/json");
            Body::from(v.to_string())
        }
        None => Body::empty(),
    };
    let resp = app.clone().oneshot(req.body(body).unwrap()).await.unwrap();
    let status = resp.status();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let v = if bytes.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&bytes).unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into()))
    };
    (status, v)
}

#[tokio::test]
async fn health_ok() {
    let app = new_app();
    let (s, v) = send(&app, "GET", "/api/health", None).await;
    assert_eq!(s, StatusCode::OK);
    assert_eq!(v, "ok");
}

#[tokio::test]
async fn create_then_list() {
    let app = new_app();
    let (s, t) = send(&app, "POST", "/api/tasks", Some(json!({"title": "HW7 測試", "course": "軟體工程"}))).await;
    assert_eq!(s, StatusCode::CREATED);
    assert_eq!(t["id"], 1);
    assert_eq!(t["priority"], 2); // 預設值
    assert_eq!(t["done"], false);

    let (s, list) = send(&app, "GET", "/api/tasks", None).await;
    assert_eq!(s, StatusCode::OK);
    assert_eq!(list.as_array().unwrap().len(), 1);
    assert_eq!(list[0]["title"], "HW7 測試");
}

#[tokio::test]
async fn validation_errors() {
    let app = new_app();
    let (s, v) = send(&app, "POST", "/api/tasks", Some(json!({"title": "   "}))).await;
    assert_eq!(s, StatusCode::BAD_REQUEST);
    assert_eq!(v["error"], "作業名稱不能是空的");

    let (s, _) = send(&app, "POST", "/api/tasks", Some(json!({"title": "x", "priority": 5}))).await;
    assert_eq!(s, StatusCode::BAD_REQUEST);

    // 缺少必要欄位 → axum 的 Json extractor 回 422
    let (s, _) = send(&app, "POST", "/api/tasks", Some(json!({"course": "x"}))).await;
    assert_eq!(s, StatusCode::UNPROCESSABLE_ENTITY);
}

#[tokio::test]
async fn patch_and_filter() {
    let app = new_app();
    for t in ["a", "b", "c"] {
        send(&app, "POST", "/api/tasks", Some(json!({ "title": t }))).await;
    }
    let (s, t) = send(&app, "PATCH", "/api/tasks/2", Some(json!({"done": true}))).await;
    assert_eq!(s, StatusCode::OK);
    assert_eq!(t["done"], true);

    let (_, active) = send(&app, "GET", "/api/tasks?filter=active", None).await;
    let (_, done) = send(&app, "GET", "/api/tasks?filter=completed", None).await;
    assert_eq!(active.as_array().unwrap().len(), 2);
    assert_eq!(done[0]["title"], "b");

    let (s, _) = send(&app, "GET", "/api/tasks?filter=nope", None).await;
    assert_eq!(s, StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn delete_and_not_found() {
    let app = new_app();
    send(&app, "POST", "/api/tasks", Some(json!({"title": "x"}))).await;
    let (s, _) = send(&app, "DELETE", "/api/tasks/1", None).await;
    assert_eq!(s, StatusCode::NO_CONTENT);
    let (s, v) = send(&app, "DELETE", "/api/tasks/1", None).await;
    assert_eq!(s, StatusCode::NOT_FOUND);
    assert_eq!(v["error"], "找不到這個作業");
    let (s, _) = send(&app, "PATCH", "/api/tasks/99", Some(json!({"done": true}))).await;
    assert_eq!(s, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn stats_and_clear_completed() {
    let app = new_app();
    for t in ["a", "b", "c", "d"] {
        send(&app, "POST", "/api/tasks", Some(json!({ "title": t }))).await;
    }
    send(&app, "PATCH", "/api/tasks/1", Some(json!({"done": true}))).await;
    let (_, st) = send(&app, "GET", "/api/stats", None).await;
    assert_eq!(st, json!({"total": 4, "done": 1, "active": 3, "percent": 25}));

    let (_, r) = send(&app, "DELETE", "/api/completed", None).await;
    assert_eq!(r["removed"], 1);
    let (_, st) = send(&app, "GET", "/api/stats", None).await;
    assert_eq!(st["total"], 3);
}
