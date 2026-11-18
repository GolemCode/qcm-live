"""Contrôles d'accessibilité communs aux tests de bout en bout (AFF-04, ACC-01).

- `low_contrasts` : contraste de tout texte et de toute forme, tels qu'affichés (I9).
- `axe_violations` : règles WCAG 2.1 A et AA vérifiées par axe-core, livré dans `vendor/`.
- `keyboard_problems` : chaque élément interactif s'atteint par Tab, avec un focus visible.

Aucun de ces contrôles ne remplace un essai avec un lecteur d'écran : ils ne trouvent qu'une
partie des défauts.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

AXE_SOURCE = (Path(__file__).parent / "vendor" / "axe.min.js").read_text(encoding="utf-8")
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]


def luminance(color) -> float:
    def channel(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# Fonctions JavaScript communes : lecture d'une couleur, mélange, fond tel qu'affiché derrière un
# élément (composé à travers les fonds semi-transparents de ses ancêtres), nom d'un élément, et
# éléments visibles qui portent eux-mêmes du texte.
PAGE_JS = """
  const WHITE = [255, 255, 255];
  const parse = s => s.match(/[\\d.]+/g).map(Number);
  const mix = (under, over, alpha) => under.map((v, i) => v * (1 - alpha) + over[i] * alpha);
  // Fonds de `el` et de ses ancêtres jusqu'à `last` compris, posés sur `base`.
  const compose = (el, last, base) => {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const [r, g, b, a = 1] = parse(getComputedStyle(e).backgroundColor);
      if (a > 0) layers.push([[r, g, b], a]);
      if (a >= 1 || e === last) break;
    }
    return layers.reverse().reduce((out, [color, a]) => mix(out, color, a), base);
  };
  const name = e => (e.getAttribute("aria-label") || e.textContent || e.name || e.tagName)
    .trim().slice(0, 40);
  const ownText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const textElements = () => [...document.body.querySelectorAll("*")]
    .filter(el => ownText(el) && el.checkVisibility());
"""

# Pour chaque élément visible qui porte du texte, ou pour chaque forme : couleur du texte et
# fond tels qu'affichés, composés à travers les fonds semi-transparents des ancêtres et
# l'opacité de l'élément ou d'un ancêtre (un bouton estompé, par exemple).
READ_COLORS = (
    "() => {"
    + PAGE_JS
    + """
  const found = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (!(ownText(el) || el.matches("svg[role=img]")) || !el.checkVisibility()) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) continue;
    let group = null, opacity = 1;
    for (let e = el; e; e = e.parentElement) {
      const o = Number(getComputedStyle(e).opacity);
      if (o < 1) { opacity *= o; group = e; }
    }
    const behind = group && group.parentElement ? compose(group.parentElement, null, WHITE) : WHITE;
    const inside = compose(el, group, behind);
    const [r, g, b, a = 1] = parse(getComputedStyle(el).color);
    const ink = mix(inside, [r, g, b], a);
    found.push({
      label: name(el),
      fg: mix(behind, ink, opacity),
      bg: mix(behind, inside, opacity),
    });
  }
  return found;
}"""
)


def low_contrasts(screen: Page) -> list[tuple[str, float]]:
    """Textes et formes de l'écran dont le contraste avec leur fond est sous 4,5:1."""
    found = screen.evaluate(READ_COLORS)
    assert found
    measured = [(item["label"], contrast(item["fg"], item["bg"])) for item in found]
    return [(label, round(ratio, 2)) for label, ratio in measured if ratio < 4.5]


def axe_violations(screen: Page) -> list[str]:
    """Violations des règles WCAG 2.1 A et AA relevées par axe-core sur la page affichée.

    axe-core est évalué par Playwright, hors de la page : la CSP de l'application, qui refuse
    tout script inline, reste en place pendant le contrôle."""
    screen.wait_for_load_state("load")
    screen.evaluate(AXE_SOURCE)
    return screen.evaluate(
        """async (tags) => {
          const result = await axe.run(document, { runOnly: { type: "tag", values: tags } });
          return result.violations.map(v => `${v.id} : ${v.nodes.map(n => n.target).join(" ; ")}`);
        }""",
        WCAG_TAGS,
    )


FOCUSABLE = (
    "a[href], button:not(:disabled), input:not([type=hidden]):not(:disabled), "
    "select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex='-1'])"
)

# Indicateur de focus de l'élément actif : épaisseur du contour, et contraste de sa couleur
# avec le fond tel qu'affiché autour de l'élément (le contour est dessiné à l'extérieur).
_FOCUS_JS = (
    "() => {"
    + PAGE_JS
    + """
  const el = document.activeElement;
  const style = getComputedStyle(el);
  const width = style.outlineStyle === "none" ? 0 : parseFloat(style.outlineWidth);
  const [r, g, b, a = 1] = parse(style.outlineColor);
  const around = compose(el.parentElement, null, WHITE);
  return {
    id: el.dataset.kbd || null,
    label: name(el),
    width,
    ring: mix(around, [r, g, b], a),
    around,
  };
}"""
)


def keyboard_problems(screen: Page) -> list[str]:
    """Éléments interactifs visibles que la touche Tab n'atteint pas, ou dont le focus ne se
    voit pas (contour de moins de 2 px, ou contraste sous 3:1 avec le fond). Un groupe de
    boutons radio compte pour un seul élément."""
    screen.wait_for_load_state("load")
    expected = screen.evaluate(
        "(selector) => {"
        + PAGE_JS
        + """
          // Un groupe de boutons radio ne compte qu'une fois : Tab en atteint un seul (le coché,
          // ou le premier), et les flèches passent de l'un à l'autre.
          // Groupe : même formulaire (ou aucun) et même nom.
          const items = [];
          const groups = new Map(); // formulaire -> nom -> repère du premier bouton du groupe
          for (const e of document.querySelectorAll(selector)) {
            if (!e.checkVisibility()) continue;
            // Retiré exprès du clavier et des aides techniques (bouton par défaut de la touche
            // Entrée, I15) : ni Tab ni un lecteur d'écran ne doivent l'atteindre.
            if (e.matches("[aria-hidden=true][tabindex='-1']")) continue;
            const names = e.matches("input[type=radio]") ? groups.get(e.form) ?? new Map() : null;
            if (names?.has(e.name)) {
              e.dataset.kbd = names.get(e.name);
              continue;
            }
            e.dataset.kbd = String(items.length);
            if (names) groups.set(e.form, names.set(e.name, e.dataset.kbd));
            items.push(e);
          }
          document.activeElement?.blur();
          return items.map(name);
        }""",
        FOCUSABLE,
    )
    problems = []
    reached: set[str] = set()
    for _ in range(len(expected) + 2):
        screen.keyboard.press("Tab")
        focus = screen.evaluate(_FOCUS_JS)
        if focus["id"] is None or focus["id"] in reached:
            continue
        reached.add(focus["id"])
        ratio = contrast(focus["ring"], focus["around"])
        if focus["width"] < 2 or ratio < 3:
            problems.append(
                f"focus peu visible : {focus['label']} ({focus['width']} px, {ratio:.2f})"
            )
    problems += [
        f"inatteignable : {label}" for i, label in enumerate(expected) if str(i) not in reached
    ]
    return problems
