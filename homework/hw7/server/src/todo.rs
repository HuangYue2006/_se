//! 作業待辦清單的核心邏輯（不碰 HTTP，方便單元測試）

use serde::{Deserialize, Serialize};

pub const MAX_TITLE: usize = 100;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Task {
    pub id: u64,
    pub title: String,
    pub course: String,
    pub priority: u8, // 1 低 / 2 中 / 3 高
    pub done: bool,
}

#[derive(Debug, Deserialize)]
pub struct NewTask {
    pub title: String,
    #[serde(default)]
    pub course: String,
    #[serde(default = "default_priority")]
    pub priority: u8,
}

fn default_priority() -> u8 {
    2
}

#[derive(Debug, Deserialize, Default)]
pub struct TaskPatch {
    pub title: Option<String>,
    pub done: Option<bool>,
    pub priority: Option<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum Filter {
    #[default]
    All,
    Active,
    Completed,
}

#[derive(Debug, PartialEq)]
pub enum TodoError {
    EmptyTitle,
    TitleTooLong,
    BadPriority,
    NotFound,
}

impl TodoError {
    pub fn message(&self) -> &'static str {
        match self {
            TodoError::EmptyTitle => "作業名稱不能是空的",
            TodoError::TitleTooLong => "作業名稱不能超過 100 個字",
            TodoError::BadPriority => "優先度必須是 1~3",
            TodoError::NotFound => "找不到這個作業",
        }
    }
}

#[derive(Debug, Serialize, PartialEq)]
pub struct Stats {
    pub total: usize,
    pub done: usize,
    pub active: usize,
    pub percent: u8,
}

pub struct Store {
    tasks: Vec<Task>,
    next_id: u64,
}

impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

pub fn validate_title(title: &str) -> Result<String, TodoError> {
    let t = title.trim();
    if t.is_empty() {
        Err(TodoError::EmptyTitle)
    } else if t.chars().count() > MAX_TITLE {
        Err(TodoError::TitleTooLong)
    } else {
        Ok(t.to_string())
    }
}

pub fn validate_priority(p: u8) -> Result<u8, TodoError> {
    if (1..=3).contains(&p) {
        Ok(p)
    } else {
        Err(TodoError::BadPriority)
    }
}

impl Store {
    pub fn new() -> Self {
        Store { tasks: Vec::new(), next_id: 1 }
    }

    pub fn add(&mut self, n: NewTask) -> Result<Task, TodoError> {
        let task = Task {
            id: self.next_id,
            title: validate_title(&n.title)?,
            course: n.course.trim().to_string(),
            priority: validate_priority(n.priority)?,
            done: false,
        };
        self.next_id += 1;
        self.tasks.push(task.clone());
        Ok(task)
    }

    /// 未完成在前；同狀態依優先度高到低；再依建立順序
    pub fn list(&self, filter: Filter) -> Vec<Task> {
        let mut v: Vec<Task> = self
            .tasks
            .iter()
            .filter(|t| match filter {
                Filter::All => true,
                Filter::Active => !t.done,
                Filter::Completed => t.done,
            })
            .cloned()
            .collect();
        v.sort_by(|a, b| {
            a.done
                .cmp(&b.done)
                .then(b.priority.cmp(&a.priority))
                .then(a.id.cmp(&b.id))
        });
        v
    }

    pub fn update(&mut self, id: u64, p: TaskPatch) -> Result<Task, TodoError> {
        // 先驗證，全部合法才修改（避免改到一半失敗）
        let title = p.title.as_deref().map(validate_title).transpose()?;
        let priority = p.priority.map(validate_priority).transpose()?;
        let t = self.tasks.iter_mut().find(|t| t.id == id).ok_or(TodoError::NotFound)?;
        if let Some(title) = title {
            t.title = title;
        }
        if let Some(pr) = priority {
            t.priority = pr;
        }
        if let Some(done) = p.done {
            t.done = done;
        }
        Ok(t.clone())
    }

    pub fn remove(&mut self, id: u64) -> Result<(), TodoError> {
        let before = self.tasks.len();
        self.tasks.retain(|t| t.id != id);
        if self.tasks.len() == before {
            Err(TodoError::NotFound)
        } else {
            Ok(())
        }
    }

