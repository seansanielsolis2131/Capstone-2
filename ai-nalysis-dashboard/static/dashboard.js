let clusterChart, depHist;

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


async function loadSummary() {
  const qp = qparams();
  const data = await fetchJSON(`/api/summary?${qp}`);
  document.getElementById("k-total").innerText = data.total_students ?? "—";
  document.getElementById("k-high").innerText = data.high_dependency ?? "—";
  document.getElementById("k-p75").innerText = data.p75_threshold != null ? data.p75_threshold.toFixed(2) : "—";
}

async function loadClusterChart() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/cluster_counts?${qp}`);
  const rows = payload.data || [];

  function clusterName(id) {
    const map = {
      "0": "Regular",
      "1": "Over-reliant",
      "2": "Strategic",
      "NaN": "Unassigned"
    };
    return map[String(id)] || `Cluster ${id}`;
  }

  const labels = rows.map(r => clusterName(r.cluster));
  const values = rows.map(r => r.count);

  const ctx = document.getElementById("clusterChart").getContext("2d");
  if (clusterChart) clusterChart.destroy();
  clusterChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Students",
        data: values,
        backgroundColor: [
          "rgba(201, 203, 207, 0.8)", // Regular (gray)
          "rgba(255, 99, 132, 0.8)",  // Over-reliant (red)
          "rgba(54, 162, 235, 0.8)",  // Strategic (blue)
          "rgba(160, 160, 160, 0.5)"  // Unassigned
        ].slice(0, labels.length)
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "Number of Students" } } }
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
        annotation: p75 ? {
          annotations: {
            p75Line: {
              type: 'line',
              xMin: nearestLabel(labels, p75),
              xMax: nearestLabel(labels, p75),
              borderWidth: 2
            }
          }
        } : {}
      },
      scales: { y: { beginAtZero: true }, x: { title: { display: true, text: "Total Dependency" } } }
    }
  });
}

let scatterDP;

function colorForCluster(c) {
  const map = {
    "0": "rgba(54, 162, 235, 0.8)",
    "1": "rgba(255, 99, 132, 0.8)",
    "2": "rgba(255, 205, 86, 0.8)",
    "NaN": "rgba(201, 203, 207, 0.8)"
  };
  return map[String(c)] || "rgba(100, 100, 100, 0.8)";
}

async function loadScatterDP() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/scatter?${qp}`);
  const pts = payload.points || [];

  const byCluster = {};
  for (const p of pts) {
    const key = String(p.cluster);
    if (!byCluster[key]) byCluster[key] = [];
    byCluster[key].push({ x: p.x, y: p.y });
  }

  const datasets = Object.keys(byCluster).map(k => ({
    label: `Cluster ${k}`,
    data: byCluster[k],
    showLine: false,
    pointRadius: 3,
    backgroundColor: colorForCluster(k),
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
              return `(${v.x.toFixed(1)}, ${v.y.toFixed(2)})`;
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: "Total Dependency" } },
        y: { title: { display: true, text: "Productivity (mean)" }, min: 1, max: 5 }
      }
    }
  });
}

function nearestLabel(labels, value) {
  if (!labels || !labels.length) return null;
  let best = labels[0], bestIdx = 0, bestDiff = Math.abs(labels[0] - value);
  for (let i = 1; i < labels.length; i++) {
    const diff = Math.abs(labels[i] - value);
    if (diff < bestDiff) { bestDiff = diff; best = labels[i]; bestIdx = i; }
  }

  return best;
}
let profileMixChart;

