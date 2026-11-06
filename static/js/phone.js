// Téléphone de l'étudiant : suit la phase et le créneau (rechargement quand ils changent),
// affiche le temps restant et enregistre chaque choix aussitôt (ETU-04, ETU-07).
(() => {
  const main = document.querySelector("main[data-state-url]");
  if (!main) return;
  const timer = main.querySelector("[role=timer]");
  if (timer) window.qcm.countdown(timer, Number(timer.dataset.remainingMs));

  window.qcm.poll(main.dataset.stateUrl, (state) => {
    const slot = state.slot === null ? "" : String(state.slot);
    if (state.phase !== main.dataset.phase || slot !== main.dataset.slot) {
      window.location.reload();
      return false;
    }
    if (timer && state.remaining_ms != null) window.qcm.countdown(timer, state.remaining_ms);
    return true;
  });

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
