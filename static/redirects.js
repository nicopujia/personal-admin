(() => {
  const asyncValue = "redirects";

  function setBusy(form, busy) {
    for (const element of form.elements) {
      element.disabled = busy;
    }

    const submitter = document.activeElement;
    if (submitter && submitter.getAttribute("form") === form.id) {
      submitter.disabled = busy;
    }
  }

  function showMessage(category, message) {
    const target = document.querySelector("#redirects-messages");
    if (!target || !message) {
      return;
    }

    target.innerHTML = "";
    const item = document.createElement("p");
    item.className = `message ${category}`;
    item.textContent = message;
    target.append(item);
  }

  async function submitRedirectForm(form) {
    const formData = new FormData(form);
    setBusy(form, true);

    try {
      const response = await fetch(form.action, {
        method: form.method || "POST",
        body: formData,
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Pujia-Async": asyncValue,
        },
      });

      const payload = await response.json();
      const current = document.querySelector("#redirects-content");
      if (!current || typeof payload.html !== "string") {
        window.location.reload();
        return;
      }

      current.outerHTML = payload.html;
      showMessage(payload.category || (response.ok ? "success" : "error"), payload.message || "");

      if (response.ok && form.hasAttribute("data-create-form")) {
        const nextPathsInput = document.querySelector("[data-create-form] textarea[name='source_paths']");
        if (nextPathsInput) {
          nextPathsInput.focus();
        }
      }
    } catch (_error) {
      showMessage("error", "Save failed. Try again.");
    } finally {
      if (form.isConnected) {
        setBusy(form, false);
      }
    }
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.async !== asyncValue) {
      return;
    }

    event.preventDefault();
    submitRedirectForm(form);
  });
})();
