// Tableau de l'enseignant : suit le direct (poll.js). En attente, met à jour la liste des
// connectés (noms insérés comme texte, jamais comme HTML). Pendant le déroulement, « +10 s »
// et « Terminer le créneau » visent le créneau en cours, et « k / n ont répondu » suit les
// réponses : la page ne se recharge qu'au changement de groupe.
(() => {
  const root = document.querySelector("body[data-state-url]");
  if (!root) return;
  const slots = root.querySelectorAll("input[name=slot]"); // formulaires du bandeau
  const CONFIRM_MS = 3000; // TPS-02 : « Confirmer » reste affiché 3 s
  const disarms = []; // un « Confirmer » ne vaut que pour le créneau où il est apparu
  for (const form of root.querySelectorAll("form[data-confirm]")) {
    const button = form.querySelector("button");
    const label = button.textContent;
    let armed = null; // minuterie du libellé « Confirmer », tant qu'il est affiché
    const disarm = () => {
      clearTimeout(armed);
      armed = null;
      button.textContent = label;
    };
    disarms.push(disarm);
    form.addEventListener("submit", (event) => {
      if (armed !== null) return; // second clic dans les 3 s : envoi
      event.preventDefault();
      button.textContent = form.dataset.confirm;
      armed = setTimeout(disarm, CONFIRM_MS);
    });
  }
  let shown = null; // liste affichée : rien à refaire si elle n'a pas changé
  window.qcm.follow(root, (state) => {
    if (state.slot !== null && slots.length && String(state.slot) !== slots[0].value) {
      for (const input of slots) input.value = state.slot;
      for (const disarm of disarms) disarm();
    }
    if (state.answered !== undefined) {
      document.getElementById("answered").textContent = state.answered;
      document.getElementById("present").textContent = state.present;
    }
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
