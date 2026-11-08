# 第 4 週：Git Flow / GitHub Flow 的用法

題目：寫一個 README.md 解說下了什麼指令（或在 GitHub 上做了什麼動作），才能創造

1. 分支 (branch)
2. 合併 (merge)
3. fork
4. pull request

並說明這是哪一種 Git 流程。

參考老師的示範：

* 母專案 <https://github.com/se-test-examples/git-examples>（分支 `developGitBranch`）
* 子專案（fork）<https://github.com/ccckmit/git-examples>

---

## 0. 先搞懂三種常見流程

流程 | 長期分支 | 適合 | 重點
-----|---------|------|-----
**Git Flow** | `main`、`develop`，加上短期的 `feature/*`、`release/*`、`hotfix/*` | 有固定版本號、定期發佈的產品（App、套件） | 功能先合到 `develop`，要發版時開 `release`，最後才合回 `main` 並打 tag
**GitHub Flow** | 只有 `main` | 持續部署的網站、小團隊 | `main` 永遠可部署；任何修改都開分支 → 開 PR → review → 合併 → 部署
**Forking Flow** | 每個人有自己的 fork | 開源專案、沒有寫入權限的人 | 先 fork 到自己帳號，改完從 fork 發 PR 回原專案

```
Git Flow:
main     ●─────────────────────●─────────── (v1.0)        (v1.1)
          \                   / \                         /
develop    ●──●──────●──────●───●────●───────────────────●
               \    /                 \                 /
feature/a       ●──●                   ●──●──●  (feature/b)

GitHub Flow:
main     ●──────●────────────●───────
          \    /  (PR #1)     \     /  (PR #2)
branch     ●──●                ●──●
```

---

## 1. 創造分支 (branch)

在**母專案**（我有寫入權限）裡開一個新分支：

```bash
git clone git@github.com:se-test-examples/git-examples.git
cd git-examples
git remote -v                       # 確認 origin 指向哪裡
git checkout -b developGitBranch    # 建立並切換到新分支（等同 git branch X + git checkout X）
git branch                          # 列出分支，* 表示目前所在分支
```

在分支上做修改並推上 GitHub：

```bash
echo "# 在分支上新增的檔案" > gitBranch.md
git add gitBranch.md
git commit -m "add gitBranch.md"
git push origin developGitBranch    # 第一次推送，GitHub 上就會出現這個分支
```

> 新版 Git 也可以用 `git switch -c developGitBranch` 建立分支。

GitHub 網頁上的做法：在 repo 首頁點左上角的分支下拉選單 → 輸入新分支名稱 → **Create branch**。

## 2. 合併 (merge)

把分支合回 `main`：

```bash
git checkout main                   # 切回主分支
git pull origin main                # 先把遠端最新的 main 拉下來，避免衝突
git merge developGitBranch          # 把分支的提交合進 main
git push origin main                # 推上 GitHub
```

* 如果 `main` 在分支開出來之後沒有新提交，Git 會做 **fast-forward**（直接把 main 指標往前移，不產生 merge commit）。
* 想保留「這裡曾經是一個分支」的紀錄，可以用 `git merge --no-ff developGitBranch`，這是 Git Flow 的習慣。
* 合併完可以刪掉分支：`git branch -d developGitBranch`、`git push origin --delete developGitBranch`。

### 如果發生衝突

```bash
git merge developGitBranch
# CONFLICT (content): Merge conflict in README.md
git status                          # 看哪些檔案衝突
# 打開檔案，處理 <<<<<<< ======= >>>>>>> 標記
git add README.md
git commit                          # 完成合併
```

## 3. Fork

Fork 是 **GitHub 上的動作**，不是 git 指令：

1. 打開母專案 <https://github.com/se-test-examples/git-examples>
2. 點右上角 **Fork** → 選擇自己的帳號 → **Create fork**
3. 自己帳號下就多了一份 `https://github.com/<我的帳號>/git-examples`

