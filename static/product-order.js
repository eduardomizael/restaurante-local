// Each list is independent; the server validates its complete saved snapshot.
(() => {
  let scrollState = [];
  let focusState = null;
  let windowScroll = null;

  const forms = () => document.querySelectorAll("form[data-product-order]");
  const feedback = (form) => form.closest("section").querySelector("[data-order-feedback]");
  const cards = (list) => [...list.querySelectorAll("[data-product-id]")];

  function refreshPositions(list) {
    const items = cards(list);
    items.forEach((card, index) => {
      const position = card.querySelector(".order-position");
      position.textContent = index + 1;
      position.setAttribute("aria-label", `Posição ${index + 1}`);
      card.querySelector('[value$=":up"]').disabled = index === 0;
      card.querySelector('[value$=":down"]').disabled = index === items.length - 1;
    });
  }

  function initialize() {
    forms().forEach((form) => {
      const list = form.querySelector(".product-order-list");
      if (window.Sortable?.get(list)) return;
      const savedIds = JSON.parse(form.elements.product_ids.value);
      form.savedOrder = savedIds;
      if (!window.Sortable) return;
      window.Sortable.create(list, {
        draggable: "[data-product-id]",
        handle: ".order-handle",
        animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 150,
        ghostClass: "order-drag-ghost",
        chosenClass: "order-drag-chosen",
        delay: 150,
        delayOnTouchOnly: true,
        touchStartThreshold: 4,
        onEnd(event) {
          if (event.oldIndex === event.newIndex) return;
          refreshPositions(list);
          form.elements.product_ids.value = JSON.stringify(cards(list).map((card) => Number(card.dataset.productId)));
          focusState = {kind: form.dataset.productOrder, id: event.item.dataset.productId, direction: "down"};
          htmx.trigger(form, "submit");
        },
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initialize);
  document.addEventListener("htmx:beforeRequest", (event) => {
    const source = event.detail.elt;
    if (!source.closest("#catalogue-results")) return;
    scrollState = [...forms()].map((form) => {
      const list = form.querySelector(".product-order-list");
      window.Sortable?.get(list)?.option("disabled", true);
      return {id: list.id, top: list.scrollTop};
    });
    const form = source.closest("form[data-product-order]");
    if (form) {
      windowScroll = {left: window.scrollX, top: window.scrollY};
      feedback(form).textContent = "Salvando…";
      const focused = document.activeElement?.closest("button[name=move]");
      if (focused?.form === form) {
        const [id, direction] = focused.value.split(":");
        focusState = {kind: form.dataset.productOrder, id, direction};
      }
    } else {
      focusState = null;
      windowScroll = null;
    }
  });
  document.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target.id !== "catalogue-results") return;
    initialize();
    scrollState.forEach(({id, top}) => {
      const list = document.getElementById(id);
      if (list) list.scrollTop = top;
    });
    if (focusState) {
      const form = document.querySelector(`form[data-product-order="${focusState.kind}"]`);
      const card = form?.querySelector(`[data-product-id="${focusState.id}"]`);
      const preferred = card?.querySelector(`[value$=":${focusState.direction}"]:not(:disabled)`);
      (preferred || card?.querySelector("button:not(:disabled)"))?.focus({preventScroll: true});
    }
    if (windowScroll) window.scrollTo(windowScroll.left, windowScroll.top);
    focusState = null;
  });
  document.addEventListener("htmx:afterRequest", (event) => {
    const source = event.detail.requestConfig?.elt || event.detail.elt;
    if (!source.closest("#catalogue-results")) return;
    forms().forEach((form) => {
      const list = form.querySelector(".product-order-list");
      window.Sortable?.get(list)?.option("disabled", false);
      // A transport error cannot tell us whether the write reached the server.
      if (!event.detail.successful && form === source) {
        const byId = new Map(cards(list).map((card) => [Number(card.dataset.productId), card]));
        (form.savedOrder || []).forEach((id) => list.append(byId.get(id)));
        form.elements.product_ids.value = JSON.stringify(form.savedOrder || []);
        refreshPositions(list);
        feedback(form).textContent = "Não foi possível confirmar o salvamento. A sequência anterior foi restaurada na tela. Recarregue para conferir a ordem salva.";
        focusState = null;
      }
    });
  });
  document.addEventListener("htmx:beforeCleanupElement", (event) => {
    if (event.detail.elt.matches(".product-order-list")) window.Sortable?.get(event.detail.elt)?.destroy();
  });
})();
