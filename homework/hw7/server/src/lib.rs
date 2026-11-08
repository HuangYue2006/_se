//! HTTP 層：把 todo::Store 包成 REST API

pub mod todo;

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{delete, get, patch},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use todo::{Filter, NewTask, Stats, Store, Task, TaskPatch, TodoError};

pub type AppState = Arc<Mutex<Store>>;
type ApiError = (StatusCode, Json<Value>);
type ApiResult<T> = Result<T, ApiError>;

fn to_http(e: TodoError) -> ApiError {
    let code = match e {
        TodoError::NotFound => StatusCode::NOT_FOUND,
        _ => StatusCode::BAD_REQUEST,
    };
    (code, Json(json!({ "error": e.message() })))
}

#[derive(Deserialize, Default)]
struct ListQuery {
    #[serde(default)]
    filter: Filter,
}

async fn health() -> &'static str {
    "ok"
}

async fn list(State(s): State<AppState>, Query(q): Query<ListQuery>) -> Json<Vec<Task>> {
    Json(s.lock().unwrap().list(q.filter))
}

async fn create(State(s): State<AppState>, Json(n): Json<NewTask>) -> ApiResult<(StatusCode, Json<Task>)> {
    let t = s.lock().unwrap().add(n).map_err(to_http)?;
    Ok((StatusCode::CREATED, Json(t)))
}

async fn update(
    State(s): State<AppState>,
    Path(id): Path<u64>,
    Json(p): Json<TaskPatch>,
) -> ApiResult<Json<Task>> {
    let t = s.lock().unwrap().update(id, p).map_err(to_http)?;
    Ok(Json(t))
}

async fn remove(State(s): State<AppState>, Path(id): Path<u64>) -> ApiResult<StatusCode> {
    s.lock().unwrap().remove(id).map_err(to_http)?;
    Ok(StatusCode::NO_CONTENT)
}

async fn clear_completed(State(s): State<AppState>) -> Json<Value> {
    let n = s.lock().unwrap().clear_completed();
    Json(json!({ "removed": n }))
}

async fn stats(State(s): State<AppState>) -> Json<Stats> {
    Json(s.lock().unwrap().stats())
}

pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/api/health", get(health))
        .route("/api/tasks", get(list).post(create))
        .route("/api/tasks/:id", patch(update).delete(remove))
        .route("/api/completed", delete(clear_completed))
        .route("/api/stats", get(stats))
        .with_state(state)
}
