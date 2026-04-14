(function () {
  const app = document.getElementById("app");
  let guildNameById = {};
  let lastChannelsRaw = null;

  function showToast(message, kind, detail) {
    const host = document.getElementById("toastHost");
    if (!host) return;
    const el = document.createElement("div");
    el.className = "toast toast-" + (kind || "info");
    if (detail) {
      el.innerHTML =
        '<div class="toast-msg">' +
        escapeHtml(message) +
        '</div><pre class="toast-detail">' +
        escapeHtml(detail) +
        "</pre>";
    } else {
      el.textContent = message;
    }
    host.appendChild(el);
    const remove = () => el.remove();
    const t = setTimeout(remove, 4200);
    el.onclick = () => {
      clearTimeout(t);
      el.remove();
    };
  }

  function resultSummary(r) {
    const d = r.data;
    if (d != null && typeof d === "object") return JSON.stringify(d, null, 2);
    if (r.raw_json && typeof r.raw_json === "object") return JSON.stringify(r.raw_json, null, 2);
    return "";
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = String(s);
    return d.innerHTML;
  }

  function setHash(path) {
    location.hash = path.startsWith("#") ? path : "#/" + path.replace(/^\/+/, "");
  }

  function getRoute() {
    const raw = (location.hash || "#/guilds").replace(/^#/, "");
    const qi = raw.indexOf("?");
    const pathPart = qi >= 0 ? raw.slice(0, qi) : raw;
    const q = new URLSearchParams(qi >= 0 ? raw.slice(qi + 1) : "");
    const parts = pathPart.split("/").filter(Boolean);
    return { parts, q };
  }

  function findChannels(obj) {
    const out = [];
    const seen = new Set();
    function walk(x) {
      if (!x || typeof x !== "object") return;
      if (Array.isArray(x)) {
        x.forEach(walk);
        return;
      }
      const cid =
        x.uint64ChannelId ??
        x.channelId ??
        x.uint64_channel_id ??
        x.channel_id;
      const name =
        x.bytesChannelName ??
        x.bytes_channel_name ??
        x.channelName ??
        x.name;
      if (cid != null && cid !== "" && name) {
        const id = String(cid);
        if (!seen.has(id)) {
          seen.add(id);
          out.push({ channel_id: id, name: String(name) });
        }
      }
      Object.values(x).forEach(walk);
    }
    walk(obj);
    return out.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  }

  async function fetchJSON(url, opt) {
    const r = await fetch(url, opt);
    const j = await r.json();
    if (j.ok === false)
      throw new Error(
        j.error ||
          (Array.isArray(j.errors) ? j.errors.join("; ") : "") ||
          j.stderr ||
          r.statusText ||
          "请求失败"
      );
    if (!j.ok) throw new Error(j.error || r.statusText || "请求失败");
    return j;
  }

  async function fetchJSONForm(url, formData) {
    const r = await fetch(url, { method: "POST", body: formData });
    const j = await r.json();
    if (j.ok === false)
      throw new Error(
        j.error ||
          (Array.isArray(j.errors) ? j.errors.join("; ") : "") ||
          j.stderr ||
          r.statusText ||
          "请求失败"
      );
    if (!j.ok) throw new Error(j.error || r.statusText || "请求失败");
    return j;
  }

  function joinGuildUsesAnswersArray(hint) {
    if (hint.quiz && hint.quiz.length) return true;
    const jt = String(hint.join_type || "");
    return /MULTI_QUESTION|_QUIZ|JOIN_GUILD_TYPE_6|JOIN_GUILD_TYPE_7|\bTYPE_6\b|\bTYPE_7\b/.test(jt);
  }

  function renderJoinVerificationForm(box, guildId, hint) {
    const host = box.querySelector("#joinVerifyHost");
    if (!host) return;
    host.innerHTML = "";
    host.style.display = "block";
    const step0 = box.querySelector("#joinStepInitial");
    if (step0) step0.style.display = "none";

    const intro = document.createElement("p");
    intro.className = "hint";
    intro.textContent = hint.message || "该频道需要验证后才能加入。";
    host.appendChild(intro);

    const jt = hint.join_type || "";
    const minAns = hint.min_answer_num != null ? String(hint.min_answer_num) : "";
    const minOk = hint.min_correct_answer_num != null ? String(hint.min_correct_answer_num) : "";
    if (minAns || minOk) {
      const p = document.createElement("p");
      p.className = "hint";
      p.style.marginTop = "0.35rem";
      p.textContent = [minAns && `至少作答 ${minAns} 题`, minOk && `至少答对 ${minOk} 题`].filter(Boolean).join("；");
      host.appendChild(p);
    }

    const quiz = hint.quiz || [];
    const questions = hint.questions || [];

    if (quiz.length) {
      quiz.forEach((item, i) => {
        const qtext = item.question || "";
        const opts = item.answers || [];
        const fieldset = document.createElement("fieldset");
        fieldset.className = "join-quiz-q";
        fieldset.style.marginTop = "0.75rem";
        fieldset.style.border = "1px solid var(--border)";
        fieldset.style.borderRadius = "8px";
        fieldset.style.padding = "0.5rem 0.75rem";
        const leg = document.createElement("legend");
        leg.style.fontSize = "0.9rem";
        leg.textContent = `第 ${i + 1} 题`;
        fieldset.appendChild(leg);
        const qel = document.createElement("div");
        qel.style.marginBottom = "0.5rem";
        qel.textContent = qtext;
        fieldset.appendChild(qel);
        if (!opts.length) {
          const ta = document.createElement("textarea");
          ta.rows = 2;
          ta.style.width = "100%";
          ta.dataset.quizQuestion = qtext;
          ta.dataset.quizMode = "open";
          ta.placeholder = "请输入答案";
          ta.id = `joinQuizOpen_${i}`;
          fieldset.appendChild(ta);
        } else {
          opts.forEach((opt, j) => {
            const row = document.createElement("div");
            row.style.margin = "0.25rem 0";
            const lab = document.createElement("label");
            lab.style.cursor = "pointer";
            lab.style.display = "block";
            const inp = document.createElement("input");
            inp.type = "radio";
            inp.name = `join_quiz_${i}`;
            inp.value = String(j);
            inp.dataset.question = qtext;
            lab.appendChild(inp);
            lab.appendChild(document.createTextNode(" " + opt));
            row.appendChild(lab);
            fieldset.appendChild(row);
          });
        }
        host.appendChild(fieldset);
      });
    } else if (joinGuildUsesAnswersArray(hint) && questions.length && !quiz.length) {
      questions.forEach((item, i) => {
        const qtext = item.question || "";
        const lab = document.createElement("label");
        lab.style.display = "block";
        lab.style.marginTop = "0.65rem";
        lab.textContent = qtext || `问题 ${i + 1}`;
        const ta = document.createElement("textarea");
        ta.rows = 2;
        ta.style.width = "100%";
        ta.dataset.mqQuestion = qtext;
        ta.id = `joinMq_${i}`;
        host.appendChild(lab);
        host.appendChild(ta);
      });
    } else {
      questions.forEach((item) => {
        const qtext = item.question || "";
        if (!qtext) return;
        const pq = document.createElement("p");
        pq.style.marginTop = "0.5rem";
        pq.style.fontSize = "0.92rem";
        pq.textContent = qtext;
        host.appendChild(pq);
      });
      const lab = document.createElement("label");
      lab.style.display = "block";
      lab.style.marginTop = "0.5rem";
      lab.textContent = questions.length ? "填写回答或附言（提交为 join_guild_comment）" : "附言 / 申请说明";
      const ta = document.createElement("textarea");
      ta.id = "joinVerifyComment";
      ta.rows = 4;
      ta.style.width = "100%";
      ta.placeholder = "join_guild_comment";
      host.appendChild(lab);
      host.appendChild(ta);
    }

    const btnRow = document.createElement("div");
    btnRow.className = "btn-row";
    btnRow.style.marginTop = "0.85rem";
    const btnBack = document.createElement("button");
    btnBack.type = "button";
    btnBack.className = "btn-ghost";
    btnBack.textContent = "返回";
    btnBack.onclick = () => {
      host.style.display = "none";
      host.innerHTML = "";
      if (step0) step0.style.display = "block";
    };
    const btnSend = document.createElement("button");
    btnSend.type = "button";
    btnSend.className = "btn-primary";
    btnSend.textContent = "提交验证并加入";
    btnSend.onclick = async () => {
      const body = { guild_id: guildId };
      try {
        if (quiz.length) {
          const answers = [];
          for (let i = 0; i < quiz.length; i++) {
            const item = quiz[i];
            const qtext = item.question || "";
            const opts = item.answers || [];
            if (!opts.length) {
              const ta = host.querySelector(`#joinQuizOpen_${i}`);
              const ans = (ta && ta.value.trim()) || "";
              if (!ans) {
                showToast(`请填写第 ${i + 1} 题`, "error");
                return;
              }
              answers.push({ question: qtext, answer: ans });
            } else {
              const sel = host.querySelector(`input[name="join_quiz_${i}"]:checked`);
              if (!sel) {
                showToast(`请选择第 ${i + 1} 题的选项`, "error");
                return;
              }
              const idx = parseInt(sel.value, 10);
              const ans = opts[idx];
              answers.push({ question: qtext, answer: ans });
            }
          }
          body.join_guild_answers = answers;
        } else if (joinGuildUsesAnswersArray(hint) && questions.length) {
          const answers = [];
          for (let i = 0; i < questions.length; i++) {
            const ta = host.querySelector(`#joinMq_${i}`);
            const qtext = questions[i].question || "";
            const ans = (ta && ta.value.trim()) || "";
            if (!ans) {
              showToast(`请填写问题 ${i + 1}`, "error");
              return;
            }
            answers.push({ question: qtext, answer: ans });
          }
          body.join_guild_answers = answers;
        } else {
          const ta = host.querySelector("#joinVerifyComment");
          const c = (ta && ta.value.trim()) || "";
          if (!c) {
            showToast("请填写附言或回答", "error");
            return;
          }
          body.join_guild_comment = c;
        }

        const r = await fetchJSON("/api/panel/join-guild", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const d = r.data || {};
        if (d.action === "need_verification") {
          showToast("仍需补充验证，请按提示操作", "info");
          renderJoinVerificationForm(box, guildId, d);
          return;
        }
        const detail = resultSummary(r);
        showToast("加入请求已处理", "success", detail || undefined);
        const shell = box.closest(".modal-bg");
        if (shell) shell.remove();
      } catch (e) {
        showToast(e.message || "加入失败", "error");
      }
    };
    btnRow.appendChild(btnSend);
    btnRow.appendChild(btnBack);
    host.appendChild(btnRow);
  }

  function openJoinModal(guildId) {
    const bg = document.createElement("div");
    bg.className = "modal-bg";
    const box = document.createElement("div");
    box.className = "modal";
    box.style.maxWidth = "560px";
    box.innerHTML = `<h3>加入频道</h3>
      <div id="joinStepInitial">
        <p class="hint">频道 ID：<code>${escapeHtml(guildId)}</code>。先提交尝试加入；若需验证，将引导你选择题或填写附言（与 <code>join_guild.py</code> 一致）。</p>
        <label>附言（可选，管理员审核 / 问答类频道）</label>
        <textarea id="jComment" rows="2" style="width:100%;" placeholder="join_guild_comment"></textarea>
        <details style="margin-top:0.5rem;font-size:0.88rem;">
          <summary>高级：手动填写 join_guild_answers（JSON）</summary>
          <textarea id="jAnswers" rows="3" style="width:100%;margin-top:0.35rem;" placeholder='[{"question":"题干","answer":"答案"}]'></textarea>
        </details>
        <div class="btn-row" style="margin-top:0.75rem;">
          <button type="button" class="btn-primary" id="jGo">加入频道</button>
          <button type="button" class="btn-ghost" id="jClose">取消</button>
        </div>
      </div>
      <div id="joinVerifyHost" style="display:none;"></div>`;
    bg.appendChild(box);
    document.body.appendChild(bg);
    box.querySelector("#jClose").onclick = () => bg.remove();
    bg.onclick = (ev) => {
      if (ev.target === bg) bg.remove();
    };
    box.querySelector("#jGo").onclick = async () => {
      const body = { guild_id: guildId };
      const c = box.querySelector("#jComment").value.trim();
      const a = (box.querySelector("#jAnswers") && box.querySelector("#jAnswers").value.trim()) || "";
      if (c) body.join_guild_comment = c;
      if (a) {
        try {
          body.join_guild_answers = JSON.parse(a);
        } catch (_) {
          showToast("高级答案 JSON 格式错误", "error");
          return;
        }
      }
      try {
        const r = await fetchJSON("/api/panel/join-guild", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const d = r.data || {};
        if (d.action === "need_verification") {
          renderJoinVerificationForm(box, guildId, d);
          return;
        }
        const detail = resultSummary(r);
        showToast("加入请求已处理", "success", detail || undefined);
        bg.remove();
      } catch (e) {
        showToast(e.message || "加入失败", "error");
      }
    };
  }

  function breadcrumb(items) {
    const el = document.createElement("div");
    el.className = "breadcrumb";
    el.innerHTML = items
      .map((it, i) => {
        if (it.href) {
          return i === 0 ? `<a href="${it.href}">${escapeHtml(it.label)}</a>` : ` › <a href="${it.href}">${escapeHtml(it.label)}</a>`;
        }
        return i === 0 ? escapeHtml(it.label) : ` › ${escapeHtml(it.label)}`;
      })
      .join("");
    return el;
  }

  async function renderGuilds() {
    app.innerHTML = "<p>加载频道列表…</p>";
    try {
      const data = await fetchJSON("/api/panel/my-guilds");
      guildNameById = {};
      (data.guilds || []).forEach((g) => {
        guildNameById[g.guild_id] = g.name;
      });
      const grid = document.createElement("div");
      grid.className = "card-grid";
      (data.guilds || []).forEach((g) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `<h3>${escapeHtml(g.name)}</h3><div class="meta">${escapeHtml(g.bucket_label)} · ${escapeHtml(g.role || "")}</div><div class="meta">ID ${escapeHtml(g.guild_id)}</div>`;
        card.onclick = () => setHash(`/g/${g.guild_id}`);
        grid.appendChild(card);
      });
      app.innerHTML = "";
      app.appendChild(breadcrumb([{ label: "我的频道", href: "#/guilds" }]));

      const tools = document.createElement("div");
      tools.className = "panel-tools-block";
      tools.innerHTML = `
        <h2 class="panel-tools-title">搜索与加入</h2>
        <div class="panel-tools-row">
          <label>关键词</label><input type="text" id="globKw" placeholder="搜频道 / 帖子 / 作者" style="flex:1;min-width:140px;" />
          <select id="globScope" class="compact">
            <option value="channel">频道</option>
            <option value="feed">帖子</option>
            <option value="author">作者</option>
            <option value="all">全部</option>
          </select>
          <button type="button" class="btn-primary" id="btnGlobSearch">搜索</button>
        </div>
        <div class="panel-tools-row" style="margin-top:0.5rem;">
          <label>分享链接</label><input type="text" id="shareUrl" placeholder="https://pd.qq.com/s/..." style="flex:1;" />
          <button type="button" class="btn-ghost" id="btnShareParse">解析</button>
        </div>
        <p class="hint" style="margin-top:0.5rem;">解析链接后可获取频道 ID 并加入。「退出频道」暂无独立脚本，请到客户端操作。</p>
        <div id="globSearchOut" class="glob-search-out"></div>`;
      app.appendChild(tools);
      tools.querySelector("#btnGlobSearch").onclick = async () => {
        const keyword = (tools.querySelector("#globKw").value || "").trim();
        const scope = tools.querySelector("#globScope").value;
        const out = tools.querySelector("#globSearchOut");
        if (!keyword) {
          showToast("请输入关键词", "error");
          return;
        }
        out.innerHTML = "<p>搜索中…</p>";
        try {
          const res = await fetchJSON("/api/panel/search-content", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ keyword, scope, disable_correction_query: false }),
          });
          const raw = res.data || res.raw_json || {};
          const chans = raw.channels || [];
          let html = "<h3>结果</h3>";
          if (chans.length) {
            html += '<ul class="channel-list">';
            chans.forEach((c) => {
              const gid = String(c.guild_id || "");
              const nm = c.name || gid;
              html += `<li><span>${escapeHtml(nm)} <small style="color:var(--muted)">${escapeHtml(gid)}</small></span>
                <button type="button" class="btn-ghost js-enter" data-gid="${escapeHtml(gid)}">进入</button>
                <button type="button" class="btn-primary js-join" data-gid="${escapeHtml(gid)}">加入</button></li>`;
            });
            html += "</ul>";
          } else {
            html += `<pre class="toast-detail" style="max-height:240px;">${escapeHtml(JSON.stringify(raw, null, 2))}</pre>`;
          }
          out.innerHTML = html;
          out.querySelectorAll(".js-enter").forEach((btn) => {
            btn.onclick = (e) => {
              const id = e.target.getAttribute("data-gid");
              guildNameById[id] = guildNameById[id] || id;
              setHash(`/g/${id}`);
            };
          });
          out.querySelectorAll(".js-join").forEach((btn) => {
            btn.onclick = (e) => openJoinModal(e.target.getAttribute("data-gid"));
          });
          showToast("搜索完成", "success");
        } catch (e) {
          out.innerHTML = "";
          showToast(e.message || "搜索失败", "error");
        }
      };
      tools.querySelector("#btnShareParse").onclick = async () => {
        const url = (tools.querySelector("#shareUrl").value || "").trim();
        const out = tools.querySelector("#globSearchOut");
        if (!url) {
          showToast("请粘贴分享链接", "error");
          return;
        }
        out.innerHTML = "<p>解析中…</p>";
        try {
          const res = await fetchJSON("/api/panel/share-info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
          });
          const d = res.data || res.raw_json || {};
          let gid = "";
          try {
            const sig = d.shareGuildInfo || d.share_guild_info || {};
            gid = String(sig.guildId || sig.guild_id || "");
          } catch (_) {
            gid = "";
          }
          out.innerHTML = `<p>解析结果（频道 ID）：<strong>${escapeHtml(gid || "(见 JSON)")}</strong></p>
            <button type="button" class="btn-primary" id="btnJoinParsed" ${gid ? "" : "disabled"}>加入该频道</button>
            <pre class="toast-detail" style="max-height:200px;">${escapeHtml(JSON.stringify(d, null, 2))}</pre>`;
          const jb = out.querySelector("#btnJoinParsed");
          if (jb && gid) jb.onclick = () => openJoinModal(gid);
          showToast("解析完成", "success");
        } catch (e) {
          out.innerHTML = "";
          showToast(e.message || "解析失败", "error");
        }
      };

      if (!data.guilds || !data.guilds.length) {
        app.appendChild(document.createTextNode("暂无加入的频道。可用上方搜索或解析链接后加入。"));
      }
      app.appendChild(grid);
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p>`;
    }
  }

  async function renderHub(gid) {
    app.innerHTML = "<p>加载…</p>";
    try {
      const chRes = await fetchJSON(`/api/panel/guild/${encodeURIComponent(gid)}/channels`);
      lastChannelsRaw = chRes.data;
      const channels = findChannels(chRes.data || {});
      const name = guildNameById[gid] || "频道 " + gid;

      app.innerHTML = "";
      app.appendChild(
        breadcrumb([
          { label: "我的频道", href: "#/guilds" },
          { label: name, href: null },
        ])
      );

      const actions = document.createElement("div");
      actions.className = "btn-row";
      const b1 = document.createElement("button");
      b1.className = "btn-primary";
      b1.textContent = "频道主页帖子（热门/最新）";
      b1.onclick = () => setHash(`/g/${gid}/home`);
      const b2 = document.createElement("button");
      b2.className = "btn-ghost";
      b2.textContent = "发帖（含图片/视频）";
      b2.onclick = () => openPublishModal(gid, channels);
      const b3 = document.createElement("button");
      b3.className = "btn-ghost";
      b3.textContent = "频道内搜帖";
      b3.onclick = () => setHash(`/g/${gid}/feed-search`);
      const b4 = document.createElement("button");
      b4.className = "btn-ghost";
      b4.textContent = "成员管理";
      b4.onclick = () => setHash(`/g/${gid}/members`);
      const b5 = document.createElement("button");
      b5.className = "btn-ghost";
      b5.textContent = "加入频道";
      b5.onclick = () => openJoinModal(gid);
      actions.appendChild(b1);
      actions.appendChild(b2);
      actions.appendChild(b3);
      actions.appendChild(b4);
      actions.appendChild(b5);
      app.appendChild(actions);

      const h = document.createElement("h2");
      h.style.fontSize = "0.95rem";
      h.style.margin = "0.75rem 0 0.5rem";
      h.textContent = "版块（点击进入该版帖子流）";
      app.appendChild(h);

      const ul = document.createElement("ul");
      ul.className = "channel-list";
      channels.forEach((c) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.innerHTML = `${escapeHtml(c.name)}<span style="color:var(--muted);font-size:0.78rem;"> · ${escapeHtml(c.channel_id)}</span>`;
        btn.onclick = () => setHash(`/g/${gid}/c/${c.channel_id}`);
        li.appendChild(btn);
        ul.appendChild(li);
      });
      app.appendChild(ul);
      if (!channels.length) {
        app.appendChild(document.createTextNode("未能解析版块列表，请用脚本控制台查看原始返回；仍可使用「频道主页帖子」。"));
      }
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p><p><a href="#/guilds">返回</a></p>`;
    }
  }

  let homeCursor = { attach: "", get_type: 2 };
  let homeFeedsList = [];
  let chCursor = { key: "", attach: "" };
  let chFeedsList = [];

  async function renderHomeFeeds(gid, loadMore) {
    const name = guildNameById[gid] || gid;
    if (!loadMore) {
      app.innerHTML = "<p>加载帖子…</p>";
      homeFeedsList = [];
      homeCursor.attach = "";
    }
    const params = new URLSearchParams({
      get_type: String(homeCursor.get_type),
      count: "20",
    });
    if (homeCursor.attach) params.set("feed_attach_info", homeCursor.attach);

    try {
      const res = await fetchJSON(`/api/panel/guild/${encodeURIComponent(gid)}/home-feeds?${params}`);
      const d = res.data || {};
      const feeds = d.feeds || [];
      const finish = d.is_finish;
      homeCursor.attach = d.feed_attach_info || "";
      homeFeedsList = homeFeedsList.concat(feeds);

      app.innerHTML = "";
      app.appendChild(
        breadcrumb([
          { label: "我的频道", href: "#/guilds" },
          { label: name, href: `#/g/${gid}` },
          { label: "频道主页帖子", href: null },
        ])
      );

      const tb = document.createElement("div");
      tb.className = "toolbar";
      tb.innerHTML = `<label>排序 <select id="homeGetType" class="compact">
        <option value="1">热门</option>
        <option value="2">最新 / 全部</option>
        <option value="3">最相关</option>
      </select></label>`;
      app.appendChild(tb);
      const sel = tb.querySelector("#homeGetType");
      sel.value = String(homeCursor.get_type);
      sel.onchange = () => {
        homeCursor.get_type = parseInt(sel.value, 10);
        homeCursor.attach = "";
        homeFeedsList = [];
        renderHomeFeeds(gid, false);
      };

      const list = document.createElement("div");
      list.className = "feed-list";
      homeFeedsList.forEach((f) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "feed-item";
        b.innerHTML = `<div class="t">${escapeHtml(f.title || "(无标题)")}</div><div class="m">${escapeHtml(f.author || "")} · ${escapeHtml(f.create_time || "")} · 💬${f.comment_count ?? 0} · 👍${f.prefer_count ?? 0}</div>`;
        b.onclick = () => setHash(`/g/${gid}/f/${encodeURIComponent(f.feed_id)}?ch=`);
        list.appendChild(b);
      });
      app.appendChild(list);

      if (!finish && homeCursor.attach) {
        const more = document.createElement("button");
        more.className = "btn-ghost";
        more.style.marginTop = "0.5rem";
        more.textContent = "加载更多";
        more.onclick = () => renderHomeFeeds(gid, true);
        app.appendChild(more);
      } else if (!homeFeedsList.length) {
        app.appendChild(document.createTextNode("暂无帖子。"));
      }
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p>`;
    }
  }

  async function renderChannelFeeds(gid, cid, loadMore) {
    const name = guildNameById[gid] || gid;
    const key = gid + ":" + cid;
    if (chCursor.key !== key) {
      chCursor = { key, attach: "" };
      chFeedsList = [];
    }
    if (!loadMore) {
      app.innerHTML = "<p>加载帖子…</p>";
      chFeedsList = [];
      chCursor.attach = "";
    }
    const params = new URLSearchParams({ count: "20" });
    if (chCursor.attach) params.set("feed_attch_info", chCursor.attach);

    try {
      const res = await fetchJSON(`/api/panel/guild/${encodeURIComponent(gid)}/channel/${encodeURIComponent(cid)}/feeds?${params}`);
      const d = res.data || {};
      const feeds = d.feeds || [];
      const finish = d.is_finish;
      chCursor.attach = d.feed_attch_info || "";
      chFeedsList = chFeedsList.concat(feeds);

      app.innerHTML = "";
      app.appendChild(
        breadcrumb([
          { label: "我的频道", href: "#/guilds" },
          { label: name, href: `#/g/${gid}` },
          { label: "版块帖子", href: null },
        ])
      );

      const list = document.createElement("div");
      list.className = "feed-list";
      chFeedsList.forEach((f) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "feed-item";
        b.innerHTML = `<div class="t">${escapeHtml(f.title || "(无标题)")}</div><div class="m">${escapeHtml(f.author || "")} · ${escapeHtml(f.create_time || "")}</div>`;
        b.onclick = () => setHash(`/g/${gid}/f/${encodeURIComponent(f.feed_id)}?ch=${encodeURIComponent(cid)}`);
        list.appendChild(b);
      });
      app.appendChild(list);

      if (!finish && chCursor.attach) {
        const more = document.createElement("button");
        more.className = "btn-ghost";
        more.style.marginTop = "0.5rem";
        more.textContent = "加载更多";
        more.onclick = () => renderChannelFeeds(gid, cid, true);
        app.appendChild(more);
      } else if (!chFeedsList.length) {
        app.appendChild(document.createTextNode("暂无帖子。"));
      }
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p>`;
    }
  }

  let memberPageToken = "";
  let membersAcc = {
    gid: null,
    owners: [],
    admins: [],
    ai_members: [],
    members: [],
    robots: [],
  };

  function mergeMemberPage(dst, src) {
    ["owners", "admins", "ai_members", "members", "robots"].forEach((k) => {
      if (Array.isArray(src[k]) && src[k].length) dst[k] = (dst[k] || []).concat(src[k]);
    });
  }

  async function renderMembers(gid, append) {
    const name = guildNameById[gid] || gid;
    if (!append) {
      membersAcc = {
        gid,
        owners: [],
        admins: [],
        ai_members: [],
        members: [],
        robots: [],
      };
      memberPageToken = "";
    }
    app.innerHTML = "<p>加载成员…</p>";
    try {
      const q = memberPageToken ? `?next_page_token=${encodeURIComponent(memberPageToken)}` : "";
      const res = await fetchJSON(`/api/panel/guild/${encodeURIComponent(gid)}/members${q}`);
      const d = res.data || {};
      memberPageToken = (d.next_page_token || "").trim();
      mergeMemberPage(membersAcc, d);
      app.innerHTML = "";
      app.appendChild(
        breadcrumb([
          { label: "我的频道", href: "#/guilds" },
          { label: name, href: `#/g/${gid}` },
          { label: "成员管理", href: null },
        ])
      );
      const sec = (title, arr) => {
        if (!arr || !arr.length) return "";
        let h = `<h3>${escapeHtml(title)}</h3><ul class="member-ul">`;
        arr.forEach((m) => {
          const inner = m["昵称"] || m.bytesMemberName || m.nickname || m.nick || "";
          const tid = m["tinyid"] || m.uint64Tinyid || m.tinyid || "";
          h += `<li>${escapeHtml(inner)} <small>${escapeHtml(String(tid))}</small></li>`;
        });
        h += "</ul>";
        return h;
      };
      const body = document.createElement("div");
      body.innerHTML =
        sec("频道主", membersAcc.owners) +
        sec("管理员", membersAcc.admins) +
        sec("AI 成员", membersAcc.ai_members) +
        sec("成员", membersAcc.members) +
        sec("系统机器人", membersAcc.robots);
      app.appendChild(body);

      const tools = document.createElement("div");
      tools.className = "panel-tools-block";
      tools.style.marginTop = "1rem";
      tools.innerHTML = `<h3>按昵称搜索</h3>
        <div class="panel-tools-row"><input type="text" id="msKw" placeholder="关键词" style="flex:1;" />
        <button type="button" class="btn-primary" id="msBtn">搜索</button></div>
        <div id="msOut" class="glob-search-out"></div>
        <h3 style="margin-top:1rem;">踢出 / 禁言</h3>
        <div class="panel-tools-row"><label>tiny_id</label><input type="text" id="kickTid" style="flex:1;" /></div>
        <div class="btn-row"><button type="button" class="btn-ghost" id="btnKick" style="color:var(--err);">踢出</button></div>
        <div class="panel-tools-row" style="margin-top:0.5rem;">
          <label>禁言到期 Unix 秒（0=解禁）</label><input type="text" id="shuTs" placeholder="如 ${Math.floor(Date.now() / 1000) + 86400}" style="flex:1;" />
          <button type="button" class="btn-primary" id="btnShu">设置禁言</button>
        </div>`;
      app.appendChild(tools);
      tools.querySelector("#msBtn").onclick = async () => {
        const kw = (tools.querySelector("#msKw").value || "").trim();
        const out = tools.querySelector("#msOut");
        if (!kw) {
          showToast("请输入关键词", "error");
          return;
        }
        try {
          const sr = await fetchJSON("/api/panel/member/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ guild_id: gid, keyword: kw, num: 20 }),
          });
          const raw = sr.data || {};
          const mems = raw.members || [];
          out.innerHTML =
            mems.map((x) => `<div>${escapeHtml(x.nickname || "")} <code>${escapeHtml(String(x.tinyid || ""))}</code></div>`).join("") ||
            `<pre class="toast-detail">${escapeHtml(JSON.stringify(raw, null, 2))}</pre>`;
          showToast("搜索完成", "success");
        } catch (e) {
          showToast(e.message, "error");
        }
      };
      tools.querySelector("#btnKick").onclick = async () => {
        const tid = (tools.querySelector("#kickTid").value || "").trim();
        if (!tid) {
          showToast("填写 tiny_id", "error");
          return;
        }
        if (!window.confirm("确定踢出该成员？")) return;
        try {
          const kr = await fetchJSON("/api/panel/member/kick", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ guild_id: gid, member_tinyid: tid }),
          });
          showToast("已提交", "success", resultSummary(kr) || undefined);
        } catch (e) {
          showToast(e.message, "error");
        }
      };
      tools.querySelector("#btnShu").onclick = async () => {
        const tid = (tools.querySelector("#kickTid").value || "").trim();
        const ts = (tools.querySelector("#shuTs").value || "").trim();
        if (!tid || ts === "") {
          showToast("填写 tiny_id 与时间戳", "error");
          return;
        }
        try {
          const sr = await fetchJSON("/api/panel/member/shutup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ guild_id: gid, tiny_id: tid, time_stamp: ts }),
          });
          showToast("已提交", "success", resultSummary(sr) || undefined);
        } catch (e) {
          showToast(e.message, "error");
        }
      };

      if (d.has_more && memberPageToken) {
        const more = document.createElement("button");
        more.className = "btn-ghost";
        more.style.marginTop = "0.5rem";
        more.textContent = "加载更多成员";
        more.onclick = () => renderMembers(gid, true);
        app.appendChild(more);
      }
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p>`;
    }
  }

  async function renderGuildFeedSearch(gid) {
    const name = guildNameById[gid] || gid;
    app.innerHTML = "";
    app.appendChild(
      breadcrumb([
        { label: "我的频道", href: "#/guilds" },
        { label: name, href: `#/g/${gid}` },
        { label: "频道内搜帖", href: null },
      ])
    );
    const box = document.createElement("div");
    box.className = "panel-tools-block";
    box.innerHTML = `<div class="panel-tools-row">
      <input type="text" id="fsQ" placeholder="关键词" style="flex:1;" />
      <button type="button" class="btn-primary" id="fsGo">搜索</button>
    </div><div id="fsOut" class="feed-list" style="margin-top:0.75rem;"></div>`;
    app.appendChild(box);
    box.querySelector("#fsGo").onclick = async () => {
      const query = (box.querySelector("#fsQ").value || "").trim();
      const out = box.querySelector("#fsOut");
      if (!query) {
        showToast("请输入关键词", "error");
        return;
      }
      out.innerHTML = "<p>搜索中…</p>";
      try {
        const res = await fetchJSON("/api/panel/guild-feeds/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ guild_id: gid, query, search_type: { type: 2, feed_type: 1 } }),
        });
        const d = res.data || {};
        const feeds = d.guild_feeds || d.feeds || d.results || [];
        out.innerHTML = "";
        const list = Array.isArray(feeds) ? feeds : [];
        if (!list.length) {
          out.innerHTML = `<pre class="toast-detail">${escapeHtml(JSON.stringify(d, null, 2))}</pre>`;
        } else {
          list.forEach((f) => {
            const fid = f.feed_id || f.feedId || "";
            const ch =
              f.channel_id != null && f.channel_id !== ""
                ? String(f.channel_id)
                : f.channelId != null && f.channelId !== ""
                  ? String(f.channelId)
                  : "";
            const b = document.createElement("button");
            b.type = "button";
            b.className = "feed-item";
            b.innerHTML = `<div class="t">${escapeHtml(f.title || "(无标题)")}</div><div class="m">${escapeHtml(f.author || "")}</div>`;
            b.onclick = () =>
              setHash(`/g/${gid}/f/${encodeURIComponent(fid)}?ch=${encodeURIComponent(ch)}`);
            out.appendChild(b);
          });
        }
        showToast("搜索完成", "success");
      } catch (e) {
        out.innerHTML = "";
        showToast(e.message, "error");
      }
    };
  }

  let ctxDetail = {};

  function channelIdForCtx() {
    const { feed, ch } = ctxDetail;
    return String((feed && feed.channel_id) || ch || "").trim();
  }

  function guildIdForCtx() {
    const { gid, feed } = ctxDetail;
    return String((feed && feed.guild_id) || gid || "").trim();
  }

  async function deletePost() {
    const { fid, feed, gid, ch } = ctxDetail;
    const guild_id = guildIdForCtx();
    const channel_id = channelIdForCtx();
    const create_time = feed.create_time_raw != null ? String(feed.create_time_raw) : "";
    if (!guild_id || !channel_id || !create_time) {
      showToast("缺少频道、版块或帖子时间，无法删除。请从版块帖子进入，或确认接口已返回 channel_id。", "error");
      return;
    }
    if (!window.confirm("确定删除该帖子？此操作不可恢复。")) return;
    try {
      await fetchJSON("/api/panel/feed/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feed_id: fid,
          create_time,
          guild_id,
          channel_id,
        }),
      });
      showToast("帖子已删除", "success");
      setTimeout(() => {
        if (window.history.length > 1) window.history.back();
        else setHash(`/g/${gid}`);
      }, 400);
    } catch (e) {
      showToast(e.message || "删除失败", "error");
    }
  }

  async function deleteComment(c, ownerMode) {
    const { fid, feed } = ctxDetail;
    const comment_type = ownerMode ? 2 : 0;
    const raw = feed.create_time_raw != null ? String(feed.create_time_raw) : "";
    const gid = guildIdForCtx();
    const cid = channelIdForCtx();
    if (!c.comment_id || !c.author_id || !raw) {
      showToast("缺少评论或帖子链式字段，无法删除", "error");
      return;
    }
    const label = ownerMode ? "以楼主身份删除他人评论" : "删除自己的评论";
    if (!window.confirm("确定" + label + "？")) return;
    try {
      const body = {
        feed_id: fid,
        feed_create_time: raw,
        comment_type,
        comment_id: String(c.comment_id),
        comment_author_id: String(c.author_id),
        guild_id: gid,
      };
      if (cid) body.channel_id = cid;
      const r = await fetchJSON("/api/panel/feed/comment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const detail = resultSummary(r);
      showToast("评论已删除", "success", detail || undefined);
      const { gid: g2, fid: f2, ch: ch2 } = ctxDetail;
      renderFeedDetail(g2, f2, ch2);
    } catch (e) {
      showToast(e.message || "删除失败", "error");
    }
  }

  async function renderFeedDetail(gid, fid, ch) {
    const name = guildNameById[gid] || gid;
    app.innerHTML = "<p>加载帖子详情…</p>";
    ctxDetail = { gid, fid, ch };

    try {
      const q = new URLSearchParams({ guild_id: gid, feed_id: fid });
      if (ch) q.set("channel_id", ch);
      const [det, com] = await Promise.all([
        fetchJSON(`/api/panel/feed/detail?${q}`),
        fetchJSON(`/api/panel/feed/comments?${new URLSearchParams({ guild_id: gid, channel_id: ch || "", feed_id: fid, page_size: "20", rank_type: "2" })}`),
      ]);

      const feed = (det.data && det.data.feed) || {};
      const comments = (com.data && com.data.comments) || [];
      ctxDetail.feed = feed;
      ctxDetail.comments = comments;
      ctxDetail.commentAttach = (com.data && com.data.attach_info) || "";
      ctxDetail.commentExt = com.data && com.data.ext_info;

      const title = typeof feed.title === "object" && feed.title && feed.title.text ? feed.title.text : feed.title || "";
      const body =
        typeof feed.contents === "object" && feed.contents && feed.contents.text
          ? feed.contents.text
          : feed.contents || "";

      app.innerHTML = "";
      app.appendChild(
        breadcrumb([
          { label: "我的频道", href: "#/guilds" },
          { label: name, href: `#/g/${gid}` },
          { label: "帖子", href: null },
        ])
      );

      const box = document.createElement("div");
      box.className = "detail-box";
      box.innerHTML = `<div><strong>${escapeHtml(title)}</strong></div>
        <div class="m" style="color:var(--muted);margin-top:0.35rem;">${escapeHtml(feed.author || "")} · ${escapeHtml(feed.create_time || "")} · 💬${feed.comment_count ?? 0} · 👍${feed.prefer_count ?? 0}</div>
        <div class="body">${escapeHtml(body)}</div>`;
      app.appendChild(box);

      const act = document.createElement("div");
      act.className = "btn-row";
      const likeBtn = document.createElement("button");
      likeBtn.className = "btn-primary";
      likeBtn.textContent = "给帖子点赞";
      likeBtn.onclick = () => doPrefer(1);
      const unlikeBtn = document.createElement("button");
      unlikeBtn.className = "btn-ghost";
      unlikeBtn.textContent = "取消点赞";
      unlikeBtn.onclick = () => doPrefer(3);
      const editPostBtn = document.createElement("button");
      editPostBtn.className = "btn-ghost";
      editPostBtn.textContent = "修改帖子";
      editPostBtn.onclick = () => openEditModal();
      const delPostBtn = document.createElement("button");
      delPostBtn.className = "btn-ghost";
      delPostBtn.style.color = "var(--err)";
      delPostBtn.textContent = "删除帖子";
      delPostBtn.onclick = () => deletePost();
      act.appendChild(likeBtn);
      act.appendChild(unlikeBtn);
      act.appendChild(editPostBtn);
      act.appendChild(delPostBtn);
      app.appendChild(act);

      const form = document.createElement("div");
      form.innerHTML = `<h3 style="font-size:0.95rem;margin:0.75rem 0 0.35rem;">发表评论</h3>
        <textarea id="cmtBody" rows="3" style="width:100%;" placeholder="内容"></textarea>
        <label style="display:block;margin-top:0.5rem;font-size:0.9rem;">附图（可选，最多 1 张）</label>
        <input type="file" id="cmtImg" accept="image/*" style="margin-top:0.25rem;" />
        <button type="button" class="btn-primary" id="cmtSend" style="margin-top:0.5rem;">发送评论</button>
        <p class="hint" style="margin-top:0.35rem;">带图时会先上传图片再提交；需要 @ 用户请用成员搜索拿到 tiny_id（见文档）。</p>`;
      app.appendChild(form);
      form.querySelector("#cmtSend").onclick = () => doComment();

      const cs = document.createElement("div");
      cs.className = "comments-section";
      cs.innerHTML = "<h3>评论</h3>";
      comments.forEach((c) => {
        const div = document.createElement("div");
        div.className = "comment-item";
        const content =
          typeof c.content === "object" && c.content && c.content.text ? c.content.text : c.content || "";
        div.innerHTML = `<div><strong>${escapeHtml(c.author || "")}</strong> · ${escapeHtml(c.create_time || "")}</div>
          <div style="margin-top:0.25rem;">${escapeHtml(content)}</div>
          <div class="comment-actions">
            <button type="button" class="btn-ghost" data-like="1">赞</button>
            <button type="button" class="btn-ghost" data-like="0">取消赞</button>
            <button type="button" class="btn-ghost" data-del="self" style="color:var(--err);">删自己的评论</button>
            <button type="button" class="btn-ghost" data-del="owner" style="color:var(--err);">楼主删评论</button>
          </div>`;
        div.querySelector('[data-like="1"]').onclick = () => doLikeComment(c, true);
        div.querySelector('[data-like="0"]').onclick = () => doLikeComment(c, false);
        div.querySelector('[data-del="self"]').onclick = () => deleteComment(c, false);
        div.querySelector('[data-del="owner"]').onclick = () => deleteComment(c, true);
        cs.appendChild(div);
      });
      if (com.data && !com.data.is_finish && ctxDetail.commentAttach) {
        const more = document.createElement("button");
        more.className = "btn-ghost";
        more.textContent = "更多评论";
        more.onclick = loadMoreComments;
        cs.appendChild(more);
      }
      app.appendChild(cs);
    } catch (e) {
      app.innerHTML = `<p class="msg-err">${escapeHtml(e.message)}</p>`;
    }
  }

  async function loadMoreComments() {
    const { gid, fid, ch, commentAttach } = ctxDetail;
    if (!commentAttach) return;
    try {
      const com = await fetchJSON(
        `/api/panel/feed/comments?${new URLSearchParams({
          guild_id: gid,
          channel_id: ch || "",
          feed_id: fid,
          page_size: "20",
          rank_type: "2",
          attach_info: commentAttach,
        })}`
      );
      const newComments = (com.data && com.data.comments) || [];
      ctxDetail.comments = (ctxDetail.comments || []).concat(newComments);
      ctxDetail.commentAttach = (com.data && com.data.attach_info) || "";
      renderFeedDetail(gid, fid, ch);
    } catch (e) {
      showToast(e.message || "加载失败", "error");
    }
  }

  async function doPrefer(action) {
    const { fid, feed } = ctxDetail;
    try {
      const body = { feed_id: fid, action, guild_id: guildIdForCtx() };
      const cid = channelIdForCtx();
      if (cid) body.channel_id = cid;
      const r = await fetchJSON("/api/panel/feed/prefer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const detail = resultSummary(r);
      showToast("操作成功", "success", detail || undefined);
    } catch (e) {
      showToast(e.message || "操作失败", "error");
    }
  }

  async function doComment() {
    const { gid, fid, ch, feed } = ctxDetail;
    let content = (document.getElementById("cmtBody") && document.getElementById("cmtBody").value) || "";
    const imgInput = document.getElementById("cmtImg");
    const imgFile = imgInput && imgInput.files && imgInput.files[0];
    const guild_id = guildIdForCtx();
    const cid = channelIdForCtx();
    if (!content.trim() && !imgFile) {
      showToast("请输入评论内容或选择一张图片", "error");
      return;
    }
    if (imgFile && !cid) {
      showToast("带图评论需要版块 ID：请从版块帖子列表进入本帖，或确认详情接口已返回 channel_id。", "error");
      return;
    }
    if (!content.trim() && imgFile) content = " ";
    const raw = feed.create_time_raw != null ? String(feed.create_time_raw) : "";
    if (!raw) {
      showToast("缺少帖子时间戳，无法评论", "error");
      return;
    }
    try {
      let images = [];
      if (imgFile) {
        const fd = new FormData();
        fd.append("guild_id", guild_id);
        fd.append("channel_id", cid);
        fd.append("file", imgFile);
        const up = await fetchJSONForm("/api/panel/comment/upload-image", fd);
        images = (up.images || []).slice(0, 1);
        if (!images.length) {
          showToast("图片上传未返回有效数据", "error");
          return;
        }
      }
      const body = {
        feed_id: fid,
        feed_create_time: raw,
        comment_type: 1,
        content: content.trim(),
        guild_id,
      };
      if (cid) body.channel_id = cid;
      if (images.length) body.images = images;
      const r = await fetchJSON("/api/panel/feed/comment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const detail = resultSummary(r);
      showToast("评论已发送", "success", detail || undefined);
      renderFeedDetail(gid, fid, ch);
    } catch (e) {
      showToast(e.message || "发送失败", "error");
    }
  }

  async function doLikeComment(c, isLike) {
    const { fid, feed } = ctxDetail;
    const like_type = isLike ? 3 : 4;
    const raw = feed.create_time_raw != null ? String(feed.create_time_raw) : "";
    const author = feed.author_id || "";
    if (!c.comment_id || !c.author_id || !raw || !author) {
      showToast("缺少评论或帖子链式字段", "error");
      return;
    }
    try {
      const body = {
        like_type,
        feed_id: fid,
        feed_author_id: author,
        feed_create_time: raw,
        guild_id: guildIdForCtx(),
        comment_id: String(c.comment_id),
        comment_author_id: String(c.author_id),
      };
      const cid = channelIdForCtx();
      if (cid) body.channel_id = cid;
      const r = await fetchJSON("/api/panel/feed/like", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const detail = resultSummary(r);
      showToast("操作成功", "success", detail || undefined);
    } catch (e) {
      showToast(e.message || "操作失败", "error");
    }
  }

  function openEditModal() {
    const { fid, feed, gid, ch } = ctxDetail;
    const guild_id = guildIdForCtx();
    const channel_id = channelIdForCtx();
    const create_time = feed.create_time_raw != null ? String(feed.create_time_raw) : "";
    const feed_type = feed.feed_type || 1;
    const title = typeof feed.title === "object" && feed.title && feed.title.text ? feed.title.text : feed.title || "";
    const content = typeof feed.contents === "object" && feed.contents && feed.contents.text ? feed.contents.text : feed.contents || "";

    if (!guild_id || !channel_id || !create_time) {
      showToast("缺少频道、版块或帖子时间，无法修改。请从版块帖子进入，或确认接口已返回 channel_id。", "error");
      return;
    }

    const bg = document.createElement("div");
    bg.className = "modal-bg";
    const box = document.createElement("div");
    box.className = "modal";
    box.style.maxWidth = "600px";
    box.innerHTML = `<h3>修改帖子</h3>
      <label>帖子类型</label>
      <select id="editFt" style="width:100%;margin-bottom:0.5rem;">
        <option value="1" ${feed_type === 1 ? "selected" : ""}>短贴</option>
        <option value="2" ${feed_type === 2 ? "selected" : ""}>长贴</option>
      </select>
      <label>标题（长贴必填）</label>
      <input type="text" id="editTitle" style="width:100%;margin-bottom:0.5rem;" value="${escapeHtml(title)}" />
      <label>正文</label>
      <textarea id="editContent" rows="5" style="width:100%;">${escapeHtml(content)}</textarea>
      <div class="btn-row" style="margin-top:0.75rem;">
        <button type="button" class="btn-primary" id="editSubmit">保存修改</button>
        <button type="button" class="btn-ghost" id="editCancel">取消</button>
      </div>`;
    bg.appendChild(box);
    document.body.appendChild(bg);

    box.querySelector("#editCancel").onclick = () => bg.remove();
    bg.onclick = (ev) => {
      if (ev.target === bg) bg.remove();
    };

    box.querySelector("#editSubmit").onclick = async () => {
      const editFt = parseInt(box.querySelector("#editFt").value, 10);
      const editTitle = box.querySelector("#editTitle").value.trim();
      const editContent = box.querySelector("#editContent").value.trim();

      if (editFt === 2 && !editTitle) {
        showToast("长贴必须填写标题", "error");
        return;
      }

      if (!editContent) {
        showToast("请填写正文内容", "error");
        return;
      }

      try {
        const body = {
          feed_id: fid,
          create_time,
          guild_id,
          channel_id,
          feed_type: editFt,
          title: editTitle,
          content: editContent
        };

        const r = await fetchJSON("/api/panel/feed/alter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        const detail = resultSummary(r);
        showToast("帖子修改成功", "success", detail || undefined);
        bg.remove();
        renderFeedDetail(gid, fid, ch);
      } catch (e) {
        showToast(e.message || "修改失败", "error");
      }
    };
  }

  function openPublishModal(gid, channels) {
    const bg = document.createElement("div");
    bg.className = "modal-bg";
    const box = document.createElement("div");
    box.className = "modal";
    const opts = (channels || [])
      .map((c) => `<option value="${escapeHtml(c.channel_id)}">${escapeHtml(c.name)}</option>`)
      .join("");
    if (!opts) {
      showToast("未解析到版块，请在脚本控制台核对 get_guild_channel_list", "error");
      return;
    }
    box.innerHTML = `<h3>发帖（支持多图 / 视频）</h3>
      <label>版块</label><select id="pubCh" style="width:100%;margin-bottom:0.5rem;">${opts}</select>
      <label>类型</label><select id="pubFt" style="width:100%;margin-bottom:0.5rem;"><option value="1">短贴</option><option value="2">长贴</option></select>
      <label>标题（长贴必填）</label><input type="text" id="pubTitle" style="width:100%;margin-bottom:0.5rem;" />
      <label>正文</label><textarea id="pubContent" rows="5" style="width:100%;"></textarea>
      <label style="display:flex;align-items:center;margin-top:0.5rem;gap:0.35rem;cursor:pointer;">
        <input type="checkbox" id="pubMarkdown" checked />
        <span>使用 Markdown 格式</span>
      </label>
      <label style="margin-top:0.5rem;">图片（可多选）</label>
      <input type="file" id="pubImgs" accept="image/*" multiple style="width:100%;margin-bottom:0.5rem;" />
      <div id="pubVidWrap"></div>
      <button type="button" class="btn-ghost" id="pubAddVid" style="margin-top:0.35rem;">添加视频</button>
      <p class="hint" style="margin-top:0.35rem;">视频：每行一个文件；<strong>无封面时需本机已安装 ffmpeg</strong>（否则请为每段视频选择封面图）。与图片可同时使用。</p>
      <div class="btn-row" style="margin-top:0.75rem;">
        <button type="button" class="btn-primary" id="pubGo">发布</button>
        <button type="button" class="btn-ghost" id="pubClose">取消</button>
      </div>`;
    bg.appendChild(box);
    document.body.appendChild(bg);
    box.querySelector("#pubClose").onclick = () => bg.remove();
    bg.onclick = (ev) => {
      if (ev.target === bg) bg.remove();
    };
    const vidWrap = box.querySelector("#pubVidWrap");
    let vidRows = 0;
    function addVidRow() {
      const i = vidRows++;
      const row = document.createElement("div");
      row.className = "panel-tools-row";
      row.style.flexWrap = "wrap";
      row.style.gap = "0.35rem";
      row.style.marginTop = "0.35rem";
      row.innerHTML = `<label>视频 ${i + 1}</label><input type="file" class="pubVid" data-i="${i}" accept="video/*" style="flex:1;min-width:120px;" />
        <label>封面</label><input type="file" class="pubCov" data-i="${i}" accept="image/*" style="flex:1;min-width:120px;" />`;
      vidWrap.appendChild(row);
    }
    box.querySelector("#pubAddVid").onclick = () => addVidRow();

    box.querySelector("#pubGo").onclick = async () => {
      const channel_id = box.querySelector("#pubCh").value;
      const feed_type = parseInt(box.querySelector("#pubFt").value, 10);
      const title = box.querySelector("#pubTitle").value.trim();
      const content = box.querySelector("#pubContent").value.trim();
      const is_markdown = box.querySelector("#pubMarkdown").checked;
      const imgs = box.querySelector("#pubImgs").files;
      if (!channel_id) {
        showToast("请选择版块", "error");
        return;
      }
      if (feed_type === 2 && !title) {
        showToast("长贴需要标题", "error");
        return;
      }
      try {
        const fd = new FormData();
        fd.append("guild_id", gid);
        fd.append("channel_id", channel_id);
        fd.append("feed_type", String(feed_type));
        fd.append("content", content);
        fd.append("on_upload_error", "abort");
        fd.append("is_markdown", is_markdown ? "true" : "false");
        if (title) fd.append("title", title);
        let ii = 0;
        if (imgs && imgs.length) {
          for (let k = 0; k < imgs.length; k++) fd.append(`image_${ii++}`, imgs[k]);
        }
        let vi = 0;
        box.querySelectorAll(".pubVid").forEach((inp) => {
          const f = inp.files && inp.files[0];
          if (!f) return;
          fd.append(`video_${vi}`, f);
          const cov = box.querySelector(`.pubCov[data-i="${inp.getAttribute("data-i")}"]`);
          const cf = cov && cov.files && cov.files[0];
          if (cf) fd.append(`video_cover_${vi}`, cf);
          vi += 1;
        });
        const r = await fetchJSONForm("/api/panel/feed/publish-media", fd);
        const detail = resultSummary(r);
        showToast("发帖已提交", "success", detail || undefined);
        bg.remove();
      } catch (e) {
        showToast(e.message || "发帖失败", "error");
      }
    };
  }

  function newUUID() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    return "j" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  async function renderOpenAISettings() {
    app.innerHTML = "<p>加载…</p>";
    const cfg = await fetchJSON("/api/automation/openai");
    app.innerHTML = "";
    app.appendChild(
      breadcrumb([
        { label: "我的频道", href: "#/guilds" },
        { label: "OpenAI 配置", href: null },
      ])
    );
    const wrap = document.createElement("div");
    wrap.className = "automation-page";
    wrap.innerHTML =
      '<div class="panel-tools-block">' +
      '<h2 class="panel-tools-title">OpenAI 兼容接口</h2>' +
      '<p class="hint">将 <code>OPENAI_API_KEY</code>、<code>OPENAI_BASE_URL</code>、<code>OPENAI_MODEL</code> 写入项目根目录 <code>.env</code>，与 <code>QQ_AI_CONNECT_TOKEN</code> 同文件（路径见下方接口返回）。</p>' +
      '<div class="panel-tools-row"><label style="min-width:5rem">Base URL</label>' +
      '<input type="text" id="oaBase" style="flex:1;min-width:200px;padding:0.4rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);" placeholder="https://api.openai.com/v1" /></div>' +
      '<div class="panel-tools-row" style="margin-top:0.5rem;"><label style="min-width:5rem">Model</label>' +
      '<input type="text" id="oaModel" style="flex:1;min-width:200px;padding:0.4rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);" placeholder="gpt-4o-mini" /></div>' +
      '<div class="panel-tools-row" style="margin-top:0.5rem;"><label style="min-width:5rem">API Key</label>' +
      '<input type="password" id="oaKey" autocomplete="off" style="flex:1;min-width:200px;padding:0.4rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);" placeholder="留空则不修改已保存的密钥" /></div>' +
      '<p class="hint" id="oaKeyHint"></p>' +
      '<p class="hint" style="font-size:0.8rem;color:var(--muted)">文件：<span id="oaDotenv"></span></p>' +
      '<div class="btn-row" style="margin-top:0.75rem;">' +
      '<button type="button" class="btn-primary" id="oaSave">保存到 .env</button> ' +
      '<button type="button" class="btn-ghost" id="oaClear">清除 API Key</button> ' +
      '<button type="button" class="btn-ghost" id="oaTest">测试连通</button></div></div>' +
      '<pre id="oaTestOut" class="toast-detail" style="max-height:240px;overflow:auto;margin-top:1rem;"></pre>';
    app.appendChild(wrap);
    wrap.querySelector("#oaBase").value = cfg.baseUrl || "";
    wrap.querySelector("#oaModel").value = cfg.model || "";
    wrap.querySelector("#oaDotenv").textContent = cfg.dotenvPath || "";
    const kh = wrap.querySelector("#oaKeyHint");
    kh.textContent = cfg.configured ? "当前已保存密钥 " + (cfg.hint || "") : "尚未保存过 API Key。";
    const outPre = wrap.querySelector("#oaTestOut");
    outPre.style.display = "none";
    wrap.querySelector("#oaSave").onclick = async () => {
      const body = {
        base_url: (wrap.querySelector("#oaBase").value || "").trim(),
        model: (wrap.querySelector("#oaModel").value || "").trim(),
      };
      const k = (wrap.querySelector("#oaKey").value || "").trim();
      if (k) body.api_key = k;
      try {
        const r = await fetchJSON("/api/automation/openai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        kh.textContent = r.configured ? "当前已保存密钥 " + (r.hint || "") : "尚未保存 API Key。";
        wrap.querySelector("#oaKey").value = "";
        showToast("已写入 .env", "success");
      } catch (e) {
        showToast(e.message || "保存失败", "error");
      }
    };
    wrap.querySelector("#oaClear").onclick = async () => {
      if (!window.confirm("确定从 .env 中删除 OPENAI_API_KEY？")) return;
      try {
        const r = await fetchJSON("/api/automation/openai", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ clear_api_key: true }),
        });
        kh.textContent = r.configured ? "当前已保存密钥 " + (r.hint || "") : "已清除 API Key。";
        showToast("已清除", "success");
      } catch (e) {
        showToast(e.message || "操作失败", "error");
      }
    };
    wrap.querySelector("#oaTest").onclick = async () => {
      outPre.style.display = "block";
      outPre.textContent = "请求中…";
      try {
        const r = await fetchJSON("/api/automation/openai/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: "简短回复一句确认连通即可。" }),
        });
        outPre.textContent = (r.reply || JSON.stringify(r, null, 2)) + "\n\n" + JSON.stringify(r.raw, null, 2);
        showToast("测试成功", "success");
      } catch (e) {
        outPre.textContent = e.message || String(e);
        showToast(e.message || "测试失败", "error");
      }
    };
  }

  function automationIntervalRow(job) {
    const id = job.id || newUUID();
    const el = document.createElement("div");
    el.className = "automation-job-card js-automation-interval";
    el.dataset.id = id;
    el.innerHTML =
      '<div class="panel-tools-row" style="flex-wrap:wrap;gap:0.35rem;">' +
      '<label><input type="checkbox" class="js-en" /> 启用</label>' +
      '<label>guild_id <input type="text" class="js-gid compact" style="width:9rem;" /></label>' +
      '<label>channel_id <input type="text" class="js-cid compact" style="width:9rem;" /></label>' +
      '<label>间隔(秒) <input type="number" class="js-int compact" min="30" step="1" style="width:5rem;" /></label>' +
      '<label>拉帖数 <input type="number" class="js-fc compact" min="1" max="50" style="width:4rem;" /></label>' +
      '<button type="button" class="btn-ghost js-del">删除</button></div>' +
      '<label class="hint" style="display:block;margin-top:0.5rem;">自定义提示词（与最新帖子摘要一并发给模型；系统说明中会提示可使用本 Skill 回复、点赞、发帖等）</label>' +
      '<textarea class="js-prompt" rows="5" style="width:100%;margin-top:0.25rem;padding:0.45rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);"></textarea>';
    el.querySelector(".js-en").checked = job.enabled !== false;
    el.querySelector(".js-gid").value = job.guild_id || "";
    el.querySelector(".js-cid").value = job.channel_id || "";
    el.querySelector(".js-int").value = job.interval_seconds != null ? job.interval_seconds : 300;
    el.querySelector(".js-fc").value = job.feed_count != null ? job.feed_count : 15;
    el.querySelector(".js-prompt").value = job.prompt || "";
    el.querySelector(".js-del").onclick = () => el.remove();
    return el;
  }

  function automationTimedRow(job) {
    const id = job.id || newUUID();
    const el = document.createElement("div");
    el.className = "automation-job-card js-automation-timed";
    el.dataset.id = id;
    const hm = (job.time_hhmm || "09:00").replace(/：/g, ":");
    el.innerHTML =
      '<div class="panel-tools-row" style="flex-wrap:wrap;gap:0.35rem;">' +
      '<label><input type="checkbox" class="js-en" /> 启用</label>' +
      '<label>每日时间 <input type="time" class="js-time compact" /></label>' +
      '<button type="button" class="btn-ghost js-del">删除</button></div>' +
      '<label class="hint" style="display:block;margin-top:0.5rem;">到点后向模型发送以下内容（系统说明中会提示可使用本 Skill 进行频道操作；鉴权 token 在 .env）</label>' +
      '<textarea class="js-prompt" rows="5" style="width:100%;margin-top:0.25rem;padding:0.45rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);"></textarea>';
    el.querySelector(".js-en").checked = job.enabled !== false;
    el.querySelector(".js-time").value = hm.length === 5 ? hm : "09:00";
    el.querySelector(".js-prompt").value = job.prompt || "";
    el.querySelector(".js-del").onclick = () => el.remove();
    return el;
  }

  function collectAutomationJobs(host) {
    const interval_jobs = [];
    host.querySelectorAll(".js-automation-interval").forEach((row) => {
      interval_jobs.push({
        id: row.dataset.id || newUUID(),
        enabled: row.querySelector(".js-en").checked,
        guild_id: (row.querySelector(".js-gid").value || "").trim(),
        channel_id: (row.querySelector(".js-cid").value || "").trim(),
        interval_seconds: parseInt(row.querySelector(".js-int").value, 10) || 300,
        feed_count: parseInt(row.querySelector(".js-fc").value, 10) || 15,
        prompt: (row.querySelector(".js-prompt").value || "").trim(),
      });
    });
    const timed_jobs = [];
    host.querySelectorAll(".js-automation-timed").forEach((row) => {
      timed_jobs.push({
        id: row.dataset.id || newUUID(),
        enabled: row.querySelector(".js-en").checked,
        time_hhmm: (row.querySelector(".js-time").value || "09:00").trim(),
        prompt: (row.querySelector(".js-prompt").value || "").trim(),
      });
    });
    return { interval_jobs, timed_jobs };
  }

  async function renderAutomationJobs() {
    app.innerHTML = "<p>加载…</p>";
    const data = await fetchJSON("/api/automation/jobs");
    app.innerHTML = "";
    app.appendChild(
      breadcrumb([
        { label: "我的频道", href: "#/guilds" },
        { label: "定时任务", href: null },
      ])
    );
    const wrap = document.createElement("div");
    wrap.className = "automation-page";
    wrap.innerHTML =
      '<div class="panel-tools-block">' +
      '<h2 class="panel-tools-title">间隔任务（本地缓存 → OpenAI + 自动工具）</h2>' +
      '<p class="hint">每次触发会先拉时间线并缓存到 <code>.tcc_feed_cache/</code>，对前几条帖抓取一页评论写入缓存，再把缓存全文与提示词发给模型；模型通过 function calling 触发点赞、评论、发帖等脚本，<strong>无需人工审批</strong>。QQ token 仍在根目录 <code>.env</code>。</p>' +
      '<div id="automationIntervalHost"></div>' +
      '<button type="button" class="btn-ghost" id="btnAddInterval">＋ 添加间隔任务</button></div>' +
      '<div class="panel-tools-block" style="margin-top:1.25rem;">' +
      '<h2 class="panel-tools-title">定时任务（每日固定时刻 → OpenAI）</h2>' +
      '<p class="hint">在服务器本地时间的该时刻触发一次（同一天内不重复）。同样启用自动工具：模型可直接调用 Skill 完成发帖等操作。</p>' +
      '<div id="automationTimedHost"></div>' +
      '<button type="button" class="btn-ghost" id="btnAddTimed">＋ 添加定时任务</button></div>' +
      '<div class="btn-row" style="margin-top:1rem;">' +
      '<button type="button" class="btn-primary" id="btnSaveJobs">保存任务</button> ' +
      '<button type="button" class="btn-ghost" id="btnRefreshLogs">刷新运行日志</button></div>' +
      '<p class="hint" style="margin-top:0.75rem;">任务列表保存在项目根目录 <code>.tcc_webui_jobs.json</code>。</p>' +
      '<h3 class="panel-tools-title" style="margin-top:1rem;font-size:0.95rem;">运行日志</h3>' +
      '<pre id="automationLogPre" class="toast-detail" style="max-height:200px;overflow:auto;"></pre>' +
      '<div class="panel-tools-block" style="margin-top:1.25rem;">' +
      '<h2 class="panel-tools-title">立即试运行（写缓存 → 模型 → 可选自动执行工具）</h2>' +
      '<div class="panel-tools-row"><label>guild_id</label><input type="text" id="onceGid" class="compact" style="flex:1;" /></div>' +
      '<div class="panel-tools-row" style="margin-top:0.35rem;"><label>channel_id</label><input type="text" id="onceCid" class="compact" style="flex:1;" /></div>' +
      '<div class="panel-tools-row" style="margin-top:0.35rem;"><label>帖数</label><input type="number" id="onceCnt" min="1" max="50" value="10" style="width:5rem;" /></div>' +
      '<div class="panel-tools-row" style="margin-top:0.35rem;flex-wrap:wrap;gap:0.5rem;">' +
      '<label><input type="checkbox" id="onceRefresh" checked /> 重新拉取并更新缓存</label> ' +
      '<label><input type="checkbox" id="onceTools" checked /> 自动执行模型 tool_calls（点赞/评论/发帖）</label></div>' +
      '<div class="panel-tools-row" style="margin-top:0.35rem;"><label>前 N 条帖附带评论预览</label>' +
      '<input type="number" id="onceCmtN" min="0" max="10" value="3" style="width:4rem;" /></div>' +
      '<label class="hint" style="display:block;margin-top:0.5rem;">提示词</label>' +
      '<textarea id="oncePrompt" rows="4" style="width:100%;padding:0.45rem;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);"></textarea>' +
      '<button type="button" class="btn-primary" id="btnRunOnce" style="margin-top:0.5rem;">立即拉帖并请求 OpenAI</button>' +
      '<pre id="onceOut" class="toast-detail" style="max-height:280px;overflow:auto;margin-top:0.5rem;"></pre></div>';
    app.appendChild(wrap);
    const ih = wrap.querySelector("#automationIntervalHost");
    const th = wrap.querySelector("#automationTimedHost");
    (data.interval_jobs || []).forEach((j) => ih.appendChild(automationIntervalRow(j)));
    (data.timed_jobs || []).forEach((j) => th.appendChild(automationTimedRow(j)));
    wrap.querySelector("#btnAddInterval").onclick = () =>
      ih.appendChild(
        automationIntervalRow({
          id: newUUID(),
          enabled: true,
          guild_id: "",
          channel_id: "",
          interval_seconds: 300,
          feed_count: 15,
          prompt: "",
        })
      );
    wrap.querySelector("#btnAddTimed").onclick = () =>
      th.appendChild(
        automationTimedRow({
          id: newUUID(),
          enabled: true,
          time_hhmm: "09:00",
          prompt: "",
        })
      );
    async function refreshLogs() {
      try {
        const lg = await fetchJSON("/api/automation/logs?limit=100");
        wrap.querySelector("#automationLogPre").textContent = (lg.lines || []).join("\n") || "（暂无）";
      } catch (e) {
        wrap.querySelector("#automationLogPre").textContent = e.message || String(e);
      }
    }
    wrap.querySelector("#btnRefreshLogs").onclick = () => refreshLogs();
    wrap.querySelector("#btnSaveJobs").onclick = async () => {
      const payload = collectAutomationJobs(wrap);
      try {
        await fetchJSON("/api/automation/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("已保存", "success");
        await refreshLogs();
      } catch (e) {
        showToast(e.message || "保存失败", "error");
      }
    };
    wrap.querySelector("#btnRunOnce").onclick = async () => {
      const pre = wrap.querySelector("#onceOut");
      pre.textContent = "执行中…";
      try {
        const r = await fetchJSON("/api/automation/jobs/run-once", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            guild_id: (wrap.querySelector("#onceGid").value || "").trim(),
            channel_id: (wrap.querySelector("#onceCid").value || "").trim(),
            feed_count: parseInt(wrap.querySelector("#onceCnt").value, 10) || 10,
            prompt: (wrap.querySelector("#oncePrompt").value || "").trim(),
            refresh_cache: wrap.querySelector("#onceRefresh").checked,
            execute_tools: wrap.querySelector("#onceTools").checked,
            comments_for_top_n: parseInt(wrap.querySelector("#onceCmtN").value, 10) || 0,
          }),
        });
        let out =
          "—— 模型回复 ——\n" +
          (r.reply || "") +
          "\n\n—— 缓存文件 ——\n" +
          (r.cachePath || "") +
          " @ " +
          (r.cachedAt || "");
        if (r.tool_trace && r.tool_trace.length)
          out += "\n\n—— 工具执行轨迹 ——\n" + JSON.stringify(r.tool_trace, null, 2);
        out += "\n\n—— 缓存摘要预览 ——\n" + (r.feeds_preview || "");
        pre.textContent = out;
        showToast("完成", "success");
      } catch (e) {
        pre.textContent = e.message || String(e);
        showToast(e.message || "失败", "error");
      }
    };
    await refreshLogs();
  }

  async function navigate() {
    const { parts, q } = getRoute();
    if (!parts.length || parts[0] === "guilds") {
      await renderGuilds();
      return;
    }
    if (parts[0] === "g" && parts[1]) {
      const gid = parts[1];
      if (parts.length === 2) {
        await renderHub(gid);
        return;
      }
      if (parts.length === 3 && parts[2] === "home") {
        await renderHomeFeeds(gid);
        return;
      }
      if (parts.length === 4 && parts[2] === "c") {
        await renderChannelFeeds(gid, parts[3]);
        return;
      }
      if (parts.length === 4 && parts[2] === "f") {
        const fid = decodeURIComponent(parts[3]);
        const ch = (q.get("ch") || "").trim();
        await renderFeedDetail(gid, fid, ch);
        return;
      }
      if (parts.length === 3 && parts[2] === "members") {
        await renderMembers(gid, false);
        return;
      }
      if (parts.length === 3 && parts[2] === "feed-search") {
        await renderGuildFeedSearch(gid);
        return;
      }
    }
    if (parts[0] === "automation" && parts[1] === "openai") {
      await renderOpenAISettings();
      return;
    }
    if (parts[0] === "automation" && parts[1] === "jobs") {
      await renderAutomationJobs();
      return;
    }
    app.innerHTML = "<p>未知路由</p>";
  }

  window.addEventListener("hashchange", () => navigate());

  const btnBack = document.getElementById("btnBack");
  if (btnBack) {
    btnBack.onclick = () => {
      if (window.history.length > 1) window.history.back();
      else location.hash = "#/guilds";
    };
  }

  navigate();
})();
