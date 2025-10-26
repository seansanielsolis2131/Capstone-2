// dashboard.js (revised)
// - Consistent cluster colors across ALL charts
// - Proper, human-readable cluster labels (Regular, Over-reliant, Strategic, Unassigned)
// - Tooltips and numeric axis ticks formatted to 2 decimal places across all charts

let clusterChart, depHist, scatterDP, profileMixChart, yearChart;
let confHist, prodHist, confByClusterChart, prodByClusterChart;
let confByDiscChart, prodByDiscChart, radarChart;
let outcomeClusterBars, outcomeGwaBars, outcomeDepConf, outcomeConfProd;



/* =========================
   Helpers: params, fetch, labels, colors, formatting
   ========================= */
// === Recommendation text logic (cluster-aware, data-driven) ===
function recoSummary(dep, conf, prod, key, gwaBucket) {
  const d = Number.isFinite(dep) ? dep : NaN;
  const c = Number.isFinite(conf) ? conf : NaN;
  const p = Number.isFinite(prod) ? prod : NaN;
  const avgCP = Number.isFinite(c) && Number.isFinite(p) ? (c + p) / 2 : NaN;

  // key meanings in your codebase:
  // "2" = Strategic, "0" = Regular/Balanced, "1" = Over-Reliant
  if (key === "2") {
    if (Number.isFinite(d) && Number.isFinite(avgCP) && d < 0.8 * avgCP) {
      return "Low dependency with strong output—keep using AI to deepen thinking, not to replace it.";
    }
    return "Generally efficient use—push for higher-order tasks and self-checks.";
  }

  if (key === "0") {
    if (Number.isFinite(d) && Number.isFinite(avgCP) && Math.abs(d - avgCP) <= 0.15 * avgCP) {
      return "Balanced use overall—productivity and confidence can rise with clearer limits.";
    }
    return "Mostly balanced—set study checkpoints to avoid creeping over-reliance.";
  }

  // key === "1" Over-Reliant
  if (Number.isFinite(d) && Number.isFinite(avgCP) && d > 1.1 * avgCP) {
    return "High dependency is pulling confidence/productivity down—shift AI to review vs. completion.";
  }
  return "Tendency toward over-reliance—rebuild independence before asking AI.";
}

function recoActions(dep, conf, prod, key, gwaBucket) {
  const d = Number.isFinite(dep) ? dep : 0;
  const c = Number.isFinite(conf) ? conf : 0;
  const p = Number.isFinite(prod) ? prod : 0;
  const actions = [];

  // Helper to push unique lines only
  const pushU = (txt) => { if (!actions.includes(txt)) actions.push(txt); };

  // Cluster-specific bases (ensures diversity)
  if (key === "2") { // Strategic
    pushU("Use AI for counter-arguments and edge cases to stress-test your ideas.");
    pushU("Do a quick self-explanation first, then ask AI to poke holes in it.");
    pushU("Turn AI into a coach: request Socratic questions, not direct answers.");
  } else if (key === "0") { // Regular/Balanced
    pushU("Set checkpoints (outline → draft → review) and use AI only at each checkpoint.");
    pushU("Ask AI to explain concepts in simpler steps, then close it while you solve.");
    pushU("Compare two AI suggestions and justify your own choice in 2–3 sentences.");
  } else { // "1" Over-Reliant
    pushU("Write or solve for 5–10 minutes with no AI, then use AI only to review your work.");
    pushU("Limit AI to outline or checklist; fill the details yourself first.");
    pushU("Track 3 tasks finished without AI this week to build confidence.");
  }

  // Data-driven refinements
  if (d > c) pushU("Try first, then ask AI to review—don’t start with a full answer from AI.");
  if (p < c) pushU("Use AI to plan steps and time blocks, not to finish the task.");
  if (c < 0.9 * (p || 1)) pushU("Reflect for 1–2 minutes on what you learned before reopening AI.");

  // GWA bucket nudge (if lower ranges show up, add a skill-building tip)
  if (typeof gwaBucket === "string" && /2\.01|2\.50|2\.51|3\.00/.test(gwaBucket)) {
    pushU("Practice recalling key ideas from memory first, then verify with AI for accuracy.");
  }

  // Keep top 3 tailored items
  return actions.slice(0, 3);
}