async function loadProfileMix() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/profile_mix?${qp}`);
  const rows = payload.groups || [];

  const disciplines = [...new Set(rows.map(r => r.discipline))];
  const profiles = ["Strategic", "Regular", "Over-reliant"]; // fixed order

  const datasets = profiles.map(profile => {
    const data = disciplines.map(disc => {
      const row = rows.find(r => r.discipline === disc && r.profile === profile);
      return row ? row.percent : 0;
    });
    const colors = {
      "Strategic": "rgba(54, 162, 235, 0.8)",
      "Regular": "rgba(201, 203, 207, 0.8)",
      "Over-reliant": "rgba(255, 99, 132, 0.8)"
    };
    return {
      label: profile,
      data,
      backgroundColor: colors[profile] || "gray",
      stack: "profiles"
    };
  });

  const ctx = document.getElementById("profileMix").getContext("2d");
  if (profileMixChart) profileMixChart.destroy();
  profileMixChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: disciplines,
      datasets
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
          }
        },
        legend: { position: "top" }
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, max: 100, title: { display: true, text: "Percentage" } }
      }
    }
  });
}

let yearChart;

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
            label: ctx => `Avg Dependency: ${ctx.parsed.y.toFixed(2)}`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: "Average Dependency Score" }
        },
        x: {
          title: { display: true, text: "Year Level" }
        }
      }
    }
  });
}

let confHist, prodHist;

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
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Confidence Score (1–5)" } },
        y: { beginAtZero: true, title: { display: true, text: "Count" } }
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
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Productivity Score (1–5)" } },
        y: { beginAtZero: true, title: { display: true, text: "Count" } }
      }
    }
  });
}

let confByClusterChart, prodByClusterChart;

async function loadConfByCluster() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/confidence_by_cluster?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => `Cluster ${r.cluster}`);
  const values = rows.map(r => r.avg_confidence);

  const ctx = document.getElementById("confByCluster").getContext("2d");
  if (confByClusterChart) confByClusterChart.destroy();
  confByClusterChart = new Chart(ctx, {
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
        tooltip: {
          callbacks: { label: ctx => `Confidence: ${ctx.parsed.y.toFixed(2)}` }
        }
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Confidence (1–5)" } }
      }
    }
  });
}

async function loadProdByCluster() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/productivity_by_cluster?${qp}`);
  const rows = payload.groups || [];

  const labels = rows.map(r => `Cluster ${r.cluster}`);
  const values = rows.map(r => r.avg_productivity);

  const ctx = document.getElementById("prodByCluster").getContext("2d");
  if (prodByClusterChart) prodByClusterChart.destroy();
  prodByClusterChart = new Chart(ctx, {
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
        tooltip: {
          callbacks: { label: ctx => `Productivity: ${ctx.parsed.y.toFixed(2)}` }
        }
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Productivity (1–5)" } }
      }
    }
  });
}

let confByDiscChart, prodByDiscChart;

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
        tooltip: {
          callbacks: { label: ctx => `Confidence: ${ctx.parsed.y.toFixed(2)}` }
        }
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Confidence (1–5)" } }
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
        tooltip: {
          callbacks: { label: ctx => `Productivity: ${ctx.parsed.y.toFixed(2)}` }
        }
      },
      scales: {
        y: { beginAtZero: true, min: 1, max: 5, title: { display: true, text: "Productivity (1–5)" } }
      }
    }
  });
}

let radarChart;

async function loadRadarChart() {
  const qp = qparams();
  const payload = await fetchJSON(`/api/cluster_centroids?${qp}`);
  const rows = payload.clusters || [];

  const labels = ["Dependency", "Confidence", "Productivity"];

  const colors = [
    "rgba(54, 162, 235, 0.6)", // cluster 0
    "rgba(255, 99, 132, 0.6)", // cluster 1
    "rgba(255, 205, 86, 0.6)", // cluster 2
    "rgba(201, 203, 207, 0.6)" // NaN or extra
  ];

  const datasets = rows.map((r, i) => ({
    label: `Cluster ${r.cluster}`,
    data: [r.dependency, r.confidence, r.productivity],
    backgroundColor: colors[i % colors.length],
    borderColor: colors[i % colors.length].replace("0.6", "1"),
    borderWidth: 2,
    fill: true
  }));

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
            label: ctx => `${ctx.dataset.label}: ${ctx.formattedValue}`
          }
        }
      },
      scales: {
        r: {
          beginAtZero: true,
          suggestedMax: 5,
          ticks: { stepSize: 1 }
        }
      }
    }
  });
}

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
}

document.getElementById("apply").addEventListener("click", refreshAll);

refreshAll();
