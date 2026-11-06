// Tableau de l'enseignant. En attente : liste des connectés. En déroulement : compte à
// rebours, et rechargement quand on change de groupe ou de phase. Les noms sont insérés
// comme texte, jamais comme HTML.
(() => {
  const section = document.querySelector("[data-state-url]");
  if (!section) return;
  const timer = section.querySelector("[role=timer]");
  if (timer) window.qcm.countdown(timer, Number(timer.dataset.remainingMs));

  function renderConnected(names) {
    document.getElementById("connected-n").textContent = names.length;
    document.getElementById("connected").replaceChildren(
      ...names.map((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        return item;
      }),
    );
  }

  window.qcm.poll(section.dataset.stateUrl, (state) => {
    const group = state.group === undefined ? "" : String(state.group);
    if (state.phase !== section.dataset.phase || group !== section.dataset.group) {
      window.location.reload();
      return false;
    }
    if (state.phase === "waiting") renderConnected(state.connected);
    if (timer && state.remaining_ms != null) window.qcm.countdown(timer, state.remaining_ms);
    return true;
  });
})();