// Friendly label+icon (unchanged logic, kept here for completeness)
function profileLabelAndIcon(profileName) {
  const key = keyFromProfileName(profileName);
  if (key === "2") return { title: "Strategic User", icon: "🧠" };
  if (key === "1") return { title: "Over-Reliant",   icon: "🔴" };
  if (key === "0") return { title: "Regular",        icon: "⚖️" };
  return { title: profileName || "Unassigned", icon: "📊" };
}

function qparams() {
  const stem = document.getElementById("f-stem").value;
  const school = document.getElementById("f-school").value;
  const year = document.getElementById("f-year").value;
  const p75 = document.getElementById("f-p75").checked ? "1" : "";
  const params = new URLSearchParams();
  if (stem) params.set("stem", stem);
  if (school) params.set("school_type", school);
  if (year) params.set("year", year);
  if (p75) params.set("p75_only", "1");
  return params.toString();
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    console.error("API error", res.status, txt);
    return {};
  }
  return await res.json();
}

// Canonical cluster mapping (IDs => labels/colors)
const CLUSTERS = {
  "0": { name: "Regular",       color: "rgba(201, 203, 207, 0.8)" }, // gray
  "1": { name: "Over-reliant",  color: "rgba(255, 99, 132, 0.8)"  }, // red
  "2": { name: "Strategic",     color: "rgba(54, 162, 235, 0.8)"  }, // blue
  "NaN": { name: "Unassigned",  color: "rgba(160, 160, 160, 0.5)" }  // light gray
};

// === helper mapping from profile names to existing cluster keys (keeps colors uniform)
function keyFromProfileName(name) {
  const n = String(name || "").toLowerCase();
  if (n.includes("strategic")) return "2";
  if (n.includes("over")) return "1"; // Over-reliant
  if (n.includes("regular")) return "0";
  return "NaN";
}

function renderCorrelationTable(corr) {
  const host = document.getElementById("corrTable");
  if (!host) return;
  if (!corr || !corr.fields || !corr.matrix) {
    host.innerHTML = '<p>No correlation data available.</p>';
    return;
  }
  const fields = corr.fields;
  const rows = corr.matrix;

  let html = '<table><thead><tr><th></th>';
  fields.forEach(f => html += `<th>${f}</th>`);
  html += '</tr></thead><tbody>';
  rows.forEach((row, i) => {
    html += `<tr><th>${fields[i]}</th>`;
    row.forEach(v => html += `<td>${(v !== null && v !== undefined) ? Number(v).toFixed(2) : ''}</td>`);
    html += '</tr>';
  });
  html += '</tbody></table>';
  host.innerHTML = html;
}

function clusterKey(id) {
  return String(id) in CLUSTERS ? String(id) : "NaN";
}
function clusterName(id) {
  return CLUSTERS[clusterKey(id)].name;
}
function clusterColor(id) {
  return CLUSTERS[clusterKey(id)].color;
}

// Number formatting to 2 decimals
function fmt2(n) {
  return (typeof n === "number" && isFinite(n)) ? n.toFixed(2) : n;
}

// Common tick formatter (forces 2 decimals on numeric axes)
const tick2dp = {
  ticks: {
    callback: (value) => {
      const num = Number(value);
      return isNaN(num) ? value : num.toFixed(2);
    }
  }
};

// Find nearest bin label to a numeric value (for p75 line placement)
function nearestLabel(labels, value) {
  if (!labels || !labels.length) return null;
  let best = labels[0], bestDiff = Math.abs(labels[0] - value);
  for (let i = 1; i < labels.length; i++) {
    const diff = Math.abs(labels[i] - value);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = labels[i];
    }
  }
  return best;
}

/* =========================
   Loaders
   ========================= */

