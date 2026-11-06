// Tableau de l'enseignant : suit le direct (poll.js) ; en attente, met à jour la liste des
// connectés. Les noms sont insérés comme texte, jamais comme HTML.
(() => {
  const main = document.querySelector("main[data-state-url]");
  if (!main) return;
  window.qcm.follow(main, (state) => {
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
