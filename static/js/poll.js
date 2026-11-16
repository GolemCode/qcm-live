// Outils communs du tableau et du téléphone : interrogation périodique d'un état JSON,
// compte à rebours, et suivi d'une page « en direct ». Script externe (CSP stricte).
window.qcm = {
  // Dernière réponse reçue du serveur, quelle qu'elle soit (ETU-11) : le chargement de la page
  // en est une.
  lastContact: performance.now(),

  // Toute requête au serveur passe par ici : abandonnée sans réponse au bout de `ms`
  // millisecondes (une requête perdue par le réseau ne bloque pas les suivantes), et notée
  // comme un contact dès que le serveur répond, quel que soit le statut.
  async request(url, options = {}, ms = 5000) {
    const signal = AbortSignal.timeout ? AbortSignal.timeout(ms) : undefined;
    const response = await fetch(url, { cache: "no-store", signal, ...options });
    this.lastContact = performance.now();
    return response;
  },

  // ETU-11 : `element` (caché) affiche `text` dès que le serveur n'a plus répondu depuis
  // `after` ms, et se vide quand il répond à nouveau.
  watchConnection(element, text, after = 3000) {
    setInterval(() => {
      const lost = performance.now() - this.lastContact > after;
      if (lost !== element.hidden) return;
      element.textContent = lost ? text : "";
      element.hidden = !lost;
    }, 250);
  },

  // Appelle onState(état) tout de suite puis toutes les `period` ms ; s'arrête si onState
  // renvoie false. Une erreur réseau est ignorée : on réessaie au tour suivant.
  poll(url, onState, period = 1000) {
    const tick = async () => {
      let again = true;
      try {
        const response = await this.request(url);
        if (response.ok) again = onState(await response.json()) !== false;
      } catch {
        // réseau momentanément indisponible
      }
      if (again) setTimeout(tick, period);
    };
    tick();
  },

  // Affiche le temps restant, « 0:18 », dans `element` jusqu'à l'échéance, et vide la barre
  // `bar` (élément <progress>, facultatif) au même rythme ; un nouvel appel les recale.
  // Entre deux appels, le décompte est monotone (performance.now()) : il ignore une correction
  // de l'horloge du navigateur. Mais follow() le recale chaque seconde sur le temps calculé par
  // le serveur : si l'horloge du serveur recule, le nombre affiché remonte (REX, section R).
  // L'échéance reste lisible sur l'élément (`qcmDeadline`), sur la même horloge.
  countdown(element, remainingMs, bar = null) {
    const deadline = performance.now() + remainingMs;
    element.qcmDeadline = deadline;
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