async function loadSummary() {
  const qp = qparams();
  const data = await fetchJSON(`/api/summary?${qp}`);
  document.getElementById("k-total").innerText = data.total_students ?? "—";
  document.getElementById("k-high").innerText = data.high_dependency ?? "—";
  document.getElementById("k-p75").innerText = (data.p75_threshold != null) ? fmt2(data.p75_threshold) : "—";
}

async function loadClusterChart() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/cluster_counts?${qp}`);
  const rows = payload.data || [];

  const labels = rows.map(r => clusterName(r.cluster));
  const values = rows.map(r => r.count);
  // Backgrounds aligned to each row's actual cluster color
  const backgrounds = rows.map(r => clusterColor(r.cluster));

  const ctx = document.getElementById("clusterChart").getContext("2d");
  if (clusterChart) clusterChart.destroy();
  clusterChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Students",
        data: values,
        backgroundColor: backgrounds
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Students: ${fmt2(ctx.parsed.y)}`
          }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        }
      }, 
      scales: {
              y: {
          beginAtZero: true,
          title: { display: true, text: "Number of Students" },
          ...tick2dp
        }
      }
    }
  });
}

async function loadDepHistogram() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/distribution?${qp}`);
  const labels = payload.bins || [];
  const counts = payload.counts || [];
  const p75 = payload.p75;

  const ctx = document.getElementById("depHist").getContext("2d");
  if (depHist) depHist.destroy();
  depHist = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Frequency", data: counts }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => `Dependency: ${fmt2(items[0].label)}`,
            label: (ctx) => `Frequency: ${fmt2(ctx.parsed.y)}`
          }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (v) => (typeof v === "number" ? v.toFixed(2) : v)
        },
        annotation: p75 ? {
          annotations: {
            p75Line: {
              type: 'line',
              xMin: nearestLabel(labels, p75),
              xMax: nearestLabel(labels, p75),
              borderWidth: 2,
              borderColor: 'rgba(255, 99, 132, 0.8)'
            }
          }
        } : {}
      },
      scales: {
        y: { beginAtZero: true, ...tick2dp },
        x: {
          title: { display: true, text: "Total Dependency" },
          ...tick2dp
        }
      }
    }
  });
}

async function loadScatterDP() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/scatter?${qp}`);
  const pts = payload.points || [];

  const byCluster = {};
  for (const p of pts) {
    const key = clusterKey(p.cluster);
    if (!byCluster[key]) byCluster[key] = [];
    byCluster[key].push({ x: p.x, y: p.y });
  }

  const datasets = Object.keys(byCluster).map(k => ({
    label: clusterName(k),
    data: byCluster[k],
    showLine: false,
    pointRadius: 3,
    backgroundColor: clusterColor(k)
  }));

  const ctx = document.getElementById("scatterDP").getContext("2d");
  if (scatterDP) scatterDP.destroy();
  scatterDP = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true,
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.raw;
              return `${ctx.dataset.label}: (${fmt2(v.x)}, ${fmt2(v.y)})`;
            }
          }
        },
        datalabels: {
          display: false
        },
      },
      scales: {
        x: { title: { display: true, text: "Total Dependency" }, ...tick2dp },
        y: { title: { display: true, text: "Productivity (mean)" }, min: 1, max: 5, ...tick2dp }
      }
    }
  });
}

async function loadProfileMix() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/profile_mix?${qp}`);
  const rows = payload.groups || [];

  const disciplines = [...new Set(rows.map(r => r.discipline))];
  const profiles = ["Strategic", "Regular", "Over-reliant"]; // fixed order, names not IDs

  const colorByProfile = {
    "Strategic": CLUSTERS["2"].color,     // blue
    "Regular": CLUSTERS["0"].color,       // gray
    "Over-reliant": CLUSTERS["1"].color   // red
  };

  const datasets = profiles.map(profile => {
    const data = disciplines.map(disc => {
      const row = rows.find(r => r.discipline === disc && r.profile === profile);
      return row ? row.percent : 0;
    });
    return {
      label: profile,
      data,
      backgroundColor: colorByProfile[profile],
      stack: "profiles"
    };
  });

  const ctx = document.getElementById("profileMix").getContext("2d");
  if (profileMixChart) profileMixChart.destroy();
  profileMixChart = new Chart(ctx, {
    type: "bar",
    data: { labels: disciplines, datasets },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${fmt2(ctx.parsed.y)}%`
          }
        },
        legend: { position: "top" },
        datalabels: {
          display: true,
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, max: 100, title: { display: true, text: "Percentage" }, ...tick2dp }
      }
    }
  });
}

