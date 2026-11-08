import { renderTask, statsText, validateTitle } from "./logic.js";

let filter = "all";
const $ = (s) => document.querySelector(s);

async function api(method, url, data) {
  const r = await fetch(url, {
    method,
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  if (r.status === 204) return null;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

function showError(msg) {
  const el = $("#error");
  el.textContent = msg || "";
  el.hidden = !msg;
}

async function refresh() {
  const [tasks, stats] = await Promise.all([api("GET", `/api/tasks?filter=${filter}`), api("GET", "/api/stats")]);
  $("#list").innerHTML = tasks.map(renderTask).join("");
  $("#empty").hidden = tasks.length > 0;
  $("#stats").textContent = statsText(stats);
  $("#bar").style.width = stats.percent + "%";
  $("#clear").hidden = stats.done === 0;
}

$("#form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("#title").value;
  const err = validateTitle(title);
  if (err) return showError(err);
  try {
    await api("POST", "/api/tasks", { title, course: $("#course").value, priority: Number($("#priority").value) });
    $("#title").value = "";
    showError(null);
    await refresh();
  } catch (e2) {
    showError(e2.message);
  }
});

$("#list").addEventListener("click", async (e) => {
  const li = e.target.closest("li");
  if (!li) return;
  const id = li.dataset.id;
  if (e.target.classList.contains("toggle")) {
    await api("PATCH", `/api/tasks/${id}`, { done: e.target.checked });
  } else if (e.target.classList.contains("del")) {
    await api("DELETE", `/api/tasks/${id}`);
  } else return;
  await refresh();
});

$("#list").addEventListener("dblclick", async (e) => {
  const span = e.target.closest(".title");
  if (!span) return;
  const id = span.closest("li").dataset.id;
  const title = prompt("修改作業名稱", span.textContent);
  if (title === null) return;
  try {
    await api("PATCH", `/api/tasks/${id}`, { title });
    showError(null);
  } catch (e2) {
    showError(e2.message);
  }
  await refresh();
});

document.querySelectorAll("[data-filter]").forEach((b) =>
  b.addEventListener("click", () => {
    filter = b.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((x) => x.classList.toggle("on", x === b));
    refresh();
  }),
);

$("#clear").addEventListener("click", async () => {
  await api("DELETE", "/api/completed");
  await refresh();
});

refresh();