接著在自己的 fork 上工作（我對 fork 有完整寫入權限）：

```bash
git clone git@github.com:<我的帳號>/git-examples.git
cd git-examples
git remote add upstream git@github.com:se-test-examples/git-examples.git   # 記住原專案
git remote -v
# origin    git@github.com:<我的帳號>/git-examples.git     ← 我的 fork
# upstream  git@github.com:se-test-examples/git-examples.git ← 原專案

git checkout -b add-my-file         # 好習慣：在 fork 裡也開分支，不直接改 main
echo "# 我在 fork 新增的檔案" > myFork.md
git add myFork.md
git commit -m "add myFork.md"
git push origin add-my-file
```

讓 fork 跟上原專案的更新：

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

（GitHub 網頁上也可以按 fork 頁面的 **Sync fork** 按鈕。）

## 4. Pull Request

PR 也是 **GitHub 上的動作**，意思是「請把我分支上的修改拉 (pull) 進你的專案」。

1. push 完之後，到自己的 fork 頁面，GitHub 會顯示黃色提示 **Compare & pull request**，點它
   （或到原專案 → **Pull requests** → **New pull request** → **compare across forks**）
2. 設定方向：
   * base repository：`se-test-examples/git-examples`，base：`main`
   * head repository：`<我的帳號>/git-examples`，compare：`add-my-file`
3. 寫標題與說明（改了什麼、為什麼），按 **Create pull request**
4. 原專案的維護者 review：可以留言、要求修改；我在同一個分支再 commit + push，PR 會自動更新
5. 維護者按 **Merge pull request**（可選 Create a merge commit / Squash and merge / Rebase and merge）
6. 合併後可以刪掉分支

用 GitHub CLI 也可以：

```bash
gh pr create --repo se-test-examples/git-examples --base main --head <我的帳號>:add-my-file \
  --title "add myFork.md" --body "新增 fork 練習檔案"
gh pr list --repo se-test-examples/git-examples
gh pr merge <PR 編號> --merge          # 維護者合併
```

同一個 repo 內也能發 PR（不用 fork）：把分支 push 上去後，從 `developGitBranch` → `main` 開 PR，這就是 GitHub Flow 的標準做法。

---

## 5. 老師的示範屬於哪種流程？

示範 | 做法 | 流程
-----|------|-----
母專案 | `git checkout -b developGitBranch` → commit → push 分支 → 切回 main → `git merge` → push main | 開功能分支再合回 main，屬於 **GitHub Flow**（只有 main 一條長期分支）。分支名稱像 develop，但沒有長期維護 `develop` + `release`，所以不是完整的 Git Flow
子專案 | 在 GitHub 上 fork → clone 自己的 fork → commit → push 到自己的 main | **Forking Flow** 的前半段；若要把修改送回母專案，最後一步就是發 **Pull Request**

## 6. 指令速查

目的 | 指令
-----|-----
建立並切換分支 | `git checkout -b <分支>` / `git switch -c <分支>`
列出分支 | `git branch`（本地）、`git branch -a`（含遠端）
切換分支 | `git checkout <分支>` / `git switch <分支>`
推送分支 | `git push -u origin <分支>`
合併 | `git checkout main && git merge <分支>`
刪除分支 | `git branch -d <分支>`、`git push origin --delete <分支>`
看歷史圖 | `git log --oneline --graph --all`
新增上游 | `git remote add upstream <原專案網址>`
同步上游 | `git fetch upstream && git merge upstream/main`

## 參考

1. [阮一峰：Git 工作流程](https://www.ruanyifeng.com/blog/2015/12/git-workflow.html)
2. [ByteByteGo：How does Git work?](https://bytebytego.com/guides/how-does-git-work/)
3. [課程教材 03-tool/02-git](https://github.com/ccc115a/se/tree/main/03-tool/02-git)