async function loadYearBreakdown() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/year_breakdown?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => r.year);
  const values = rows.map(r => r.avg_dependency);

  const ctx = document.getElementById("yearBreakdown").getContext("2d");
  if (yearChart) yearChart.destroy();
  yearChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Average Dependency",
        data: values,
        backgroundColor: "rgba(75, 192, 192, 0.8)"
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Avg Dependency: ${fmt2(ctx.parsed.y)}`
          }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          grace: "10%",
          title: { display: true, text: "Average Dependency Score" },
          ...tick2dp
        },
        x: { title: { display: true, text: "Year Level" } }
      }
    }
  });
}

async function loadConfidenceHist() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/confidence_distribution?${qp}`);
  const labels = payload.bins || [];
  const counts = payload.counts || [];

  const ctx = document.getElementById("confHist").getContext("2d");
  if (confHist) confHist.destroy();
  confHist = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Students",
        data: counts,
        backgroundColor: "rgba(153, 102, 255, 0.8)"
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => `Confidence: ${fmt2(items[0].label)}`,
            label: (ctx) => `Students: ${fmt2(ctx.parsed.y)}`
          }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        x: { title: { display: true, text: "Confidence Score (1–5)" }, ...tick2dp },
        y: { beginAtZero: true, grace: "10%", title: { display: true, text: "Count" }, ...tick2dp }
      }
    }
  });
}

