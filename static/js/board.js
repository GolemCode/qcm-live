// Tableau de l'enseignant : liste des étudiants connectés, rafraîchie chaque seconde.
// Script externe (CSP stricte) ; les noms sont insérés comme texte, jamais comme HTML.
(() => {
  const section = document.querySelector("[data-state-url]");
  if (!section) return;
  const count = document.getElementById("connected-n");
  const list = document.getElementById("connected");

  function render(state) {
    count.textContent = state.connected.length;
    list.replaceChildren(
      ...state.connected.map((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        return item;
      }),
    );
  }

  async function refresh() {
    try {
      const response = await fetch(section.dataset.stateUrl, { cache: "no-store" });
      if (response.ok) render(await response.json());
    } catch {
      // Réseau momentanément indisponible : on réessaie au prochain tour.
    } finally {
      setTimeout(refresh, 1000);
    }
  }

  setTimeout(refresh, 1000);
})();
