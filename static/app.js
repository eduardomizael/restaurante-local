document.addEventListener("htmx:configRequest", (event) => {
  // Send a CSRF token for all HTMX POSTs using the current local fragment.
  const token = document.querySelector("[name=csrfmiddlewaretoken]");
  if (token) event.detail.headers["X-CSRFToken"] = token.value;
});
document.addEventListener("htmx:sendError", () => {
  const message = document.getElementById("connection-message");
  if (message) {
    message.textContent = "Sem resposta do inicializador. Verifique se o programa está aberto.";
    message.classList.add("error");
  }
});
document.addEventListener("htmx:responseError", () => {
  const message = document.getElementById("connection-message");
  if (message) message.textContent = "A ação não foi concluída. Consulte o status do inicializador.";
});

window.localPollingAllowed = () => !document.hidden
  && !document.querySelector("dialog[open], form.htmx-request, form[data-submitting]");

document.addEventListener("htmx:beforeSwap", (event) => {
  if (["shared-board", "runtime-status", "print-jobs"].includes(event.detail.target.id)
      && !window.localPollingAllowed()) {
    event.detail.shouldSwap = false;
    return;
  }
  if (event.detail.target.id === "shared-board") {
    const destination = event.detail.xhr.getResponseHeader("X-Selected-Order");
    if (destination !== null && destination !== document.body.dataset.selectedOrder) {
      event.detail.shouldSwap = false;
    }
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.dataset.submitting) {
    event.preventDefault();
    return;
  }
  // HTMX owns its own pending state; normal POSTs navigate after acceptance.
  if (form.hasAttribute("hx-post")) return;
  form.dataset.submitting = "true";
  form.setAttribute("aria-busy", "true");
  setTimeout(() => form.querySelectorAll("button[type=submit]").forEach((button) => {
    button.disabled = true;
  }), 0);
});

window.addEventListener("pageshow", () => {
  document.querySelectorAll("form[data-submitting]").forEach((form) => {
    delete form.dataset.submitting;
    form.removeAttribute("aria-busy");
    form.querySelectorAll("button[type=submit]").forEach((button) => { button.disabled = false; });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.getElementById("numeric-keypad");
  const output = document.getElementById("keypad-value");
  if (!dialog) return;
  let target = null;
  let draft = "";
  let precision = "0";
  const display = () => { output.textContent = draft || "0"; };
  const open = (input) => {
    target = input;
    draft = input.value.replace(".", ",");
    precision = input.dataset.keypad;
    document.getElementById("keypad-label").textContent = document.querySelector(`label[for="${input.id}"]`)?.textContent || "Valor";
    document.getElementById("keypad-separator").disabled = precision === "0";
    display();
    dialog.showModal();
  };
  document.querySelectorAll("input[data-keypad]").forEach((input) => {
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "secondary compact keypad-trigger";
    trigger.textContent = "▦";
    trigger.setAttribute("aria-label", `Abrir teclado numérico: ${input.labels?.[0]?.textContent || "valor"}`);
    trigger.addEventListener("click", () => open(input));
    input.after(trigger);
    input.addEventListener("click", () => open(input));
  });
  dialog.querySelectorAll("[data-digit]").forEach((button) => button.addEventListener("click", () => {
    const decimals = draft.includes(",") ? draft.split(",")[1].length : 0;
    if (draft.length >= 18 || (draft.includes(",") && decimals >= Number(precision))) return;
    draft += button.dataset.digit;
    display();
  }));
  document.getElementById("keypad-separator").addEventListener("click", () => {
    if (precision !== "0" && !draft.includes(",")) draft = (draft || "0") + ",";
    display();
  });
  document.getElementById("keypad-backspace").addEventListener("click", () => { draft = draft.slice(0, -1); display(); });
  document.getElementById("keypad-clear").addEventListener("click", () => { draft = ""; display(); });
  document.getElementById("keypad-cancel").addEventListener("click", () => dialog.close());
  document.getElementById("keypad-apply").addEventListener("click", () => {
    target.value = draft.endsWith(",") ? draft.slice(0, -1) : draft;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
    dialog.close();
    target.focus();
  });
});
