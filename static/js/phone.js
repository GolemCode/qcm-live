// Téléphone de l'étudiant : suit le direct (poll.js) et enregistre chaque choix aussitôt
// (ETU-04, ETU-07).
(() => {
  const main = document.querySelector("main[data-state-url]");
  if (!main) return;
  window.qcm.follow(main);

  const form = document.getElementById("answer-form");
  if (!form) return;
  const status = document.getElementById("save-status");
  form.addEventListener("change", async () => {
    status.textContent = "";
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      status.textContent = (await response.json()).message;
    } catch {
      status.textContent = "Réseau indisponible : réponse non enregistrée";
    }
  });
})();