async function loadProductivityHist() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/productivity_distribution?${qp}`);
  const labels = payload.bins || [];
  const counts = payload.counts || [];

  const ctx = document.getElementById("prodHist").getContext("2d");
  if (prodHist) prodHist.destroy();
  prodHist = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Students",
        data: counts,
        backgroundColor: "rgba(255, 159, 64, 0.8)"
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => `Productivity: ${fmt2(items[0].label)}`,
            label: (ctx) => `Students: ${fmt2(ctx.parsed.y)}`
          }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        x: { title: { display: true, text: "Productivity Score (1–5)" }, ...tick2dp },
        y: { beginAtZero: true, grace: "10%", title: { display: true, text: "Count" }, ...tick2dp }
      }
    }
  });
}

async function loadConfByCluster() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/confidence_by_cluster?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => clusterName(r.cluster));
  const values = rows.map(r => r.avg_confidence);
  const backgrounds = rows.map(r => clusterColor(r.cluster));

  const ctx = document.getElementById("confByCluster").getContext("2d");
  if (confByClusterChart) confByClusterChart.destroy();
  confByClusterChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Avg Confidence",
        data: values,
        backgroundColor: backgrounds
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => `Confidence: ${fmt2(ctx.parsed.y)}` }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Confidence (1–5)" }, ...tick2dp }
      }
    }
  });
}

async function loadProdByCluster() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/productivity_by_cluster?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => clusterName(r.cluster));
  const values = rows.map(r => r.avg_productivity);
  const backgrounds = rows.map(r => clusterColor(r.cluster));

  const ctx = document.getElementById("prodByCluster").getContext("2d");
  if (prodByClusterChart) prodByClusterChart.destroy();
  prodByClusterChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Avg Productivity",
        data: values,
        backgroundColor: backgrounds
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => `Productivity: ${fmt2(ctx.parsed.y)}` }
        },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Productivity (1–5)" }, ...tick2dp }
      }
    }
  });
}

async function loadConfByDiscipline() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/confidence_by_discipline?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => r.discipline);
  const values = rows.map(r => r.avg_confidence);

  const ctx = document.getElementById("confByDisc").getContext("2d");
  if (confByDiscChart) confByDiscChart.destroy();
  confByDiscChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Avg Confidence",
        data: values,
        backgroundColor: "rgba(153, 102, 255, 0.8)"
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `Confidence: ${fmt2(ctx.parsed.y)}` } },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Confidence (1–5)" }, ...tick2dp }
      }
    }
  });
}

async function loadProdByDiscipline() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/productivity_by_discipline?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => r.discipline);
  const values = rows.map(r => r.avg_productivity);

  const ctx = document.getElementById("prodByDisc").getContext("2d");
  if (prodByDiscChart) prodByDiscChart.destroy();
  prodByDiscChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Avg Productivity",
        data: values,
        backgroundColor: "rgba(255, 159, 64, 0.8)"
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `Productivity: ${fmt2(ctx.parsed.y)}` } },
        datalabels: {
          display: true,
          align: "end",
          anchor: "end",
          color: "#333",
          font: { size: 11, weight: "bold" },
          formatter: (value) => value.toFixed(2)
        },
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Productivity (1–5)" }, ...tick2dp }
      }
    }
  });
}

async function loadRadarChart() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/cluster_centroids?${qp}`);
  const rows = payload.clusters || [];

  const labels = ["Dependency", "Confidence", "Productivity"];

  // Build datasets using canonical color & proper label
  const datasets = rows.map((r) => {
    const key = clusterKey(r.cluster);
    return {
      label: clusterName(key),
      data: [r.dependency, r.confidence, r.productivity],
      backgroundColor: clusterColor(key).replace("0.8", "0.6").replace("0.5", "0.6"),
      borderColor: clusterColor(key).replace("0.6", "1").replace("0.5", "1"),
      borderWidth: 2,
      fill: true
    };
  });

  const ctx = document.getElementById("radarChart").getContext("2d");
  if (radarChart) radarChart.destroy();
  radarChart = new Chart(ctx, {
    type: "radar",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const vals = ctx.raw || [];
              // Chart.js provides single value here; format displayed value to 2dp
              return `${ctx.dataset.label}: ${fmt2(ctx.formattedValue)}`;
            }
          }
        },
        datalabels: {
          display: false
        },
      },
      scales: {
        r: {
          beginAtZero: true,
          suggestedMax: 5,
          ticks: {
            stepSize: 1,
            callback: (value) => Number(value).toFixed(2)
          }
        }
      }
    }
  });
}

function renderRecommendations(labels, byName) {
  const host = document.getElementById("reco-grid");
  if (!host) return; // silently exit if container not found

  // Build card HTML per profile using snapshot fields you already fetch
  const cards = labels.map((name) => {
    const r = byName[name] || {};

    // Metrics available from your /api/outcome-mapping snapshot
    const dep = Number(r.mean_dependency ?? r.mean_total_dependency ?? NaN); // backend may name it either way
    const conf = Number(r.mean_confidence ?? NaN);
    const prod = Number(r.mean_productivity ?? NaN);
    const gwaBucket = (r.mode_gwa_bucket ?? "").toString();
    const gwaPct = Number(r.mode_gwa_pct ?? NaN);

    const { title, icon } = profileLabelAndIcon(name);
    const key = keyFromProfileName(name);
    const color = clusterColor(key);

    const chips = [
      Number.isFinite(r.mean_gwa) ? `Avg GWA: <strong>${fmt2(r.mean_gwa)}</strong>` : "",
      Number.isFinite(dep) ? `Dep: <strong>${fmt2(dep)}</strong>` : "",
      Number.isFinite(conf) ? `Conf: <strong>${fmt2(conf)}</strong>` : "",
      Number.isFinite(prod) ? `Prod: <strong>${fmt2(prod)}</strong>` : "",
      gwaBucket ? `GWA Mode: <strong>${gwaBucket}</strong>${Number.isFinite(gwaPct) ? ` · ${fmt2(gwaPct)}%` : ""}` : ""
    ].filter(Boolean).map(s => `<span class="reco-chip">${s}</span>`).join("");

    const summary = recoSummary(dep, conf, prod, key, gwaBucket);
    const actions = recoActions(dep, conf, prod, key, gwaBucket).map(a => `<li>${a}</li>`).join("");

    // Card markup (kept CSS classes consistent with what we used earlier—safe to reuse)
    return `
      <div class="reco-card" style="border-color:${color.replace('0.8','1')};background:${color.replace('0.8','0.08').replace('0.5','0.08')}">
        <div class="reco-head">
          <div class="reco-icon">${icon}</div>
          <div class="reco-title">${title}</div>
        </div>
        <div class="reco-chips">${chips}</div>
        <div class="reco-body">${summary}</div>
        <ul class="reco-actions">${actions}</ul>
      </div>
    `;
  });

  host.innerHTML = cards.join("");
}

