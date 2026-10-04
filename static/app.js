document.addEventListener("htmx:configRequest", (event) => {
  // Send a CSRF token for all HTMX POSTs using the current local fragment.
  const token = document.querySelector("[name=csrfmiddlewaretoken]");
  if (token) event.detail.headers["X-CSRFToken"] = token.value;
});
function requestFeedback(event) {
  const source = event.detail.requestConfig?.elt || event.detail.elt;
  if (source?.closest("#manual-item-dialog")) return document.getElementById("manual-item-feedback");
  if (source?.closest("#catalogue-results")) return document.getElementById("catalogue-feedback");
  if (source?.closest("#attendance-workspace") && source.id !== "shared-board") {
    return document.getElementById("attendance-feedback");
  }
  return document.getElementById("connection-message");
}
document.addEventListener("htmx:sendError", (event) => {
  const message = requestFeedback(event);
  if (message) {
    message.textContent = "Sem resposta do inicializador. Verifique se o programa está aberto.";
    message.classList.add("error");
  }
});
document.addEventListener("htmx:responseError", (event) => {
  const message = requestFeedback(event);
  if (message) message.textContent = "A ação não foi concluída. Consulte o status do inicializador.";
});

window.localPollingAllowed = () => !document.hidden
  && !document.querySelector("dialog[open], form.htmx-request, form[data-submitting], .order-card.htmx-request");

const attendanceScroll = new Map();
const syncAttendanceSelection = () => {
  const workspace = document.getElementById("attendance-workspace");
  if (workspace) {
    if (document.body.dataset.selectedOrder !== workspace.dataset.selectedOrder) {
      attendanceScroll.delete("order-item-list");
    }
    document.body.dataset.selectedOrder = workspace.dataset.selectedOrder;
  }
};
const restoreAttendanceScroll = () => {
  document.querySelectorAll("[data-preserve-scroll]").forEach((element) => {
    const position = attendanceScroll.get(element.id);
    if (position) {
      element.scrollLeft = position.left;
      element.scrollTop = position.top;
    }
  });
};

document.addEventListener("htmx:beforeSwap", (event) => {
  const source = event.detail.requestConfig?.elt;
  const polling = ["shared-board", "runtime-status", "print-jobs"].includes(source?.id);
  if (polling
      && !window.localPollingAllowed()) {
    event.detail.shouldSwap = false;
    return;
  }
  if (["shared-board", "catalogue-choices", "manual-item-content"].includes(event.detail.target.id)) {
    const destination = event.detail.xhr.getResponseHeader("X-Selected-Order");
    if (destination !== null && destination !== document.body.dataset.selectedOrder) {
      event.detail.shouldSwap = false;
      return;
    }
  }
  // Only our explicit validation fragment may replace the local error region.
  if ([400, 409].includes(event.detail.xhr.status)
      && event.detail.xhr.getResponseHeader("HX-Retarget") === "#attendance-feedback") {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
  if ([400, 409].includes(event.detail.xhr.status)
      && event.detail.xhr.getResponseHeader("X-Manual-Item-Fragment") === "1") {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
  if ([400, 409].includes(event.detail.xhr.status)
      && event.detail.target.id === "catalogue-results"
      && event.detail.xhr.getResponseHeader("X-Catalogue-Fragment") === "1") {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
  if (event.detail.shouldSwap && document.getElementById("attendance-workspace")) {
    document.querySelectorAll("[data-preserve-scroll]").forEach((element) => {
      attendanceScroll.set(element.id, {left: element.scrollLeft, top: element.scrollTop});
    });
  }
});

document.addEventListener("htmx:beforeRequest", (event) => {
  if (event.detail.elt.closest("#attendance-workspace") && event.detail.elt.id !== "shared-board") {
    const feedback = document.getElementById("attendance-feedback");
    if (feedback) feedback.replaceChildren();
  }
});
document.addEventListener("htmx:afterSwap", syncAttendanceSelection);
document.addEventListener("htmx:oobAfterSwap", restoreAttendanceScroll);
document.addEventListener("htmx:afterSettle", restoreAttendanceScroll);
document.addEventListener("htmx:historyRestore", syncAttendanceSelection);
document.addEventListener("htmx:afterRequest", (event) => {
  const source = event.detail.requestConfig?.elt || event.detail.elt;
  if (!event.detail.successful && source?.closest("#catalogue-results")) {
    document.querySelectorAll("#catalogue-results input[type=checkbox]").forEach((input) => {
      input.checked = input.dataset.savedChecked === "true";
    });
  }
  if (event.detail.successful) {
    const message = document.getElementById("connection-message");
    if (message?.classList.contains("connection-feedback")) message.textContent = "";
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.dataset.submitting) {
    event.preventDefault();
    return;
  }
  // HTMX owns its own pending state; normal POSTs navigate after acceptance.
  if (form.matches("[hx-post], [hx-get]")) return;
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
  const itemDialog = document.getElementById("manual-item-dialog");
  if (itemDialog) {
    let replaceOnDigit = true;
    document.addEventListener("htmx:afterSwap", (event) => {
      if (event.detail.target.id !== "manual-item-content") return;
      const input = itemDialog.querySelector("[data-item-value]");
      if (!input) return;
      if (!itemDialog.open) itemDialog.showModal();
      input.focus();
      input.select();
      replaceOnDigit = true;
    });
    document.addEventListener("manualItemAdded", () => itemDialog.close());
    itemDialog.addEventListener("cancel", (event) => {
      if (itemDialog.querySelector("form.htmx-request")) event.preventDefault();
    });
    itemDialog.addEventListener("input", (event) => {
      if (event.target.matches("[data-item-value]")) replaceOnDigit = false;
    });
    itemDialog.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      const input = itemDialog.querySelector("[data-item-value]");
      if (!button || !input || button.type === "submit") return;
      if (button.hasAttribute("data-item-cancel")) { itemDialog.close(); return; }
      const precision = Number(input.dataset.itemValue);
      let value = input.value.replace(".", ",");
      if (button.hasAttribute("data-item-digit")) {
        if (replaceOnDigit) value = "";
        const decimals = value.includes(",") ? value.split(",")[1].length : 0;
        if (value.length >= 18 || (value.includes(",") && decimals >= precision)) return;
        value += button.dataset.itemDigit;
      } else if (button.hasAttribute("data-item-separator")) {
        if (precision && !value.includes(",")) value = (value || "0") + ",";
      } else if (button.hasAttribute("data-item-backspace")) value = value.slice(0, -1);
      else if (button.hasAttribute("data-item-clear")) value = "";
      else return;
      replaceOnDigit = false;
      input.value = value;
      input.dispatchEvent(new Event("input", {bubbles: true}));
    });
  }
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
