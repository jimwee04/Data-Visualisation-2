// Shared look for every chart, so the specs only describe data and encodings.
const FONT = "Public Sans, system-ui, sans-serif";

const theme = {
  font: FONT,
  background: null,
  view: { stroke: null },
  axis: {
    labelColor: "#4B5569",
    titleColor: "#4B5569",
    labelFontSize: 12,
    titleFontSize: 13,
    titleFontWeight: 500,
    gridColor: "#E7E2DE",
    domain: false,
    ticks: false,
    labelPadding: 6
  },
  legend: {
    labelColor: "#4B5569",
    titleColor: "#2F3A55",
    labelFontSize: 12,
    titleFontSize: 12,
    titleFontWeight: 600,
    labelLimit: 320
  },
  header: { labelFont: FONT },
  text: { font: FONT, color: "#2F3A55" },
  title: { color: "#2F3A55" }
};

// KPI micro-charts sit on the dark hero, so they get no padding and light text.
const kpiTheme = {
  font: FONT,
  background: null,
  padding: 0,
  view: { stroke: null },
  text: { font: FONT }
};

const charts = {
  fig1: "specs/1_choropleth_state_value.vg.json",
  fig2: "specs/2_symbol_map_food_source.vg.json",
  fig3: "specs/3_dumbbell_self_sufficiency.vg.json",
  fig4: "specs/4_waffle_supply_balance.vg.json",
  fig5: "specs/5_waterfall_dairy_buffer.vg.json",
  fig6: "specs/6_flow_map_trade.vg.json",
  fig7: "specs/7_sankey_export_destinations.vg.json",
  fig8: "specs/8_line_per_person_trend.vg.json",
  fig9: "specs/9_boxplot_retail_shock.vg.json",
  fig10: "specs/10_heatmap_retail_seasons.vg.json",
  fig11: "specs/11_dumbbell_supply_vs_sales.vg.json"
};

const kpis = {
  kpi1: "specs/kpi_1_cereals_surplus.vl.json",
  kpi2: "specs/kpi_2_seafood_gap.vl.json",
  kpi3: "specs/kpi_3_chicken_vs_beef.vl.json",
  kpi4: "specs/kpi_4_state_value.vl.json"
};

// Faceted charts have fixed cell sizes and can't use the container width,
// so their cells are sized to fill the card once, before embedding.
const fitToWidth = {
  // Ten waffles of 10 squares with 28px between them and ~32px of chart padding:
  // five per row when they fit at the 11px minimum square, otherwise two, so rows always split evenly;
  // then squares grow to fill the row.
  fig4: (spec, w) => {
    const cols = w >= 5 * 110 + 4 * 28 + 32 ? 5 : 2;
    const square = Math.max(11, Math.min(20, Math.floor((w - 32 - 28 * (cols - 1)) / (cols * 10))));
    spec.columns = cols;
    spec.spec.width.step = spec.spec.height.step = square;
  },
  // 12 month columns after ~64px of year labels and padding.
  // Full month names need ~66px; narrower columns tilt them instead of abbreviating.
  fig10: (spec, w) => {
    const step = Math.max(21, Math.floor((w - 64) / 12));
    spec.spec.width.step = step;
    if (step < 66) Object.assign(spec.spec.encoding.x.axis, { labelAngle: -45, labelAlign: "right" });
  }
};

const views = {};

// Specs and their data are resolved against this script's folder (public/), not the page,
// so the same script works whether the page sits at the repo root or inside public/.
const BASE = new URL("../", document.currentScript.src).href;
const loader = vega.loader({ baseURL: BASE });

function embed(id, path, config) {
  const url = new URL(path, BASE).href;
  const fit = fitToWidth[id];
  const spec = fit
    ? fetch(url).then((r) => r.json()).then((s) => { fit(s, document.getElementById(id).clientWidth); return s; })
    : Promise.resolve(url);
  return spec
    .then((s) => vegaEmbed("#" + id, s, { actions: false, renderer: "svg", config, loader }))
    .then((result) => {
      views[id] = result.view;
      // Apply any icon choice made while the chart was still loading.
      const picked = document.querySelector(`.icon-filter[data-chart="${id}"] button[aria-checked="true"]`);
      if (picked) result.view.signal(picked.parentElement.dataset.param, picked.dataset.value).runAsync();
    })
    .catch((err) => {
      document.getElementById(id).textContent = "Chart failed to load: " + err.message;
      console.error(id, err);
    });
}

