// Outils communs du tableau et du téléphone : interrogation périodique d'un état JSON,
// compte à rebours, et suivi d'une page « en direct ». Script externe (CSP stricte).
window.qcm = {
  // Appelle onState(état) tout de suite puis toutes les `period` ms ; s'arrête si onState
  // renvoie false. Une erreur réseau est ignorée : on réessaie au tour suivant.
  poll(url, onState, period = 1000) {
    async function tick() {
      let again = true;
      try {
        const response = await fetch(url, { cache: "no-store" });
        if (response.ok) again = onState(await response.json()) !== false;
      } catch {
        // réseau momentanément indisponible
      }
      if (again) setTimeout(tick, period);
    }
    tick();
  },

  // Affiche le temps restant, « 0:18 », dans `element` jusqu'à l'échéance, et vide la barre
  // `bar` (élément <progress>, facultatif) au même rythme ; un nouvel appel les recale.
  // Entre deux appels, le décompte est monotone (performance.now()) : il ignore une correction
  // de l'horloge du navigateur. Mais follow() le recale chaque seconde sur le temps calculé par
  // le serveur : si l'horloge du serveur recule, le nombre affiché remonte (REX, section R).
  countdown(element, remainingMs, bar = null) {
    const deadline = performance.now() + remainingMs;
    clearInterval(element.qcmTimer);
    const render = () => {
      const left = Math.max(0, deadline - performance.now());
      const seconds = Math.ceil(left / 1000);
      const text = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
      if (element.textContent !== text) element.textContent = text; // écrit une fois par seconde
      if (bar) bar.value = left;
    };
    render();
    element.qcmTimer = setInterval(render, 250);
  },

  // Page qui suit le direct : `root` porte data-state-url et data-page (jeton de la page).
  // Dès que l'état annonce un autre jeton, la page se recharge, avec un léger décalage
  // aléatoire pour étaler les requêtes d'une classe entière. Sinon, le compte à rebours
  // se recale et onState reçoit l'état.
  // `root` est le <body> : le minuteur et la barre du temps (data-countdown) sont dans le bandeau.
  follow(root, onState) {
    const timer = root.querySelector("[role=timer]");
    const bar = root.querySelector("progress[data-countdown]");
    if (timer) this.countdown(timer, Number(timer.dataset.remainingMs), bar);
    this.poll(root.dataset.stateUrl, (state) => {
      if (state.page !== root.dataset.page) {
        setTimeout(() => window.location.reload(), Math.random() * 300);
        return false;
      }
      if (bar && state.slot_ms !== null) bar.max = state.slot_ms; // temps ajouté (TPS-01)
      if (timer && state.remaining_ms !== null) this.countdown(timer, state.remaining_ms, bar);
      if (onState) onState(state);
      return true;
    });
  },
};