async function loadOutcomeMapping() {
  const payload = await fetchJSON('/api/outcome-mapping');
  const data = (payload && payload.data) ? payload.data : null;
  if (!data) { console.error('Outcome mapping: no data'); return; }

  const snapshot = Array.isArray(data.snapshot) ? data.snapshot : [];
  const correlation = data.correlation || null;
  const points = data.points || { dep_vs_conf: [], conf_vs_prod: [] };

  // Dynamic labels from API
  const labels = snapshot
    .map(r => String(r.profile ?? '').trim())
    .filter(s => s.length > 0);

  const byName = Object.fromEntries(snapshot.map(r => [String(r.profile ?? '').trim(), r]));

  // Confidence & Productivity means
  const confVals = labels.map(n => Number(byName[n]?.mean_confidence ?? NaN));
  const prodVals = labels.map(n => Number(byName[n]?.mean_productivity ?? NaN));

  // Canonical cluster colors
  const colors = labels.map(n => {
    const key = keyFromProfileName(n);
    return clusterColor(key) || CLUSTERS["NaN"].color;
  });

  // Dominant GWA bucket + % per profile (from backend)
  const modeBuckets = labels.map(n => (byName[n]?.mode_gwa_bucket ?? '').toString());
  const modePcts    = labels.map(n => Number(byName[n]?.mode_gwa_pct ?? NaN));

  // Optional fixed colors per GWA bucket (consistent look)
// Use the same canonical cluster colors for consistency
const gwaBarColors = labels.map(n => {
  const key = keyFromProfileName(n); // "0"=Regular, "1"=Over-reliant, "2"=Strategic
  return clusterColor(key) || CLUSTERS["NaN"].color;
});

  // Destroy existing charts if present
  if (outcomeClusterBars) outcomeClusterBars.destroy();
  if (outcomeGwaBars) outcomeGwaBars.destroy();
  if (outcomeDepConf) outcomeDepConf.destroy();
  if (outcomeConfProd) outcomeConfProd.destroy();

  const CONF_COLOR = '#6C8CF5';   // Confidence (blue)
  const PROD_COLOR = '#F4A261';   // Productivity (orange)
  
  // Grouped bars: Confidence & Productivity
  const ctx1 = document.getElementById('chartClusterBars')?.getContext('2d');
  if (ctx1 && labels.length) {
outcomeClusterBars = new Chart(ctx1, {
  type: 'bar',
  data: {
    labels,
    datasets: [
      { label: 'Mean Confidence', data: confVals, backgroundColor: CONF_COLOR, borderRadius: 6 },
      { label: 'Mean Productivity', data: prodVals, backgroundColor: PROD_COLOR, borderRadius: 6 }
    ]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'top' },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toFixed(2)}` } },
      datalabels: {
        display: true,
        anchor: 'end', align: 'end',
        color: '#333', font: { size: 11, weight: 'bold' },
        formatter: v => (typeof v === 'number' ? v.toFixed(2) : '')
      }
    },
    scales: { y: { beginAtZero: true, min: 0, max: 5 } }
  }
});
  }

  // Dominant GWA Range by Cluster (mode bucket + % share)
  const ctx2 = document.getElementById('chartGwaBars')?.getContext('2d');
  if (ctx2 && labels.length) {
    outcomeGwaBars = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Dominant GWA Range %',
          data: modePcts,
          backgroundColor: gwaBarColors
        }]
      },
      options: {
  responsive: true,
  plugins: {
    // hide legend so no red box appears
    legend: { display: false },
    // show a clear chart title instead
    title: {
      display: true,
      text: 'Dominant GWA Range by Cluster (Mode, % Share)'
    },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const bucket = modeBuckets[ctx.dataIndex] || '—';
          return `${bucket} • ${ctx.parsed.y.toFixed(2)}%`;
        }
      }
    },
    datalabels: {
      display: true,
      anchor: 'end', align: 'end',
      color: '#333', font: { size: 11, weight: 'bold' },
      formatter: (_val, ctx) => modeBuckets[ctx.dataIndex] || ''
    }
  },
  scales: {
    y: {
      beginAtZero: true, min: 0, max: 100,
      title: { display: true, text: 'Share of Respondents (%)' },
      grid: { color: 'rgba(0,0,0,0.05)' }
    }
  }
}

    });
  }

  // Scatter: Total Dependency vs Confidence
  const byProfA = {};
  (points.dep_vs_conf || []).forEach(p => {
    const name = String(p.profile ?? '').trim();
    if (!byProfA[name]) byProfA[name] = [];
    byProfA[name].push({ x: Number(p.x), y: Number(p.y) });
  });

  const ctx3 = document.getElementById('chartDepConf')?.getContext('2d');
  if (ctx3 && Object.keys(byProfA).length) {
    outcomeDepConf = new Chart(ctx3, {
      type: 'scatter',
      data: {
        datasets: Object.keys(byProfA).map(name => {
          const key = keyFromProfileName(name);
          return {
            label: name || 'Unassigned',
            data: byProfA[name],
            pointRadius: 3,
            backgroundColor: clusterColor(key)
          };
        })
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' },
          datalabels: { display: false }
        },
        scales: {
          x: { title: { display: true, text: 'Total Dependency' } },
          y: { title: { display: true, text: 'Confidence' }, min: 0, max: 5 }
        }
      }
    });
  }

  // Scatter: Confidence vs Productivity
  const byProfB = {};
  (points.conf_vs_prod || []).forEach(p => {
    const name = String(p.profile ?? '').trim();
    if (!byProfB[name]) byProfB[name] = [];
    byProfB[name].push({ x: Number(p.x), y: Number(p.y) });
  });

  const ctx4 = document.getElementById('chartConfProd')?.getContext('2d');
  if (ctx4 && Object.keys(byProfB).length) {
    outcomeConfProd = new Chart(ctx4, {
      type: 'scatter',
      data: {
        datasets: Object.keys(byProfB).map(name => {
          const key = keyFromProfileName(name);
          return {
            label: name || 'Unassigned',
            data: byProfB[name],
            pointRadius: 3,
            backgroundColor: clusterColor(key)
          };
        })
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' },
          datalabels: { display: false }
        },
        scales: {
          x: { title: { display: true, text: 'Confidence' }, min: 0, max: 5 },
          y: { title: { display: true, text: 'Productivity' }, min: 0, max: 5 }
        }
      }
    });
  }

  renderRecommendations(labels, byName);

  // Correlation table
  renderCorrelationTable(correlation);
}

/* =========================
   Orchestration
   ========================= */

Chart.register(ChartDataLabels);

async function refreshAll() {
  await loadSummary();
  await loadClusterChart();
  await loadDepHistogram();
  await loadScatterDP();
  await loadProfileMix();
  await loadYearBreakdown();
  await loadConfidenceHist();
  await loadProductivityHist();
  await loadConfByCluster();
  await loadProdByCluster();
  await loadConfByDiscipline();
  await loadProdByDiscipline();
  await loadRadarChart();
  await loadOutcomeMapping(); // NEW
}

document.getElementById("apply").addEventListener("click", refreshAll);
refreshAll();