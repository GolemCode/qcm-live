// Tableau de l'enseignant : suit le direct (poll.js). En attente, met à jour la liste des
// connectés (noms insérés comme texte, jamais comme HTML). Pendant le déroulement, « +10 s »
// vise le créneau en cours : la page ne se recharge qu'au changement de groupe.
(() => {
  const root = document.querySelector("body[data-state-url]");
  if (!root) return;
  const slot = root.querySelector("input[name=slot]"); // formulaire « +10 s », dans le bandeau
  let shown = null; // liste affichée : rien à refaire si elle n'a pas changé
  window.qcm.follow(root, (state) => {
    if (slot && state.slot !== null) slot.value = state.slot;
    if (!state.connected) return;
    const names = state.connected.join("\n");
    if (names === shown) return;
    shown = names;
    document.getElementById("connected-n").textContent = state.connected.length;
    document.getElementById("connected-bar").value = state.connected.length;
    document.getElementById("connected").replaceChildren(
      ...state.connected.map((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        return item;
      }),
    );
  });
})();
