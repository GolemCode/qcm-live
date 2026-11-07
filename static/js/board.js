// Tableau de l'enseignant : suit le direct (poll.js). En attente, met à jour la liste des
// connectés (noms insérés comme texte, jamais comme HTML). Pendant le déroulement, « +10 s »
// vise le créneau en cours : la page ne se recharge qu'au changement de groupe.
(() => {
  const main = document.querySelector("main[data-state-url]");
  if (!main) return;
  const slot = main.querySelector("input[name=slot]");
  window.qcm.follow(main, (state) => {
    if (slot && state.slot !== undefined) slot.value = state.slot;
    if (!state.connected) return;
    document.getElementById("connected-n").textContent = state.connected.length;
    document.getElementById("connected").replaceChildren(
      ...state.connected.map((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        return item;
      }),
    );
  });
})();
