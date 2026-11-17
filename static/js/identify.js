// ETU-13 : recherche dans la liste du groupe, pendant la saisie, sans majuscules ni accents.
// Sans ce script, le champ reste masqué et la liste entière reste utilisable.
(function () {
  "use strict";
  const box = document.querySelector(".pick .search");
  const input = document.getElementById("search");
  const entries = Array.from(document.querySelectorAll(".roster li"));
  const none = document.querySelector(".pick .no-match");
  if (!box || !input || !none) return;

  function plain(text) {
    return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  const names = entries.map((entry) => plain(entry.querySelector(".list-name").textContent));

  function filter() {
    const wanted = plain(input.value);
    let shown = 0;
    entries.forEach((entry, i) => {
      const match = names[i].includes(wanted);
      entry.hidden = !match;
      if (match) shown += 1;
    });
    none.hidden = shown > 0;
  }

  box.hidden = false;
  input.addEventListener("input", filter);
  filter();
})();
