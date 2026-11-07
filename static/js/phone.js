// Téléphone de l'étudiant : suit le direct (poll.js) et enregistre chaque choix aussitôt
// (ETU-04, ETU-07). Les envois partent un par un, chacun avec l'état du formulaire au moment
// de partir : la dernière réponse arrive toujours en dernier, même sur un réseau lent.
(() => {
  const main = document.querySelector("main[data-state-url]");
  if (!main) return;
  window.qcm.follow(main);

  const form = document.getElementById("answer-form");
  if (!form) return;
  const status = document.getElementById("save-status");

  async function send() {
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      const json = (response.headers.get("Content-Type") || "").includes("application/json");
      status.textContent = json
        ? (await response.json()).message
        : "Réponse refusée : rechargez la page.";
    } catch {
      status.textContent = "Réseau indisponible : réponse non enregistrée";
    }
  }

  let queue = Promise.resolve();
  form.addEventListener("change", () => {
    status.textContent = "";
    queue = queue.then(send);
  });
})();