    pub fn clear_completed(&mut self) -> usize {
        let before = self.tasks.len();
        self.tasks.retain(|t| !t.done);
        before - self.tasks.len()
    }

    pub fn stats(&self) -> Stats {
        let total = self.tasks.len();
        let done = self.tasks.iter().filter(|t| t.done).count();
        let percent = if total == 0 { 0 } else { (done * 100 / total) as u8 };
        Stats { total, done, active: total - done, percent }
    }
}

// ============================================================== 單元測試
#[cfg(test)]
mod tests {
    use super::*;

    fn nt(title: &str, priority: u8) -> NewTask {
        NewTask { title: title.into(), course: "軟體工程".into(), priority }
    }

    #[test]
    fn add_assigns_increasing_ids_and_trims() {
        let mut s = Store::new();
        let a = s.add(nt("  HW1  ", 2)).unwrap();
        let b = s.add(nt("HW2", 2)).unwrap();
        assert_eq!(a.id, 1);
        assert_eq!(b.id, 2);
        assert_eq!(a.title, "HW1");
        assert!(!a.done);
    }

    #[test]
    fn title_validation() {
        assert_eq!(validate_title("   "), Err(TodoError::EmptyTitle));
        assert_eq!(validate_title(&"字".repeat(101)), Err(TodoError::TitleTooLong));
        assert_eq!(validate_title(&"字".repeat(100)).unwrap().chars().count(), 100);
    }

    #[test]
    fn priority_validation() {
        let mut s = Store::new();
        assert_eq!(s.add(nt("x", 0)), Err(TodoError::BadPriority));
        assert_eq!(s.add(nt("x", 4)), Err(TodoError::BadPriority));
        assert!(s.add(nt("x", 3)).is_ok());
    }

    #[test]
    fn failed_add_does_not_consume_id() {
        let mut s = Store::new();
        let _ = s.add(nt("", 2));
        assert_eq!(s.add(nt("ok", 2)).unwrap().id, 1);
    }

    #[test]
    fn list_sorts_and_filters() {
        let mut s = Store::new();
        s.add(nt("low", 1)).unwrap();
        s.add(nt("high", 3)).unwrap();
        s.add(nt("mid", 2)).unwrap();
        s.update(2, TaskPatch { done: Some(true), ..Default::default() }).unwrap();
        let titles: Vec<_> = s.list(Filter::All).into_iter().map(|t| t.title).collect();
        assert_eq!(titles, ["mid", "low", "high"]);
        assert_eq!(s.list(Filter::Active).len(), 2);
        assert_eq!(s.list(Filter::Completed)[0].title, "high");
    }

    #[test]
    fn update_is_atomic() {
        let mut s = Store::new();
        s.add(nt("orig", 2)).unwrap();
        let bad = TaskPatch { title: Some("new".into()), priority: Some(9), done: None };
        assert_eq!(s.update(1, bad), Err(TodoError::BadPriority));
        assert_eq!(s.list(Filter::All)[0].title, "orig");
    }

    #[test]
    fn update_and_remove_missing() {
        let mut s = Store::new();
        assert_eq!(s.update(42, TaskPatch::default()), Err(TodoError::NotFound));
        assert_eq!(s.remove(42), Err(TodoError::NotFound));
    }

    #[test]
    fn remove_and_clear_completed() {
        let mut s = Store::new();
        for i in 0..4 {
            s.add(nt(&format!("t{i}"), 2)).unwrap();
        }
        s.remove(1).unwrap();
        s.update(2, TaskPatch { done: Some(true), ..Default::default() }).unwrap();
        s.update(3, TaskPatch { done: Some(true), ..Default::default() }).unwrap();
        assert_eq!(s.clear_completed(), 2);
        assert_eq!(s.list(Filter::All).len(), 1);
    }

    #[test]
    fn stats_percent() {
        let mut s = Store::new();
        assert_eq!(s.stats(), Stats { total: 0, done: 0, active: 0, percent: 0 });
        for i in 0..3 {
            s.add(nt(&format!("t{i}"), 2)).unwrap();
        }
        s.update(1, TaskPatch { done: Some(true), ..Default::default() }).unwrap();
        assert_eq!(s.stats(), Stats { total: 3, done: 1, active: 2, percent: 33 });
    }
}
