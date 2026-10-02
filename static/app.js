(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }
  const INIT_DATA = tg ? tg.initData : "";

  // ----------------------------------------------------------------------- //
  // Ranglar — Anthropic dataviz skill'ining tasdiqlangan palitrasi.
  // Status ranglar (kirim/chiqim/qarz) mode-invariant, faqat "chiqim" light/
  // dark uchun ikki xil qadam. Kategoriya ranglari — 8 xil hue, adjacent
  // pairlist (donut/bar) uchun validatsiya qilingan, light/dark alohida.
  // ----------------------------------------------------------------------- //

  const SCHEME = (tg && tg.colorScheme) ||
    (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");

  // CSS ham AYNAN shu qarorga bo'ysunishi uchun ildizga belgi qo'yamiz.
  // Aks holda CSS brauzerning prefers-color-scheme'iga, JS esa Telegram
  // mavzusiga qarab qolib, yorug' fonda qorong'i palitra chizilishi mumkin.
  document.documentElement.setAttribute("data-theme", SCHEME);

  // Qarz yo'nalishlari uchun status emas, KATEGORIYA ranglari ishlatiladi:
  // status warning/serious juftligi (sariq/to'q sariq) oddiy ko'rishda ham
  // ajratib bo'lmas darajada yaqin (ΔE 13.6 < 15). Ko'k+to'q sariq juftligi
  // validatordan ikkala mavzuda to'liq o'tadi (ΔE 24.7+).
  // Jamg'arma uchun binafsha: yashil (kirim) va qizil (chiqim) bilan
  // aralashmasin — u ikkalasidan ham boshqa toifadagi harakat.
  //
  // «Yechilgan» uchun binafshaning ochroq soyasi YETMADI — jonli
  // ekranda ikkala nuqta bir xil ko'rindi. Shuning uchun u boshqa
  // rangga (kuzatiladigan sariq-jigarrang) o'tkazildi: bu ikkisi
  // yonma-yon turadi va farqlanishi shart.
  const STATUS = SCHEME === "light"
    ? { kirim: "#0ca30c", chiqim: "#d03b3b", qarz_berdim: "#2a78d6",
        qarz_oldim: "#eb6834", jamgarma: "#7048c4", jamgarma_yechdim: "#b07d18" }
    : { kirim: "#0ca30c", chiqim: "#e66767", qarz_berdim: "#3987e5",
        qarz_oldim: "#d95926", jamgarma: "#a98ae0", jamgarma_yechdim: "#e0b155" };
  // Qarz qaytarish o'z yo'nalishining rangida: men qaytargan pul — men
  // olgan qarz rangida, menga qaytarilgani — men bergan qarz rangida.
  STATUS.qarz_qaytardim = STATUS.qarz_oldim;
  STATUS.qarz_qaytdi = STATUS.qarz_berdim;

  const CATEGORY_PALETTE = SCHEME === "light"
    ? ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
    : ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];

  const MAX_CATEGORY_SLICES = 8;

  // ----------------------------------------------------------------------- //
  // Holat
  // ----------------------------------------------------------------------- //

  // «Hammasi» — tur va valyuta filtrlaridagi «filtrlamaslik» tanlovi.
  // Serverda ham shu nom bilan tanilgan (config.CURRENCY_ALL).
  const ALL = "hammasi";

  const state = {
    period: "oy",
    ref: todayIso(),
    kind: ALL,
    currency: "som",
    currencies: ["som"],
    // Foydalanuvchi valyutani o'zi tanlaganmi. Tanlamagan bo'lsa —
    // birlashtirilgan «Hammasi» ko'rinishi standart bo'ladi.
    currencyPicked: false,
    summary: null,
    debts: null,
    recentOffset: 0,
    recentLimit: 20,
    me: null,
    detailTx: null,
  };

  /** Date -> "YYYY-MM-DD" MAHALLIY vaqt bo'yicha.
   * toISOString() ishlatib bo'lmaydi: u UTC'ga o'giradi va musbat mintaqada
   * (masalan Toshkent UTC+5) oyning 1-kuni oldingi oyga tushib qoladi. */
  function isoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function todayIso() {
    return isoLocal(new Date());
  }

  // ----------------------------------------------------------------------- //
  // API
  // ----------------------------------------------------------------------- //

  async function api(path, opts) {
    const options = Object.assign({ headers: {} }, opts || {});
    options.headers = Object.assign({ "X-Telegram-Init-Data": INIT_DATA }, options.headers || {});
    if (options.body && typeof options.body !== "string") {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
    const res = await fetch(path, options);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      // 402 — Bepul daraja chegarasi: {paywall, message}.
      if (detail && typeof detail === "object") {
        const err = new Error(detail.message || "PRO imkoniyati");
        err.paywall = detail.paywall;
        throw err;
      }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // ----------------------------------------------------------------------- //
  // Formatlash
  // ----------------------------------------------------------------------- //

  function fmtMoney(value, currency) {
    const symbols = (state.me && state.me.currency_symbols) || { som: "so'm", usd: "$" };
    // «hammasi» — barcha valyuta asosiy valyutaga o'girilgan holat.
    if (currency === "usd") {
      const v = Math.round(value * 100) / 100;
      let text = Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
      return "$" + groupThousands(text);
    }
    const rounded = Math.round(value);
    return groupThousands(String(rounded)) + " " + (symbols.som || "so'm");
  }

  /** Donut markazi uchun: son va birlik alohida qaytariladi. Bitta qatorga
   * sig'magan uzun summa tasodifan bo'linib ketmasin — birlik ataylab
   * pastda, kichikroq shriftda turadi. */
  function fmtMoneyParts(value, currency) {
    const symbols = (state.me && state.me.currency_symbols) || { som: "so'm", usd: "$" };
    if (currency === "usd") {
      const v = Math.round(value * 100) / 100;
      const text = Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
      return { num: groupThousands(text), unit: "$" };
    }
    return { num: groupThousands(String(Math.round(value))), unit: symbols.som || "so'm" };
  }

  function groupThousands(numStr) {
    const neg = numStr.startsWith("-");
    if (neg) numStr = numStr.slice(1);
    const [intPart, frac] = numStr.split(".");
    const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return (neg ? "-" : "") + grouped + (frac ? "." + frac : "");
  }

  function catIcon(name) {
    return (state.me && state.me.category_icons && state.me.category_icons[name]) || "•";
  }

  function kindIcon(kind) {
    return (state.me && state.me.kind_icons && state.me.kind_icons[kind]) || "•";
  }

  /** Kategoriyaning ko'rinadigan nomi (masalan «oylik» -> «ish haqi»).
   * Bazada va so'rovlarda asl nom qoladi — faqat ekranda o'zgaradi. */
  function catLabel(cat) {
    return (state.me && state.me.category_labels && state.me.category_labels[cat]) || cat;
  }

  function kindLabel(kind) {
    return (state.me && state.me.kind_labels && state.me.kind_labels[kind]) || kind;
  }

  function fmtDate(iso) {
    const MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"];
    const [y, m, d] = iso.split("-").map(Number);
    return `${d}-${MONTHS[m - 1]}`;
  }

  function toast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    // Animatsiya har safar qayta ishga tushishi uchun qayta ulaymiz
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "";
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2400);
  }

  /** Telegram'ning taktil javobi — tugma bosilganini his qilish uchun.
   * Qo'llab-quvvatlanmasa jimgina o'tkazib yuboriladi. */
  function haptic(style) {
    try {
      const h = tg && tg.HapticFeedback;
      if (!h) return;
      if (style === "success" || style === "error" || style === "warning") {
        h.notificationOccurred(style);
      } else {
        h.impactOccurred(style || "light");
      }
    } catch (_) { /* eski Telegram versiyalari */ }
  }

  /** Yuklanayotganda bo'sh matn emas, ro'yxat shakli ko'rsatiladi. */
  function skeleton(rows) {
    return `<div class="skeleton">${'<div class="sk-row"></div>'.repeat(rows || 4)}</div>`;
  }

  /** Foizni o'qishga qulay yozadi. Nolga teng bo'lmagan juda kichik ulush
   * "0%" emas, "<1%" deb ko'rsatiladi — aks holda summa bor-u, foiz nol
   * bo'lib chiqib, ma'lumot noto'g'ri o'qiladi. */
  function fmtPct(share) {
    if (share <= 0) return "0%";
    const pct = share * 100;
    if (pct < 1) return "<1%";
    return `${Math.round(pct)}%`;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  /** Kategoriyalar 8 tadan ko'p bo'lsa, qolganini "Boshqa" ga yig'adi —
   * ranglar palitrasi 8 slotdan iborat, 9-rang hech qachon o'ylab topilmaydi. */
  function foldToOther(rows) {
    if (rows.length <= MAX_CATEGORY_SLICES) return rows;
    const head = rows.slice(0, MAX_CATEGORY_SLICES - 1);
    const rest = rows.slice(MAX_CATEGORY_SLICES - 1);
    const otherSum = rest.reduce((s, r) => s + r.summa, 0);
    const otherCount = rest.reduce((s, r) => s + r.soni, 0);
    head.push({ kategoriya: `Boshqa (${rest.length})`, summa: otherSum, soni: otherCount, _other: true });
    return head;
  }

  // ----------------------------------------------------------------------- //
  // Davr navigatsiyasi
  // ----------------------------------------------------------------------- //

  function shiftRef(period, isoRef, delta) {
    const [y, m, day] = isoRef.split("-").map(Number);
    const d = new Date(y, m - 1, day);
    if (period === "kun") {
      d.setDate(d.getDate() + delta);
    } else if (period === "hafta") {
      d.setDate(d.getDate() + delta * 7);
    } else if (period === "oy") {
      d.setMonth(d.getMonth() + delta, 1);
    } else if (period === "yil") {
      d.setFullYear(d.getFullYear() + delta, d.getMonth(), 1);
    }
    return isoLocal(d);
  }

  // ----------------------------------------------------------------------- //
  // Donut (SVG)
  // ----------------------------------------------------------------------- //

  /** Donut ostidagi yorliq — identifikatsiya HECH QACHON faqat rangga
   * tayanmasligi uchun (yashil/qizil rang ko'rligida deyarli bir xil
   * ko'rinadi). Har bir bo'lak nomi va aniq summasi bilan yoziladi. */
  function renderLegend(items, currency) {
    const el = document.getElementById("donutLegend");
    if (!items || !items.length) { el.innerHTML = ""; return; }
    const total = items.reduce((s, i) => s + i.value, 0);
    el.innerHTML = items.map((i) => {
      const share = total > 0 ? i.value / total : 0;
      return `<div class="legend-item">
        <span class="legend-dot" style="background:${i.color}"></span>
        <span class="legend-name">${escapeHtml(i.label)}</span>
        <span class="legend-value">${fmtMoney(i.value, currency)}</span>
        <span class="legend-pct">${fmtPct(share)}</span>
      </div>`;
    }).join("");
  }

  function renderDonut(segments, centerValue, centerSub) {
    const g = document.getElementById("donutSegments");
    g.innerHTML = "";
    const r = 80, cx = 100, cy = 100, circumference = 2 * Math.PI * r;
    const total = segments.reduce((s, seg) => s + seg.value, 0);

    if (total > 0) {
      // 2px oraliq — qo'shni segmentlar orasida (skill: "surface gap between fills").
      const gapDeg = segments.filter((s) => s.value > 0).length > 1 ? 2 : 0;
      const gapLen = (gapDeg / 360) * circumference;
      let offset = 0;
      segments.forEach((seg) => {
        if (seg.value <= 0) return;
        const share = seg.value / total;
        const len = Math.max(0, share * circumference - gapLen);
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", r);
        circle.setAttribute("stroke", seg.color);
        circle.setAttribute("stroke-dashoffset", -offset);
        // Noldan boshlanadi, keyingi kadrda haqiqiy uzunlikka o'sadi —
        // shunda CSS transition bo'lakni aylanib chizilgandek ko'rsatadi.
        circle.setAttribute("stroke-dasharray", `0 ${circumference}`);
        g.appendChild(circle);
        const finalDash = `${len} ${circumference - len}`;
        requestAnimationFrame(() =>
          requestAnimationFrame(() => circle.setAttribute("stroke-dasharray", finalDash))
        );
        offset += share * circumference;
      });
    }

    const valEl = document.getElementById("donutValue");
    if (centerValue && typeof centerValue === "object") {
      valEl.innerHTML =
        `<span class="donut-num">${escapeHtml(centerValue.num)}</span>` +
        `<span class="donut-unit">${escapeHtml(centerValue.unit)}</span>`;
    } else {
      valEl.textContent = centerValue;
    }
    document.getElementById("donutSub").textContent = centerSub;
  }

  function renderCategorySection(title, rows, total, currency, kindForClick) {
    const folded = foldToOther(rows);
    let html = `<div class="section-label">${escapeHtml(title)}</div>`;
    if (!folded.length) {
      return html + '<div class="empty-state">Yozuv yo\'q.</div>';
    }
    folded.forEach((row, i) => {
      const share = total > 0 ? row.summa / total : 0;
      const color = CATEGORY_PALETTE[i % CATEGORY_PALETTE.length];
      html += `
        <div class="cat-row" ${row._other ? "" : `data-cat-click="1" data-kind="${kindForClick}" data-category="${escapeHtml(row.kategoriya)}"`}>
          <div class="cat-icon" style="background:${color}22">${row._other ? "…" : catIcon(row.kategoriya)}</div>
          <div class="cat-info">
            <div class="cat-name-row">
              <span class="cat-name">${escapeHtml(catLabel(row.kategoriya))}</span>
              <span class="cat-amount">${fmtMoney(row.summa, currency)}</span>
            </div>
            <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${(share * 100).toFixed(0)}%;background:${color}"></div></div>
          </div>
          <div class="cat-share">${fmtPct(share)}</div>
        </div>`;
    });
    return html;
  }

  function renderPersonSection(title, items, currency, color, kind) {
    let html = `<div class="section-label">${escapeHtml(title)}</div>`;
    if (!items.length) {
      return html + '<div class="empty-state">Yo\'q.</div>';
    }
    const total = items.reduce((s, i) => s + i.amount, 0);
    items.forEach((item) => {
      const share = total > 0 ? item.amount / total : 0;
      html += `
        <div class="cat-row" data-debt-id="${item.id}" data-kind="${kind}">
          <div class="cat-icon" style="background:${color}22">${kind === "qarz_berdim" ? "📤" : "📥"}</div>
          <div class="cat-info">
            <div class="cat-name-row">
              <span class="cat-name">${escapeHtml(item.person)}</span>
              <span class="cat-amount">${fmtMoney(item.amount, currency)}</span>
            </div>
            ${item.original && item.original > item.amount
              ? `<div class="tx-meta">qoldiq · asli ${fmtMoney(item.original, currency)}</div>` : ""}
            <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${(share * 100).toFixed(0)}%;background:${color}"></div></div>
          </div>
          <button class="cat-settle" data-settle-id="${item.id}">Yopish</button>
        </div>`;
    });
    return html;
  }

  // ----------------------------------------------------------------------- //
  // Yuklash
  // ----------------------------------------------------------------------- //

  async function loadMe() {
    state.me = await api("/api/me");
  }

  /** PRO imkoniyatga urilganda: Telegram'ning o'z oynasi va «PRO ga
   * o'tish» — bot tariflar sahifasini ochadi (/start pro). */
  function showPaywall(message) {
    haptic("warning");
    const bot = state.me && state.me.bot_username;
    const go = () => {
      if (bot && tg && tg.openTelegramLink) tg.openTelegramLink(`https://t.me/${bot}?start=pro`);
      else toast("Botda /obuna buyrug'ini bosing");
    };
    const text = message.length > 250 ? message.slice(0, 247) + "…" : message;
    if (tg && tg.showPopup) {
      tg.showPopup({
        title: "💎 Tanga PRO",
        message: text,
        buttons: [{ id: "pro", type: "default", text: "💎 PRO ga o'tish" }, { type: "close" }],
      }, (id) => { if (id === "pro") go(); });
    } else if (confirm(text + "\n\nPRO ga o'tasizmi?")) {
      go();
    }
  }

  async function loadSummary() {
    let data;
    try {
      data = await api(`/api/summary?period=${state.period}&ref=${state.ref}`);
    } catch (e) {
      if (!e.paywall || !state.lastGood) throw e;
      // Bepul darajada joriy oydan oldingi davr — oxirgi ko'ringan davrga
      // qaytamiz va PRO taklifini ko'rsatamiz.
      state.period = state.lastGood.period;
      state.ref = state.lastGood.ref;
      document.querySelectorAll("#periodTabs button").forEach((b) =>
        b.classList.toggle("active", b.dataset.period === state.period));
      showPaywall(e.message);
      return;
    }
    state.lastGood = { period: state.period, ref: state.ref };
    state.summary = data;
    document.getElementById("rangeLabel").textContent = data.label;

    state.currencies = data.currencies.length ? data.currencies : ["som"];
    if (!state.currencyPicked || !state.currencies.includes(state.currency)) {
      state.currency = state.currencies[0];
    }
    renderCurrencyToggle();

    renderCurrentKind();
    state.recentOffset = 0;
    loadRecent(false);
  }

  async function loadDebts() {
    state.debts = await api("/api/debts");
    if (state.kind === "qarz") { renderCurrentKind(); loadRecent(false); }
  }

  async function loadSavings() {
    // Xato bo'lsa jim o'tamiz: jamg'arma holati qo'shimcha ma'lumot,
    // uning yo'qligi butun ekranni yiqitmasligi kerak.
    try {
      state.savings = await api("/api/savings");
    } catch (e) {
      state.savings = null;
      return;
    }
    if (state.kind === "jamgarma") renderCurrentKind();
  }

  function renderCurrencyToggle() {
    const el = document.getElementById("currencyToggle");
    el.innerHTML = "";
    if (state.currencies.length <= 1) return;
    const symbols = state.me.currency_symbols;
    state.currencies.forEach((cur) => {
      const btn = document.createElement("button");
      // «hammasi» — valyutalar asosiy valyutada birlashtirilgan ko'rinish.
      btn.textContent = cur === ALL ? "Hammasi" : (symbols[cur] || cur.toUpperCase());
      if (cur === state.currency) btn.classList.add("active");
      btn.onclick = () => {
        state.currency = cur;
        state.currencyPicked = true;
        renderCurrencyToggle();
        renderCurrentKind();
        loadRecent(false);
      };
      el.appendChild(btn);
    });
  }

  function renderCurrentKind() {
    const cur = state.currency;

    if (state.kind === "qarz") {
      renderQarzKind();
      return;
    }
    if (state.kind === "jamgarma") {
      renderJamgarmaKind();
      return;
    }

    const data = state.summary && state.summary.by_currency[cur];
    const listEl = document.getElementById("categoryList");

    if (!data) {
      renderDonut([], fmtMoneyParts(0, cur), "");
      renderLegend([], cur);
      listEl.innerHTML = '<div class="empty-state">Bu davrda yozuv yo\'q.</div>';
      return;
    }

    if (state.kind === ALL) {
      renderDonut(
        [
          { value: data.kirim, color: STATUS.kirim },
          { value: data.chiqim, color: STATUS.chiqim },
        ],
        fmtMoneyParts(data.farq, cur),
        "Farq"
      );
      // Jamg'arma halqaga QO'SHILMAYDI: halqa kirim/chiqim nisbatini
      // ko'rsatadi, jamg'arma esa sarflangan pul emas. Lekin yorliqda
      // turadi — «avval o'zingga to'la» qoidasi ko'zga tashlansin.
      renderLegend([
        { label: "Kirim", value: data.kirim, color: STATUS.kirim },
        { label: "Chiqim", value: data.chiqim, color: STATUS.chiqim },
        ...(data.jamgarma
          ? [{ label: "🏦 Jamg'arma", value: data.jamgarma, color: STATUS.jamgarma }]
          : []),
      ], cur);
      listEl.innerHTML =
        renderCategorySection("Kirim kategoriyalari", data.kirim_kategoriyalari, data.kirim, cur, "kirim") +
        renderCategorySection("Chiqim kategoriyalari", data.chiqim_kategoriyalari, data.chiqim, cur, "chiqim");
    } else if (state.kind === "kirim") {
      const folded = foldToOther(data.kirim_kategoriyalari);
      renderDonut(
        folded.map((c, i) => ({ value: c.summa, color: CATEGORY_PALETTE[i % CATEGORY_PALETTE.length] })),
        fmtMoneyParts(data.kirim, cur), "Kirim"
      );
      // Kategoriya bo'laklari pastdagi ro'yxatda nomi bilan berilgan —
      // takrorlamaymiz, faqat 2 bo'lakli ko'rinishlarda yorliq kerak.
      renderLegend([], cur);
      listEl.innerHTML = renderCategorySection("Kategoriyalar", data.kirim_kategoriyalari, data.kirim, cur, "kirim");
    } else if (state.kind === "chiqim") {
      const folded = foldToOther(data.chiqim_kategoriyalari);
      renderDonut(
        folded.map((c, i) => ({ value: c.summa, color: CATEGORY_PALETTE[i % CATEGORY_PALETTE.length] })),
        fmtMoneyParts(data.chiqim, cur), "Chiqim"
      );
      renderLegend([], cur);
      listEl.innerHTML = renderCategorySection("Kategoriyalar", data.chiqim_kategoriyalari, data.chiqim, cur, "chiqim");
    }

    bindCategoryClicks();
  }

  function renderQarzKind() {
    const listEl = document.getElementById("categoryList");
    if (!state.debts) { renderDonut([], "…", ""); renderLegend([], "som"); listEl.innerHTML = ""; return; }
    const cur = state.currency;
    const berdim = (state.debts.qarz_berdim.totals[cur]) || 0;
    const oldim = (state.debts.qarz_oldim.totals[cur]) || 0;
    renderDonut(
      [
        { value: berdim, color: STATUS.qarz_berdim },
        { value: oldim, color: STATUS.qarz_oldim },
      ],
      fmtMoneyParts(berdim - oldim, cur),
      "Sof qarz"
    );
    renderLegend([
      { label: "📤 Menga qarzdorlar", value: berdim, color: STATUS.qarz_berdim },
      { label: "📥 Men qarzdorman", value: oldim, color: STATUS.qarz_oldim },
    ], cur);
    const berdimItems = state.debts.qarz_berdim.items[cur] || [];
    const oldimItems = state.debts.qarz_oldim.items[cur] || [];
    // Shu davrda qaytarilgan pul — chiqim ham, kirim ham emas, shuning
    // uchun faqat shu yerda ko'rinadi.
    const period = state.summary && state.summary.by_currency[cur];
    const repaid = period
      ? [["↩️ Qarzimni qaytardim", period.qarz_qaytardim],
         ["↪️ Menga qaytarildi", period.qarz_qaytdi]].filter((r) => r[1])
      : [];
    const repaidHtml = repaid.length
      ? `<div class="section-label">Shu davrda qaytarilgan</div>` +
        repaid.map(([label, value]) => `
          <div class="cat-row">
            <div class="cat-info"><div class="cat-name-row">
              <span class="cat-name">${escapeHtml(label)}</span>
              <span class="cat-amount">${fmtMoney(value, cur)}</span>
            </div></div>
          </div>`).join("")
      : "";
    listEl.innerHTML =
      renderPersonSection("📤 Menga qarzdorlar", berdimItems, cur, STATUS.qarz_berdim, "qarz_berdim") +
      renderPersonSection("📥 Men qarzdorman", oldimItems, cur, STATUS.qarz_oldim, "qarz_oldim") +
      repaidHtml;
    bindSettleButtons();
  }

  /**
   * «Jamg'arma» yorlig'i: qo'yilgan va yechilgan pul, o'rtasida sof
   * qiymat. Halqa markazida shu davrda jamg'armaga QANCHA QO'SHILGANI
   * turadi — umumiy qoldiq emas: yorliq davr (kun/hafta/oy/yil)
   * bo'yicha ishlaydi va boshqa yorliqlar bilan bir xil mantiqda
   * bo'lishi kerak.
   */
  function renderJamgarmaKind() {
    const cur = state.currency;
    const listEl = document.getElementById("categoryList");
    const data = state.summary && state.summary.by_currency[cur];

    if (!data) { renderDonut([], "…", ""); renderLegend([], cur); listEl.innerHTML = ""; return; }

    const qoygan = data.jamgarma_qoygan || 0;
    const yechgan = data.jamgarma_yechgan || 0;

    if (!qoygan && !yechgan) {
      renderDonut([], fmtMoneyParts(0, cur), "Jamg'arma");
      renderLegend([], cur);
    } else {
      renderDonut(
        [
          { value: qoygan, color: STATUS.jamgarma },
          { value: yechgan, color: STATUS.jamgarma_yechdim },
        ],
        fmtMoneyParts(qoygan - yechgan, cur),
        "Sof jamg'arma"
      );
      renderLegend([
        { label: "🏦 Qo'yilgan", value: qoygan, color: STATUS.jamgarma },
        { label: "🏧 Yechilgan", value: yechgan, color: STATUS.jamgarma_yechdim },
      ], cur);
    }

    listEl.innerHTML = renderSavingsBlock(qoygan || yechgan);
  }

  /**
   * Umumiy qoldiq va maqsad. Halqa TANLANGAN DAVRni ko'rsatadi
   * («avgustda qancha qo'shildi»), bu blok esa umumiy holatni —
   * ikkalasi har xil savolga javob beradi va aralashtirilsa
   * chalkashlik chiqadi.
   */
  /** 0.1 -> "10%", 0.125 -> "12.5%". Foiz har kimda o'zi bo'ladi. */
  function pctText(rate) {
    const v = (rate || 0.1) * 100;
    return (Math.abs(v - Math.round(v)) < 0.05 ? v.toFixed(0) : v.toFixed(1)) + "%";
  }

  function renderSavingsBlock(hadMovement) {
    const s = state.savings;
    if (!s) return "";

    let html = '<div class="section-label">Jamg\'arma holati</div>';
    html += `
      <div class="cat-row">
        <div class="cat-icon" style="background:${STATUS.jamgarma}22">🏦</div>
        <div class="cat-info">
          <div class="cat-name-row">
            <span class="cat-name">Umumiy qoldiq</span>
            <span class="cat-amount">${fmtMoney(s.balance, "som")}</span>
          </div>
        </div>
      </div>`;

    if (s.goal > 0) {
      const pct = s.percent || 0;
      const note = s.goal_note ? ` — ${escapeHtml(s.goal_note)}` : "";
      html += `
        <div class="cat-row">
          <div class="cat-icon" style="background:${STATUS.jamgarma}22">🎯</div>
          <div class="cat-info">
            <div class="cat-name-row">
              <span class="cat-name">Maqsad${note}</span>
              <span class="cat-amount">${fmtMoney(s.goal, "som")}</span>
            </div>
            <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${pct.toFixed(0)}%;background:${STATUS.jamgarma}"></div></div>
          </div>
          <div class="cat-share">${pct.toFixed(0)}%</div>
        </div>`;
      html += s.left > 0
        ? `<div class="hint-row">Yetishga <b>${fmtMoney(s.left, "som")}</b> qoldi</div>`
        : '<div class="hint-row">🎉 Maqsadga yetdingiz!</div>';
    } else {
      html += '<div class="hint-row">Maqsad qo\'yilmagan. Botda: '
            + '<b>/maqsad 10 mln</b></div>';
      html += `<div class="hint-row">Jamg'arma foizingiz: `
            + `<b>${pctText(s.rate)}</b>. O'zgartirish: <b>/foiz 15</b></div>`;
    }

    if (s.streak >= 2) {
      html += `<div class="hint-row">🔥 Ketma-ket <b>${s.streak} oy</b> `
            + `${pctText(s.rate)} qoidasini bajaryapsiz</div>`;
    }
    if (!hadMovement) {
      html += '<div class="hint-row">Bu davrda harakat yo\'q. Qo\'shish: '
            + '<b>jamg\'armaga 500 ming o\'tkazdim</b></div>';
    }
    return html;
  }

  function bindCategoryClicks() {
    const listEl = document.getElementById("categoryList");
    listEl.querySelectorAll("[data-cat-click]").forEach((el) => {
      el.onclick = () => {
        openFilteredList(el.dataset.kind, el.dataset.category);
      };
    });
  }

  function bindSettleButtons() {
    const listEl = document.getElementById("categoryList");
    listEl.querySelectorAll("[data-settle-id]").forEach((btn) => {
      btn.onclick = (ev) => {
        ev.stopPropagation();
        confirmAction("Bu qarzni yopilgan deb belgilaysizmi?", () => settleDebt(btn.dataset.settleId));
      };
    });
  }

  async function loadRecent(append) {
    const listEl = document.getElementById("recentList");
    if (!append) {
      listEl.innerHTML = skeleton(4);
      setListTitle("", false);  // filtr yorlig'i eski holatda qolib ketmasin
    }

    if (state.kind === "qarz") {
      document.getElementById("loadMore").classList.add("hidden");
      if (!state.debts) return;
      const cur = state.currency;
      const items = [
        ...((state.debts.qarz_berdim.items[cur] || []).map((i) => ({ ...i, kind: "qarz_berdim" }))),
        ...((state.debts.qarz_oldim.items[cur] || []).map((i) => ({ ...i, kind: "qarz_oldim" }))),
      ].sort((a, b) => (a.date < b.date ? 1 : -1));
      listEl.innerHTML = "";
      if (!items.length) { listEl.innerHTML = '<div class="empty-state">Ochiq qarz yo\'q.</div>'; return; }
      items.forEach((it) => listEl.appendChild(buildDebtRow(it, cur)));
      return;
    }

    const params = new URLSearchParams({
      start: state.summary.start, end: state.summary.end,
      limit: state.recentLimit, offset: state.recentOffset,
    });
    // «hammasi» — valyuta filtri yo'q degani, uni serverga yubormaymiz.
    if (state.currency !== ALL) params.set("currency", state.currency);
    // «Jamg'arma» yorlig'i ikkita turni qamraydi — server vergul bilan
    // berilgan ro'yxatni qabul qiladi.
    if (state.kind === "jamgarma") {
      params.set("kind", "jamgarma,jamgarma_yechdim");
    } else if (state.kind !== ALL) {
      params.set("kind", state.kind);
    }

    let data;
    try {
      data = await api(`/api/transactions?${params.toString()}`);
    } catch (e) {
      // Skeleton abadiy qolib ketmasin — xatoni ko'rsatib, qayta urinish beramiz.
      showListError(listEl, e, () => loadRecent(append));
      return;
    }
    if (!append) listEl.innerHTML = "";
    if (!data.items.length && !append) {
      listEl.innerHTML = '<div class="empty-state">Yozuv yo\'q.</div>';
    }
    data.items.forEach((tx) => listEl.appendChild(buildTxRow(tx)));

    const shown = state.recentOffset + data.items.length;
    document.getElementById("loadMore").classList.toggle("hidden", shown >= data.total_count);
  }

  /** Ro'yxat yuklanmaganda xatoni ko'rsatadi va qayta urinish tugmasini beradi. */
  function showListError(listEl, err, retry) {
    document.getElementById("loadMore").classList.add("hidden");
    listEl.innerHTML =
      `<div class="empty-state">Ro'yxatni yuklab bo'lmadi.<br>` +
      `<small>${escapeHtml(err.message || "Nomaʼlum xatolik")}</small><br>` +
      `<button class="clear-filter" id="retryList">Qayta urinish</button></div>`;
    listEl.querySelector("#retryList").onclick = retry;
  }

  /** Kategoriya ustiga bosilganda — shu kategoriyadagi yozuvlarni pastdagi
   * "So'nggi yozuvlar" ro'yxatiga filtrlab ko'rsatadi. */
  async function openFilteredList(kind, category) {
    const listEl = document.getElementById("recentList");
    listEl.innerHTML = skeleton(3);
    const params = new URLSearchParams({
      start: state.summary.start, end: state.summary.end,
      kind, search: category, limit: 100,
    });
    if (state.currency !== ALL) params.set("currency", state.currency);

    let data;
    try {
      data = await api(`/api/transactions?${params.toString()}`);
    } catch (e) {
      showListError(listEl, e, () => openFilteredList(kind, category));
      return;
    }
    const filtered = data.items.filter((t) => t.category === category);

    // Filtr qo'llanganini ko'rsatuvchi yorliq + uni bekor qilish tugmasi.
    setListTitle(`${catIcon(category)} ${category}`, true);

    listEl.innerHTML = "";
    if (!filtered.length) { listEl.innerHTML = '<div class="empty-state">Yozuv yo\'q.</div>'; return; }
    filtered.forEach((tx) => listEl.appendChild(buildTxRow(tx)));
    document.getElementById("loadMore").classList.add("hidden");
    document.getElementById("listTitle").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /** Ro'yxat sarlavhasini o'zgartiradi; filtr faol bo'lsa "✕ tozalash" tugmasi bilan. */
  function setListTitle(text, filtered) {
    const el = document.getElementById("listTitle");
    if (!filtered) {
      el.innerHTML = "So'nggi yozuvlar";
      return;
    }
    el.innerHTML = `Filtr: ${escapeHtml(text)} <button class="clear-filter" id="clearFilter">✕ tozalash</button>`;
    el.querySelector("#clearFilter").onclick = () => {
      setListTitle("", false);
      state.recentOffset = 0;
      loadRecent(false);
    };
  }

  function buildTxRow(tx) {
    const div = document.createElement("div");
    div.className = "tx-row";
    const icon = tx.kind.startsWith("qarz") ? "🤝" : catIcon(tx.category);
    div.innerHTML = `
      <div class="tx-icon">${icon}</div>
      <div class="tx-main">
        <div class="tx-note">${escapeHtml(tx.note || catLabel(tx.category))}${tx.person ? " — " + escapeHtml(tx.person) : ""}${tx.settled ? " ✅" : ""}</div>
        <div class="tx-meta">${fmtDate(tx.date)} · ${escapeHtml(catLabel(tx.category))}${tx.receipt_id ? " · 🧾" : ""}</div>
      </div>
      <div class="tx-amount ${tx.kind}">${kindIcon(tx.kind)} ${fmtMoney(tx.amount, tx.currency)}</div>
    `;
    div.onclick = () => openDetailSheet(tx);
    return div;
  }

  function buildDebtRow(item, currency) {
    const div = document.createElement("div");
    div.className = "tx-row";
    div.innerHTML = `
      <div class="tx-icon">${item.kind === "qarz_berdim" ? "📤" : "📥"}</div>
      <div class="tx-main">
        <div class="tx-note">${escapeHtml(item.person)}</div>
        <div class="tx-meta">${fmtDate(item.date)}${item.note ? " · " + escapeHtml(item.note) : ""}</div>
      </div>
      <div class="tx-amount ${item.kind}">${fmtMoney(item.amount, currency)}</div>
    `;
    div.onclick = () => openDetailSheet({
      id: item.id, kind: item.kind, amount: item.amount, currency,
      category: "qarz", note: item.note, person: item.person, date: item.date,
      receipt_id: null, settled: false,
    });
    return div;
  }

  // ----------------------------------------------------------------------- //
  // Tasdiqlash (Telegram'ning o'ziga xos dialogi, bo'lmasa oddiy confirm)
  // ----------------------------------------------------------------------- //

  function confirmAction(message, onYes) {
    if (tg && tg.showConfirm) {
      tg.showConfirm(message, (ok) => { if (ok) onYes(); });
    } else if (confirm(message)) {
      onYes();
    }
  }

  // ----------------------------------------------------------------------- //
  // Yozuv tafsiloti / tahrirlash paneli
  // ----------------------------------------------------------------------- //

  /** Panel pastdan sirg'alib chiqadi. .hidden (display:none) olib tashlangach
   * keyingi kadrda .open qo'shiladi — aks holda brauzer o'tishni animatsiya
   * qilmaydi (bir kadrda ikkala holat qo'llansa transition ishlamaydi). */
  function openSheet(id) {
    const el = document.getElementById(id);
    el.classList.remove("hidden");
    requestAnimationFrame(() => el.classList.add("open"));
    haptic("light");
  }

  function closeSheet(id) {
    const el = document.getElementById(id);
    el.classList.remove("open");
    clearTimeout(el._closeTimer);
    el._closeTimer = setTimeout(() => el.classList.add("hidden"), 260);
  }

  function openDetailSheet(tx) {
    state.detailTx = tx;
    const isDebt = tx.kind.startsWith("qarz");
    // Qaysi turga almashtirish mumkinligi serverdan keladi
    // (config.KIND_SWITCHES): kirim <-> chiqim va ular <-> qarz qaytarish.
    const switches = (state.me.kind_switches && state.me.kind_switches[tx.kind]) || [];
    const canSettle = tx.kind === "qarz_berdim" || tx.kind === "qarz_oldim";
    const cats = (state.me.categories_by_kind[tx.kind] || []);

    let html = `
      <div class="sheet-titlebar">
        <div class="tx-detail-header">
          <span style="font-size:22px">${kindIcon(tx.kind)}</span>
          <span class="tx-detail-amount" style="color:${isDebt ? "var(--text)" : (tx.kind === "kirim" ? "var(--good)" : "var(--critical)")}">
            ${fmtMoney(tx.amount, tx.currency)}
          </span>
        </div>
        <button class="icon-btn" id="detailClose" aria-label="Yopish">✕</button>
      </div>
      <div class="tx-detail-meta">
        ${escapeHtml(kindLabel(tx.kind))} · ${fmtDate(tx.date)}
        ${tx.person ? " · " + escapeHtml(tx.person) : ""}
        ${tx.note ? "<br>" + escapeHtml(tx.note) : ""}
      </div>
    `;

    if (!isDebt) {
      html += `<div class="sheet-row">
        <div class="sheet-label">Kategoriya</div>
        <div class="chip-grid" id="catChips">
          ${cats.map((c) => `<button class="chip ${c === tx.category ? "active" : ""}" data-cat="${escapeHtml(c)}">${catIcon(c)} ${escapeHtml(catLabel(c))}</button>`).join("")}
        </div>
      </div>`;
    }

    switches.forEach((other) => {
      html += `<button class="btn btn-secondary" data-switch-kind="${escapeHtml(other)}" style="width:100%;margin-bottom:10px">
        🔄 ${kindIcon(other)} ${escapeHtml(kindLabel(other))} deb belgilash
      </button>`;
    });

    if (tx.receipt_id) {
      html += `<div id="receiptItems" class="sheet-row"><div class="sheet-label">🧾 Shu chekdagi boshqa mahsulotlar</div><div class="spinner">Yuklanmoqda…</div></div>`;
    }

    html += `<div class="sheet-actions">
      ${canSettle && !tx.settled ? '<button class="btn btn-good" id="settleBtn">✅ Yopish</button>' : ""}
      <button class="btn btn-danger" id="deleteBtn">🗑 O'chirish</button>
    </div>`;

    const body = document.getElementById("detailBody");
    body.innerHTML = html;
    openSheet("detailBackdrop");

    // Selektorlar faqat shu panel ichida — sahifadagi bir xil atributli
    // boshqa elementlarga tegmasligi uchun.
    body.querySelectorAll("#catChips .chip").forEach((chip) => {
      chip.onclick = () => updateTxCategory(tx.id, chip.dataset.cat);
    });
    body.querySelectorAll("[data-switch-kind]").forEach((btn) => {
      btn.onclick = () => toggleTxKind(tx.id, btn.dataset.switchKind);
    });
    const settleBtn = body.querySelector("#settleBtn");
    if (settleBtn) settleBtn.onclick = () => confirmAction("Bu qarzni yopilgan deb belgilaysizmi?", () => settleDebt(tx.id));
    body.querySelector("#deleteBtn").onclick = () =>
      confirmAction("Bu yozuvni o'chirasizmi?", () => deleteTx(tx.id));
    body.querySelector("#detailClose").onclick = () => closeSheet("detailBackdrop");

    if (tx.receipt_id) loadReceiptItems(tx.receipt_id, tx.id);
  }

  async function loadReceiptItems(receiptId, excludeId) {
    try {
      const data = await api(`/api/transactions?receipt_id=${encodeURIComponent(receiptId)}&limit=100`);
      const others = data.items.filter((i) => i.id !== excludeId);
      const el = document.getElementById("receiptItems");
      if (!el) return;
      if (!others.length) {
        el.querySelector(".spinner")?.remove();
        return;
      }
      const list = others.map((i) =>
        `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;color:var(--hint)">
          <span>${catIcon(i.category)} ${escapeHtml(i.note || i.category)}</span>
          <span>${fmtMoney(i.amount, i.currency)}</span>
        </div>`
      ).join("");
      el.innerHTML = `<div class="sheet-label">🧾 Shu chekdagi boshqa mahsulotlar (${others.length})</div>${list}`;
    } catch (_) { /* jim tur — asosiy funksionallik emas */ }
  }

  async function updateTxCategory(id, category) {
    try {
      await api(`/api/transactions/${id}`, { method: "PATCH", body: { category } });
      haptic("success"); toast("Kategoriya yangilandi");
      closeSheet("detailBackdrop");
      refreshAll();
    } catch (e) { haptic("error"); toast("Xatolik: " + e.message); }
  }

  async function toggleTxKind(id, newKind) {
    try {
      await api(`/api/transactions/${id}`, { method: "PATCH", body: { kind: newKind } });
      haptic("success"); toast("Turi yangilandi");
      closeSheet("detailBackdrop");
      refreshAll();
    } catch (e) { haptic("error"); toast("Xatolik: " + e.message); }
  }

  async function settleDebt(id) {
    try {
      await api(`/api/debts/${id}/settle`, { method: "POST" });
      haptic("success"); toast("Qarz yopildi ✅");
      closeSheet("detailBackdrop");
      await loadDebts();
      refreshAll();
    } catch (e) { haptic("error"); toast("Xatolik: " + e.message); }
  }

  async function deleteTx(id) {
    try {
      await api(`/api/transactions/${id}`, { method: "DELETE" });
      haptic("success"); toast("O'chirildi");
      closeSheet("detailBackdrop");
      refreshAll();
    } catch (e) { haptic("error"); toast("Xatolik: " + e.message); }
  }

  function refreshAll() {
    loadSummary();
    loadDebts();
    loadSavings();
    if (!document.getElementById("searchPanel").classList.contains("hidden")) runSearch();
  }

  // ----------------------------------------------------------------------- //
  // Yangi yozuv qo'shish
  // ----------------------------------------------------------------------- //

  const addForm = {
    kind: "chiqim", currency: "som", category: "", date: todayIso(),
    amount: "", note: "", person: "",
  };

  function openAddSheet() {
    addForm.kind = "chiqim";
    addForm.currency = state.currencies[0] || "som";
    addForm.category = (state.me.categories_by_kind.chiqim || [])[0] || "";
    addForm.date = todayIso();
    addForm.amount = "";
    addForm.note = "";
    addForm.person = "";
    renderAddForm();
    openSheet("addBackdrop");
  }

  /** Chip bosilganda forma qayta chiziladi — shundan oldin foydalanuvchi
   * hali saqlab ulgurmagan matn/son maydonlarini yo'qotmaslik uchun
   * joriy qiymatlarni addForm'ga o'qib olamiz. */
  function captureFormValues() {
    const amountEl = document.getElementById("fAmount");
    const noteEl = document.getElementById("fNote");
    const personEl = document.getElementById("fPerson");
    const dateEl = document.getElementById("fDate");
    if (amountEl) addForm.amount = amountEl.value;
    if (noteEl) addForm.note = noteEl.value;
    if (personEl) addForm.person = personEl.value;
    if (dateEl) addForm.date = dateEl.value;
  }

  function renderAddForm() {
    const isDebt = addForm.kind.startsWith("qarz");
    const cats = state.me.categories_by_kind[addForm.kind] || [];
    if (!cats.includes(addForm.category)) addForm.category = cats[0] || "";

    const html = `
      <div class="sheet-titlebar">
        <h2>➕ Yangi yozuv</h2>
        <button class="icon-btn" id="addClose" aria-label="Yopish">✕</button>
      </div>

      <div class="sheet-row">
        <div class="sheet-label">Turi</div>
        <div class="chip-grid">
          ${["chiqim", "kirim", "qarz_berdim", "qarz_oldim",
             "qarz_qaytardim", "qarz_qaytdi",
             "jamgarma", "jamgarma_yechdim"].map((k) =>
            `<button class="chip ${k === addForm.kind ? "active" : ""}" data-kind="${k}">${kindIcon(k)} ${escapeHtml(kindLabel(k))}</button>`
          ).join("")}
        </div>
      </div>

      <div class="sheet-row">
        <div class="sheet-label">Summa</div>
        <input id="fAmount" class="field-input" type="number" inputmode="decimal" placeholder="0" value="${escapeHtml(addForm.amount)}" />
      </div>

      <div class="sheet-row">
        <div class="sheet-label">Valyuta</div>
        <div class="chip-grid">
          ${(state.me.currency_symbols ? Object.keys(state.me.currency_symbols) : ["som", "usd"]).map((c) =>
            `<button class="chip ${c === addForm.currency ? "active" : ""}" data-currency="${c}">${state.me.currency_symbols[c]}</button>`
          ).join("")}
        </div>
      </div>

      ${!isDebt ? `
      <div class="sheet-row">
        <div class="sheet-label">Kategoriya</div>
        <div class="chip-grid">
          ${cats.map((c) => `<button class="chip ${c === addForm.category ? "active" : ""}" data-cat="${escapeHtml(c)}">${catIcon(c)} ${escapeHtml(catLabel(c))}</button>`).join("")}
        </div>
      </div>` : ""}

      ${isDebt ? `
      <div class="sheet-row">
        <div class="sheet-label">Kim bilan (ism)</div>
        <input id="fPerson" class="field-input" type="text" placeholder="Masalan: Ali" value="${escapeHtml(addForm.person)}" />
      </div>` : ""}

      <div class="sheet-row">
        <div class="sheet-label">Izoh</div>
        <input id="fNote" class="field-input" type="text" placeholder="Ixtiyoriy" value="${escapeHtml(addForm.note)}" />
      </div>

      <div class="sheet-row">
        <div class="sheet-label">Sana</div>
        <input id="fDate" class="field-input" type="date" value="${addForm.date}" />
      </div>

      <div class="sheet-actions">
        <button class="btn btn-secondary" id="addCancel">Bekor qilish</button>
        <button class="btn btn-primary" id="addSave">Saqlash</button>
      </div>
    `;
    const body = document.getElementById("addBody");
    body.innerHTML = html;

    // MUHIM: selektorlar FAQAT shu panel ichida qidirilishi kerak.
    // Aks holda dashboard'dagi bir xil atributli elementlar (tur tablari
    // data-kind, kategoriya qatorlari data-kind) ham qayta bog'lanib,
    // ishlamay qoladi.
    body.querySelectorAll("[data-kind]").forEach((btn) => {
      btn.onclick = () => { captureFormValues(); addForm.kind = btn.dataset.kind; renderAddForm(); };
    });
    body.querySelectorAll("[data-currency]").forEach((btn) => {
      btn.onclick = () => { captureFormValues(); addForm.currency = btn.dataset.currency; renderAddForm(); };
    });
    body.querySelectorAll("[data-cat]").forEach((btn) => {
      btn.onclick = () => { captureFormValues(); addForm.category = btn.dataset.cat; renderAddForm(); };
    });
    body.querySelector("#addCancel").onclick = () => closeSheet("addBackdrop");
    body.querySelector("#addClose").onclick = () => closeSheet("addBackdrop");
    body.querySelector("#addSave").onclick = submitAddForm;
  }

  async function submitAddForm() {
    const amount = parseFloat(document.getElementById("fAmount").value);
    if (!amount || amount <= 0) { toast("Summani to'g'ri kiriting"); return; }
    const isDebt = addForm.kind.startsWith("qarz");
    const person = isDebt ? (document.getElementById("fPerson").value || "").trim() : "";
    if (isDebt && !person) { toast("Qarz uchun ism kerak"); return; }

    const body = {
      kind: addForm.kind, amount, currency: addForm.currency,
      category: isDebt ? "qarz" : addForm.category,
      note: (document.getElementById("fNote").value || "").trim(),
      person: person || null,
      date: document.getElementById("fDate").value || todayIso(),
    };
    try {
      await api("/api/transactions", { method: "POST", body });
      haptic("success"); toast("Saqlandi ✅");
      closeSheet("addBackdrop");
      refreshAll();
    } catch (e) {
      haptic("error"); toast("Xatolik: " + e.message);
    }
  }

  // ----------------------------------------------------------------------- //
  // CSV eksport
  // ----------------------------------------------------------------------- //

  // Havolada imzo tashilmaydi: avval bir martalik token olinadi, u 60
  // soniya yashaydi va ishlatilgach o'chadi. Shunda havola brauzer
  // tarixida qolib ketsa ham ish bermaydi.
  async function exportCsv() {
    try {
      const { token } = await api("/api/export/token", { method: "POST" });
      const url = `${location.origin}/api/export.csv?token=${encodeURIComponent(token)}`;
      if (tg && tg.openLink) {
        tg.openLink(url);
      } else {
        window.open(url, "_blank");
      }
    } catch (e) {
      if (e.paywall) { showPaywall(e.message); return; }
      haptic("error");
      toast("Yuklab bo'lmadi: " + e.message);
    }
  }

  // ----------------------------------------------------------------------- //
  // Qidiruv
  // ----------------------------------------------------------------------- //

  let searchTimer = null;

  function initSearch() {
    const panel = document.getElementById("searchPanel");
    const dashboard = document.getElementById("dashboard");
    const toggle = document.getElementById("searchToggle");
    const input = document.getElementById("searchInput");

    toggle.onclick = () => {
      const opening = panel.classList.contains("hidden");
      panel.classList.toggle("hidden");
      dashboard.classList.toggle("hidden", opening);
      document.getElementById("fabAdd").classList.toggle("hidden", opening);
      if (opening) input.focus();
    };

    input.oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runSearch, 350);
    };
  }

  async function runSearch() {
    const q = document.getElementById("searchInput").value.trim();
    const resultsEl = document.getElementById("searchResults");
    const metaEl = document.getElementById("searchMeta");
    if (!q) { resultsEl.innerHTML = ""; metaEl.textContent = ""; return; }

    resultsEl.innerHTML = skeleton(3);
    try {
      const data = await api(`/api/transactions?search=${encodeURIComponent(q)}&limit=100`);
      resultsEl.innerHTML = "";
      if (!data.items.length) {
        metaEl.textContent = "Natija topilmadi.";
        return;
      }
      const totalsStr = Object.entries(data.totals)
        .map(([cur, v]) => fmtMoney(v, cur)).join(" + ");
      metaEl.textContent = `${data.total_count} ta natija · Jami: ${totalsStr}`;
      data.items.forEach((tx) => resultsEl.appendChild(buildTxRow(tx)));
    } catch (e) {
      metaEl.textContent = "Xatolik: " + e.message;
    }
  }

  // ----------------------------------------------------------------------- //
  // Boshlash
  // ----------------------------------------------------------------------- //

  function initTabs() {
    document.querySelectorAll("#periodTabs button").forEach((btn) => {
      btn.onclick = () => {
        haptic("light");
        document.querySelectorAll("#periodTabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.period = btn.dataset.period;
        state.ref = todayIso();
        loadSummary();
      };
    });

    document.querySelectorAll("#kindTabs button").forEach((btn) => {
      btn.onclick = () => {
        haptic("light");
        document.querySelectorAll("#kindTabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.kind = btn.dataset.kind;
        renderCurrentKind();
        state.recentOffset = 0;
        loadRecent(false);
      };
    });

    document.getElementById("prevRange").onclick = () => {
      haptic("light");
      state.ref = shiftRef(state.period, state.ref, -1);
      loadSummary();
    };
    document.getElementById("nextRange").onclick = () => {
      haptic("light");
      state.ref = shiftRef(state.period, state.ref, 1);
      loadSummary();
    };
    document.getElementById("loadMore").onclick = () => {
      state.recentOffset += state.recentLimit;
      loadRecent(true);
    };

    document.getElementById("fabAdd").onclick = openAddSheet;
    document.getElementById("csvBtn").onclick = exportCsv;

    document.getElementById("detailBackdrop").onclick = (ev) => {
      if (ev.target.id === "detailBackdrop") closeSheet("detailBackdrop");
    };
    document.getElementById("addBackdrop").onclick = (ev) => {
      if (ev.target.id === "addBackdrop") closeSheet("addBackdrop");
    };
  }

  async function main() {
    if (!INIT_DATA) {
      document.getElementById("app").innerHTML =
        '<div class="empty-state" style="padding-top:60px">⚠️ Bu sahifa faqat Telegram ichida ishlaydi.<br>Botdagi «📊 Boshqaruv paneli» tugmasini bosing.</div>';
      return;
    }
    try {
      await loadMe();
    } catch (e) {
      document.getElementById("app").innerHTML =
        `<div class="empty-state" style="padding-top:60px">⚠️ ${escapeHtml(e.message)}</div>`;
      return;
    }
    initTabs();
    initSearch();
    await Promise.all([loadSummary(), loadDebts(), loadSavings()]);
  }

  main();
})();