for (const [id, spec] of Object.entries(charts)) embed(id, spec, theme);
for (const [id, spec] of Object.entries(kpis)) embed(id, spec, kpiTheme);

// ---------------------------------------------------------------- icon filters
// Each .icon-filter is a radio group of labelled icon buttons that sets one chart parameter.
// The first button is selected to match the spec's default value.
document.querySelectorAll(".icon-filter").forEach((group) => {
  const buttons = [...group.querySelectorAll("button")];

  function select(button, focus) {
    buttons.forEach((b) => {
      const on = b === button;
      b.setAttribute("aria-checked", on);
      b.tabIndex = on ? 0 : -1;
    });
    if (focus) button.focus();
    const view = views[group.dataset.chart];
    if (view) view.signal(group.dataset.param, button.dataset.value).runAsync();
  }

  buttons.forEach((b, i) => {
    b.addEventListener("click", () => select(b, false));
    b.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!step) return;
      e.preventDefault();
      select(buttons[(i + step + buttons.length) % buttons.length], true);
    });
  });
  select(buttons[0], false);
});

// ---------------------------------------------------------------- stage rail
// The rail is a top bar: it marks the stage being read, fills the track up to it,
// and slides in once the hero has scrolled away.
(function stageRail() {
  const rail = document.querySelector(".rail");
  if (!rail) return;
  const list = rail.querySelector(".rail-list");
  const track = rail.querySelector(".rail-track");
  const items = [...rail.querySelectorAll(".rail-item")];
  const sections = items.map((a) => document.querySelector(a.getAttribute("href")));
  const hero = document.querySelector(".hero");
  let lastCurrent = -1;

  // Stretch the track between the first and last dot centres.
  function placeTrack() {
    const box = list.getBoundingClientRect();
    const centreX = (a) => {
      const r = a.querySelector(".rail-dot").getBoundingClientRect();
      return r.left + r.width / 2 - box.left + list.scrollLeft;
    };
    const first = centreX(items[0]), last = centreX(items[items.length - 1]);
    track.style.left = first + "px";
    track.style.width = last - first + "px";
  }

  function update() {
    const line = window.innerHeight * 0.4;
    let current = -1;
    sections.forEach((s, i) => {
      if (s.getBoundingClientRect().top <= line) current = i;
    });

    // Progress = stages passed + how far through the current one, so the fill lands on its dot.
    let progress = 0;
    if (current >= 0) {
      const r = sections[current].getBoundingClientRect();
      const within = Math.min(Math.max((line - r.top) / r.height, 0), 1);
      progress = Math.min((current + within) / (sections.length - 1), 1);
    }
    rail.style.setProperty("--progress", progress);

    items.forEach((a, i) => {
      a.classList.toggle("is-done", i < current);
      a.classList.toggle("is-current", i === current);
      if (i === current) a.setAttribute("aria-current", "step");
      else a.removeAttribute("aria-current");
    });

    // Keep the current stage visible when the bar is narrow enough to scroll.
    if (current !== lastCurrent && current >= 0 && list.scrollWidth > list.clientWidth) {
      const a = items[current];
      list.scrollLeft = a.offsetLeft - (list.clientWidth - a.offsetWidth) / 2;
    }
    lastCurrent = current;

    document.body.classList.toggle("past-hero", hero.getBoundingClientRect().bottom < 0);
  }

  let ticking = false;
  window.addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { update(); ticking = false; });
  }, { passive: true });
  window.addEventListener("resize", () => { placeTrack(); update(); });
  document.fonts.ready.then(placeTrack);

  placeTrack();
  update();
})();
