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
