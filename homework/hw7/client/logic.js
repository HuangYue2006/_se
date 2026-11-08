// 前端的純函式（瀏覽器與 Node 都能用，方便測試）

export const PRIORITY_LABEL = { 1: "低", 2: "中", 3: "高" };

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export function validateTitle(title) {
  const t = String(title ?? "").trim();
  if (!t) return "請輸入作業名稱";
  if ([...t].length > 100) return "作業名稱不能超過 100 個字";
  return null;
}

export function statsText({ total, done, percent }) {
  if (total === 0) return "目前沒有作業 🎉";
  return `完成 ${done} / ${total}（${percent}%）`;
}

export function renderTask(t) {
  return `<li class="task ${t.done ? "done" : ""} p${t.priority}" data-id="${t.id}" data-testid="task">
    <input type="checkbox" class="toggle" ${t.done ? "checked" : ""} aria-label="完成 ${escapeHtml(t.title)}">
    <span class="title">${escapeHtml(t.title)}</span>
    ${t.course ? `<span class="course">${escapeHtml(t.course)}</span>` : ""}
    <span class="pri">${PRIORITY_LABEL[t.priority] ?? ""}</span>
    <button class="del" aria-label="刪除 ${escapeHtml(t.title)}">✕</button>
  </li>`;
}
