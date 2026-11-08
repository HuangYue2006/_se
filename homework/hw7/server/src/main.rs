use std::{
    net::SocketAddr,
    sync::{Arc, Mutex},
};
use todo_server::{app, todo::Store};
use tower_http::services::ServeDir;

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(3000);
    let static_dir = std::env::var("STATIC_DIR").unwrap_or_else(|_| "../client".into());

    let state = Arc::new(Mutex::new(Store::new()));
    // /api/* 給 API，其他路徑給前端靜態檔
    let router = app(state).fallback_service(ServeDir::new(&static_dir));

    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    println!("作業清單伺服器：http://{addr}  (靜態檔目錄 {static_dir})");
    let listener = tokio::net::TcpListener::bind(addr).await.expect("無法綁定 port");
    axum::serve(listener, router).await.unwrap();
}
