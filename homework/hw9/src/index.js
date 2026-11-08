// DeadlineMate Cloud —— Cloudflare Worker + D1
//
// 靜態檔（public/）由 Workers Static Assets 直接回應；找不到的路徑（/api/*、/cal/*）才會進到這裡。
import { findConflicts, fmt, fmtDate, parseNaive, parseQuick, taipeiNow, toIcs } from "../public/lib.js";

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8" } });

const KEY_RE = /^[A-Za-z0-9_-]{20,64}$/;

function newKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(18));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function body(req) {
  try {
    return await req.json();
  } catch {
    throw new HttpError(400, "JSON 格式錯誤");
  }
}

async function requireUser(env, key) {
  if (!key || !KEY_RE.test(key)) throw new HttpError(401, "缺少或無效的使用者金鑰");
  const user = await env.DB.prepare("SELECT * FROM users WHERE key = ?").bind(key).first();
  if (!user) throw new HttpError(401, "找不到這個使用者，請重新建立");
  return user;
}

// ---------------------------------------------------------------- 驗證
function validateCourse(b) {
  const c = {
    name: String(b.name ?? "").trim(),
    code: String(b.code ?? "").trim(),
    room: String(b.room ?? "").trim(),
    day: Number(b.day),
    start_period: Number(b.start_period),
    end_period: Number(b.end_period),
    color: /^#[0-9a-fA-F]{6}$/.test(b.color) ? b.color : "#4f7cff",
  };
  if (!c.name) throw new HttpError(400, "課名必填");
  if (c.name.length > 50) throw new HttpError(400, "課名太長");
  if (!(Number.isInteger(c.day) && c.day >= 1 && c.day <= 7)) throw new HttpError(400, "星期需 1~7");
  if (!(Number.isInteger(c.start_period) && Number.isInteger(c.end_period) &&
        c.start_period >= 1 && c.start_period <= c.end_period && c.end_period <= 10))
    throw new HttpError(400, "節次需 1~10 且開始 ≤ 結束");
  return c;
}

function validateHw(b, partial = false) {
  const h = {};
  if (!partial || "title" in b) {
    h.title = String(b.title ?? "").trim();
    if (!h.title) throw new HttpError(400, "作業名稱必填");
    if (h.title.length > 200) throw new HttpError(400, "作業名稱太長");
  }
  if (!partial || "due" in b) {
    const d = parseNaive(b.due);
    if (!d) throw new HttpError(400, "截止時間格式錯誤，例如 2026-11-15T23:59");
    h.due = /T\d{2}:\d{2}/.test(b.due) ? fmt(d) : `${fmtDate(d)}T23:59`; // 沒給時間就當天 23:59
  }
  if ("course_id" in b) h.course_id = b.course_id ? Number(b.course_id) : null;
  if ("note" in b) h.note = String(b.note ?? "").slice(0, 500);
  if ("priority" in b) h.priority = Math.max(1, Math.min(3, Number(b.priority) || 2));
  if ("done" in b) h.done = b.done ? 1 : 0;
  return h;
}

async function checkCourseOwner(env, key, courseId) {
  if (courseId == null) return;
  const c = await env.DB.prepare("SELECT id FROM courses WHERE id = ? AND user_key = ?").bind(courseId, key).first();
  if (!c) throw new HttpError(400, "課程不存在");
}

// ---------------------------------------------------------------- 資料
const listCourses = async (env, key) =>
  (await env.DB.prepare("SELECT * FROM courses WHERE user_key = ? ORDER BY day, start_period").bind(key).all()).results;

const listHws = async (env, key) =>
  (await env.DB.prepare(
    `SELECT a.*, c.name AS course_name, c.color FROM assignments a
     LEFT JOIN courses c ON c.id = a.course_id WHERE a.user_key = ? ORDER BY a.done, a.due`,
  ).bind(key).all()).results.map((a) => ({ ...a, done: !!a.done }));

async function seedDemo(env, key) {
  const now = taipeiNow();
  const plus = (h) => new Date(now.getTime() + h * 3600e3).toISOString().slice(0, 16);
  const courses = [
    ["軟體工程", "CS201", "E321", 2, 2, 4, "#4f7cff"],
    ["計算機結構", "CS202", "E320", 3, 5, 7, "#f08c00"],
    ["資料結構", "CS203", "E318", 1, 2, 4, "#2b8a3e"],
    ["網頁程式設計", "CS204", "電腦教室B", 4, 6, 8, "#ae3ec9"],
  ];
  const stmts = courses.map((c) =>
    env.DB.prepare("INSERT INTO courses (user_key,name,code,room,day,start_period,end_period,color) VALUES (?,?,?,?,?,?,?,?)")
      .bind(key, ...c));
  const res = await env.DB.batch(stmts);
  const ids = res.map((r) => r.meta.last_row_id);
  const hws = [
    [ids[0], "第 9 週：Cloudflare 網站", plus(20), 3],
    [ids[1], "Verilog 期中實作", plus(51), 3],
    [ids[2], "Lab5 二元搜尋樹", plus(120), 2],
    [ids[3], "期末專題提案", plus(290), 1],
  ];
  await env.DB.batch(hws.map((h) =>
    env.DB.prepare("INSERT INTO assignments (user_key,course_id,title,due,priority) VALUES (?,?,?,?,?)").bind(key, ...h)));
}

