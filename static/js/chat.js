/* Rihla AI travel agent: the floating chat window.
 *
 * - Talks to the Flask JSON API (/api/chat, /api/confirm/<id>, ...) with fetch().
 * - Every POST sends the CSRF token in the X-CSRF-Token header.
 * - Results come back as "cards" (flight, stay, guide, summary...) drawn with
 *   DOM methods and textContent, so nothing from the server is run as HTML.
 * - The current conversation id is remembered in localStorage, so the chat
 *   continues after changing page; the messages themselves live in the database.
 */
(function () {
  "use strict";

  const root = document.getElementById("chat");
  if (!root) return;

  const $ = (selector) => root.querySelector(selector);
  const panel = $("#chat-panel");
  const fab = $(".chat-fab");
  const log = $(".chat-log");
  const form = $(".chat-form");
  const input = $("#chat-input");
  const starters = $(".chat-starters");
  const historySelect = $(".chat-history");
  const modeBadge = $("[data-mode]");
  const storageKey = "rihla-chat-" + root.dataset.user;
  let conversationId = null;
  let loaded = false;
  let busy = false;

  // ---------------------------------------------------------------- helpers
  function remember(id) {
    conversationId = id;
    try { id ? localStorage.setItem(storageKey, id) : localStorage.removeItem(storageKey); } catch (e) { /* private mode */ }
  }
  function recall() {
    try { return parseInt(localStorage.getItem(storageKey), 10) || null; } catch (e) { return null; }
  }
  function urlWithId(base, id) { return base.replace(/\/0$/, "/" + id); }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // Safe mini-formatting: the text is inserted with textContent, then only
  // **bold** and line breaks are turned into elements.
  function formatText(container, text) {
    text.split("\n").forEach((line, i) => {
      if (i > 0) container.append(document.createElement("br"));
      line.split(/(\*\*[^*]+\*\*)/).forEach((part) => {
        if (/^\*\*[^*]+\*\*$/.test(part)) container.append(el("strong", null, part.slice(2, -2)));
        else if (part) container.append(document.createTextNode(part));
      });
    });
  }

  async function api(url, options) {
    const response = await fetch(url, Object.assign({
      headers: { "Content-Type": "application/json", "X-CSRF-Token": root.dataset.csrf },
      credentials: "same-origin",
    }, options || {}));
    let data = {};
    try { data = await response.json(); } catch (e) { /* not JSON */ }
    if (!response.ok) throw new Error(data.error || "Something went wrong (" + response.status + ").");
    return data;
  }

  function setMode(mode) {
    if (!mode) return;
    modeBadge.textContent = mode === "claude" ? "AI · Claude" : "Demo mode";
    modeBadge.classList.toggle("is-ai", mode === "claude");
  }

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  // ---------------------------------------------------------------- messages
  function addBubble(role, text, cards) {
    const row = el("div", "chat-row chat-" + role);
    if (text) {
      const bubble = el("div", "chat-bubble");
      formatText(bubble, text);
      row.append(bubble);
    }
    if (cards && cards.length) {
      const list = el("div", "chat-cards");
      cards.forEach((card) => { const node = renderCard(card); if (node) list.append(node); });
      row.append(list);
    }
    log.append(row);
    starters.hidden = true;
    scrollDown();
  }

  function addNotice(text) {
    log.append(el("div", "chat-notice", text));
    scrollDown();
  }

  function showTyping(on) {
    let dots = log.querySelector(".chat-typing");
    if (on && !dots) {
      dots = el("div", "chat-row chat-assistant chat-typing");
      const bubble = el("div", "chat-bubble");
      bubble.setAttribute("aria-label", "The agent is typing");
      for (let i = 0; i < 3; i++) bubble.append(el("span", "dot"));
      dots.append(bubble);
      log.append(dots);
      scrollDown();
    } else if (!on && dots) {
      dots.remove();
    }
  }

  // ---------------------------------------------------------------- cards
  function cardShell(type, title, subtitle) {
    const card = el("article", "chat-card chat-card-" + type);
    card.append(el("div", "chat-card-title", title));
    if (subtitle) card.append(el("div", "chat-card-sub", subtitle));
    return card;
  }

  function stars(rating, reviews) {
    if (!rating) return el("div", "chat-card-sub", "New · no reviews yet");
    return el("div", "chat-card-stars", "★ " + rating + (reviews !== undefined ? " (" + reviews + ")" : ""));
  }

  function bookButton(label, message) {
    const button = el("button", "chat-card-btn", label);
    button.type = "button";
    button.addEventListener("click", () => send(message));
    return button;
  }

  function renderCard(c) {
    let card;
    switch (c.type) {
      case "country": {
        card = cardShell("country", (c.warm ? "☀️ " : "") + c.title, c.subtitle);
        card.append(el("div", "chat-card-price", c.price));
        const link = el("a", "chat-card-link", "Open page →");
        link.href = root.dataset.countryUrl.replace("SLUG", encodeURIComponent(c.slug));
        card.append(link);
        break;
      }
      case "flight":
        card = cardShell("flight", "✈ " + c.route, c.title + " · " + c.stops);
        card.append(el("div", "chat-card-sub", c.dates));
        card.append(el("div", "chat-card-price", c.price + " · " + c.seats + " seats left"));
        card.append(bookButton("Book", "Book flight #" + c.id + " (" + c.title + ") for 1 seat"));
        break;
      case "stay":
        card = cardShell("stay", "🛏 " + c.title, c.subtitle);
        card.append(stars(c.rating));
        card.append(el("div", "chat-card-price", c.total || c.price));
        card.append(bookButton("Book", "Book stay #" + c.id + " (" + c.title + ")"));
        break;
      case "guide":
        card = cardShell("guide", "🧭 " + c.title, c.subtitle);
        card.append(stars(c.rating, c.reviews));
        card.append(el("div", "chat-card-price", c.price));
        card.append(bookButton("Book", "Book guide #" + c.id + " (" + c.title + ") for 2 days"));
        break;
      case "summary":
        return renderSummary(c);
      case "booking":
        card = cardShell("booking", "🎟 Trip #" + c.booking_id + " · " + c.country, c.dates);
        (c.items || []).forEach((item) => card.append(el("div", "chat-card-sub", item)));
        card.append(el("div", "chat-card-price", c.total + (c.status === "cancelled" ? " · cancelled" : "")));
        break;
      default:
        return null;
    }
    return card;
  }

  // The boarding-pass summary with Confirm / Not now (the ONLY way to book from the chat).
  function renderSummary(c) {
    const card = el("article", "chat-summary");
    card.append(el("div", "chat-summary-head", c.action === "cancel" ? "CANCELLATION" : "BOOKING SUMMARY"));
    card.append(el("div", "chat-card-title", c.title));
    card.append(el("div", "chat-card-sub", "📅 " + c.dates));
    const list = el("ul", "chat-summary-lines");
    c.lines.forEach((line) => {
      const li = el("li");
      const left = el("span");
      left.append(el("span", null, line.label), document.createElement("br"), el("small", null, line.detail));
      li.append(left, el("span", null, line.total));
      list.append(li);
    });
    card.append(list);
    const total = el("div", "chat-summary-total");
    total.append(el("span", null, "Total"), el("strong", null, c.total));
    card.append(total);

    const actions = el("div", "chat-summary-actions");
    if (c.status && c.status !== "pending") {   // an old summary, reloaded from history
      actions.append(el("span", "chat-summary-closed", c.status === "confirmed" ? "✅ Confirmed" : "Closed"));
      card.append(actions);
      return card;
    }
    const yes = el("button", "btn btn-sm btn-terracotta", c.action === "cancel" ? "Confirm cancellation" : "Confirm & book");
    const no = el("button", "btn btn-sm btn-outline-ink", "Not now");
    yes.type = no.type = "button";
    yes.addEventListener("click", () => decide(root.dataset.confirmUrl, c.proposal_id, [yes, no]));
    no.addEventListener("click", () => decide(root.dataset.declineUrl, c.proposal_id, [yes, no]));
    actions.append(yes, no);
    card.append(actions);
    return card;
  }

  async function decide(baseUrl, proposalId, buttons) {
    if (busy) return;
    buttons.forEach((b) => { b.disabled = true; });
    busy = true;
    showTyping(true);
    try {
      const data = await api(urlWithId(baseUrl, proposalId), { method: "POST", body: "{}" });
      showTyping(false);
      data.messages.forEach((m) => addBubble(m.role, m.text, m.cards));
      setMode(data.mode);
    } catch (error) {
      showTyping(false);
      addNotice(error.message);
      buttons.forEach((b) => { b.disabled = false; });
    } finally {
      busy = false;
    }
  }

  // ---------------------------------------------------------------- sending
  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    input.value = "";
    addBubble("user", text);
    showTyping(true);
    try {
      const data = await api(root.dataset.chatUrl, {
        method: "POST",
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });
      showTyping(false);
      if (data.conversation_id !== conversationId) { remember(data.conversation_id); loadHistoryList(); }
      // The user's bubble is already on screen: only draw the agent's answer(s).
      data.messages.filter((m) => m.role === "assistant").forEach((m) => addBubble("assistant", m.text, m.cards));
      setMode(data.mode);
    } catch (error) {
      showTyping(false);
      addNotice(error.message);
    } finally {
      busy = false;
      input.focus();
    }
  }

  // ---------------------------------------------------------------- history
  async function loadConversation(id) {
    log.replaceChildren();
    starters.hidden = false;
    if (!id) { remember(null); return; }
    try {
      const data = await api(urlWithId(root.dataset.conversationUrl, id));
      remember(data.conversation_id);
      setMode(data.mode);
      data.messages.forEach((m) => addBubble(m.role, m.text, m.cards));
    } catch (error) {
      remember(null);   // deleted or not ours: start fresh
    }
  }

  async function loadHistoryList() {
    try {
      const data = await api(root.dataset.listUrl);
      setMode(data.mode);
      historySelect.replaceChildren(el("option", null, "Past chats"));
      historySelect.firstChild.value = "";
      data.conversations.forEach((c) => {
        const option = el("option", null, c.title + " · " + c.updated);
        option.value = c.id;
        if (c.id === conversationId) option.selected = true;
        historySelect.append(option);
      });
    } catch (error) { /* the list is optional */ }
  }

  // ---------------------------------------------------------------- open / close
  function open() {
    panel.hidden = false;
    fab.setAttribute("aria-expanded", "true");
    root.classList.add("is-open");
    if (!loaded) {
      loaded = true;
      loadConversation(recall()).then(loadHistoryList);
      addWelcome();
    }
    input.focus();
  }
  function close() {
    panel.hidden = true;
    fab.setAttribute("aria-expanded", "false");
    root.classList.remove("is-open");
    fab.focus();
  }
  function addWelcome() {
    if (!recall()) {
      addBubble("assistant", "Hi! I'm Rihla, your travel agent. Tell me when you'd like to travel, your budget " +
        "and what you love, and I'll plan and book the whole trip, from the flight to the last dinner.");
      starters.hidden = false;
    }
  }

  fab.addEventListener("click", () => (panel.hidden ? open() : close()));
  $("[data-close]").addEventListener("click", close);
  $("[data-new]").addEventListener("click", () => {
    remember(null);
    log.replaceChildren();
    addWelcome();
    historySelect.value = "";
    input.focus();
  });
  historySelect.addEventListener("change", () => {
    if (historySelect.value) loadConversation(parseInt(historySelect.value, 10));
  });
  starters.addEventListener("click", (event) => {
    if (event.target.matches(".chat-starter")) send(event.target.textContent);
  });
  form.addEventListener("submit", (event) => { event.preventDefault(); send(input.value); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !panel.hidden) close(); });

  // Links like <a data-open-chat> anywhere on the page open the chat.
  document.querySelectorAll("[data-open-chat]").forEach((link) =>
    link.addEventListener("click", (event) => { event.preventDefault(); open(); }));
})();
