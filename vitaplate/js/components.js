function renderState(container, type, message, retry) {
  const state = document.createElement("div");
  state.className = `ui-state ui-state-${type}`;
  state.setAttribute(type === "error" ? "role" : "aria-live", type === "error" ? "alert" : "polite");

  if (type === "loading") {
    state.innerHTML = '<div class="ui-skeleton" aria-hidden="true"></div>';
  } else {
    const text = document.createElement("p");
    text.className = "ui-state-message";
    text.textContent = message;
    state.append(text);
    if (type === "error" && typeof retry === "function") {
      const button = document.createElement("button");
      button.className = "btn btn-ghost btn-sm";
      button.type = "button";
      button.textContent = "Retry";
      button.addEventListener("click", retry);
      state.append(button);
    }
  }

  container.replaceChildren(state);
}