// ---------------------------------------------------------------- 路由
async function route(req, env, url) {
  const p = url.pathname.split("/").filter(Boolean); // ["api","courses","3"]
  const m = req.method;

  // iCalendar 訂閱：/cal/<key>.ics（行事曆 App 不能帶自訂 header，所以金鑰放網址）
  if (p[0] === "cal" && p.length === 2 && m === "GET") {
    const key = p[1].replace(/\.ics$/, "");
    const user = await requireUser(env, key);
    const sem = parseNaive(user.semester_start) ?? taipeiNow();
    const ics = toIcs(await listCourses(env, key), await listHws(env, key), sem, taipeiNow());
    return new Response(ics, { headers: { "content-type": "text/calendar; charset=utf-8", "cache-control": "no-store" } });
  }

  if (p[0] !== "api") throw new HttpError(404, "找不到");

  if (p[1] === "health") return json({ ok: true, now_taipei: taipeiNow().toISOString().slice(0, 16) });

  if (p[1] === "users" && m === "POST") {
    const b = await body(req).catch(() => ({}));
    const key = newKey();
    const now = taipeiNow();
    const semStart = `${now.getUTCMonth() >= 7 ? now.getUTCFullYear() : now.getUTCFullYear() - 1}-09-08`;
    await env.DB.prepare("INSERT INTO users (key, semester_start) VALUES (?, ?)").bind(key, semStart).run();
    if (b.demo) await seedDemo(env, key);
    return json({ key }, 201);
  }

  const key = req.headers.get("x-user-key");
  const user = await requireUser(env, key);
  const id = p[2] ? Number(p[2]) : null;

  if (p[1] === "me") {
    if (m === "GET") return json({ semester_start: user.semester_start, created_at: user.created_at });
    if (m === "PUT") {
      const b = await body(req);
      if (!parseNaive(b.semester_start)) throw new HttpError(400, "日期格式錯誤");
      await env.DB.prepare("UPDATE users SET semester_start = ? WHERE key = ?").bind(b.semester_start.slice(0, 10), key).run();
      return json({ ok: true });
    }
    if (m === "DELETE") {
      await env.DB.batch([
        env.DB.prepare("DELETE FROM assignments WHERE user_key = ?").bind(key),
        env.DB.prepare("DELETE FROM courses WHERE user_key = ?").bind(key),
        env.DB.prepare("DELETE FROM users WHERE key = ?").bind(key),
      ]);
      return json({ ok: true });
    }
  }

  if (p[1] === "courses") {
    if (m === "GET") return json(await listCourses(env, key));
    if (m === "POST" || (m === "PUT" && id)) {
      const c = validateCourse(await body(req));
      const conflicts = findConflicts(await listCourses(env, key), { ...c, id });
      if (conflicts.length && !url.searchParams.get("force")) throw new HttpError(409, `與「${conflicts[0].name}」衝堂`);
      const vals = [c.name, c.code, c.room, c.day, c.start_period, c.end_period, c.color];
      if (m === "POST") {
        const r = await env.DB.prepare(
          "INSERT INTO courses (user_key,name,code,room,day,start_period,end_period,color) VALUES (?,?,?,?,?,?,?,?)",
        ).bind(key, ...vals).run();
        return json({ id: r.meta.last_row_id }, 201);
      }
      const r = await env.DB.prepare(
        "UPDATE courses SET name=?,code=?,room=?,day=?,start_period=?,end_period=?,color=? WHERE id=? AND user_key=?",
      ).bind(...vals, id, key).run();
      if (!r.meta.changes) throw new HttpError(404, "找不到課程");
      return json({ ok: true });
    }
    if (m === "DELETE" && id) {
      const r = await env.DB.prepare("DELETE FROM courses WHERE id=? AND user_key=?").bind(id, key).run();
      if (!r.meta.changes) throw new HttpError(404, "找不到課程");
      await env.DB.prepare("UPDATE assignments SET course_id=NULL WHERE course_id=? AND user_key=?").bind(id, key).run();
      return json({ ok: true });
    }
  }

  if (p[1] === "assignments") {
    if (m === "GET") return json(await listHws(env, key));
    if (m === "POST") {
      const h = validateHw(await body(req));
      await checkCourseOwner(env, key, h.course_id ?? null);
      const r = await env.DB.prepare(
        "INSERT INTO assignments (user_key,course_id,title,due,note,priority) VALUES (?,?,?,?,?,?)",
      ).bind(key, h.course_id ?? null, h.title, h.due, h.note ?? "", h.priority ?? 2).run();
      return json({ id: r.meta.last_row_id }, 201);
    }
    if (m === "PUT" && id) {
      const h = validateHw(await body(req), true);
      const cols = Object.keys(h);
      if (!cols.length) throw new HttpError(400, "沒有要更新的欄位");
      if ("course_id" in h) await checkCourseOwner(env, key, h.course_id);
      const r = await env.DB.prepare(`UPDATE assignments SET ${cols.map((c) => c + "=?").join(",")} WHERE id=? AND user_key=?`)
        .bind(...cols.map((c) => h[c]), id, key).run();
      if (!r.meta.changes) throw new HttpError(404, "找不到作業");
      return json({ ok: true });
    }
    if (m === "DELETE" && id) {
      const r = await env.DB.prepare("DELETE FROM assignments WHERE id=? AND user_key=?").bind(id, key).run();
      if (!r.meta.changes) throw new HttpError(404, "找不到作業");
      return json({ ok: true });
    }
  }

  if (p[1] === "quick" && m === "POST") {
    let h;
    try {
      h = parseQuick((await body(req)).text, await listCourses(env, key), taipeiNow());
    } catch (e) {
      throw e instanceof HttpError ? e : new HttpError(400, e.message);
    }
    const r = await env.DB.prepare("INSERT INTO assignments (user_key,course_id,title,due) VALUES (?,?,?,?)")
      .bind(key, h.course_id, h.title, h.due).run();
    return json({ id: r.meta.last_row_id, ...h }, 201);
  }

  throw new HttpError(404, "API 不存在");
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      return await route(req, env, url);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      console.error(e);
      return json({ error: "伺服器錯誤" }, 500);
    }
  },
};
