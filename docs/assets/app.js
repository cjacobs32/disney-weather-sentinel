(() => {
  "use strict";

  const config = window.DWS_CONFIG;
  const STORAGE_KEY = "disney-weather-sentinel.snapshots.v4";
  const DAILY_FORECAST_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "sunshine_duration",
  ].join(",");
  const DAILY_ARCHIVE_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "sunshine_duration",
  ].join(",");
  const SEASONAL_FIELDS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
  ].join(",");

  const endpoints = {
    forecast: "https://api.open-meteo.com/v1/forecast",
    archive: "https://archive-api.open-meteo.com/v1/archive",
    seasonal: "https://seasonal-api.open-meteo.com/v1/seasonal",
    noaa: "https://www.ncei.noaa.gov/access/services/data/v1",
  };

  const weatherCodes = {
    0: "Despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna leve",
    53: "Llovizna",
    55: "Llovizna intensa",
    61: "Lluvia leve",
    63: "Lluvia",
    65: "Lluvia intensa",
    80: "Chaparrones leves",
    81: "Chaparrones",
    82: "Chaparrones intensos",
    95: "Tormenta",
    96: "Tormenta con granizo leve",
    99: "Tormenta con granizo",
  };

  const elements = {
    form: document.querySelector("#query-form"),
    mode: document.querySelector("#query-mode"),
    start: document.querySelector("#start-date"),
    end: document.querySelector("#end-date"),
    historyYears: document.querySelector("#history-years"),
    validation: document.querySelector("#validation-message"),
    loading: document.querySelector("#loading"),
    loadingDetail: document.querySelector("#loading-detail"),
    resultPanel: document.querySelector("#result-panel"),
    resultTitle: document.querySelector("#result-title"),
    resultKicker: document.querySelector("#result-kicker"),
    resultContent: document.querySelector("#result-content"),
    saveCapture: document.querySelector("#save-capture"),
    exportJson: document.querySelector("#export-json"),
    exportMd: document.querySelector("#export-md"),
    capturesList: document.querySelector("#captures-list"),
    importFile: document.querySelector("#import-file"),
    comparisonPanel: document.querySelector("#comparison-panel"),
    comparisonContent: document.querySelector("#comparison-content"),
    exportComparison: document.querySelector("#export-comparison"),
    actionsLink: document.querySelector("#actions-link"),
    repositoryLatest: document.querySelector("#repository-latest"),
    latestContent: document.querySelector("#latest-content"),
  };

  let currentResult = null;
  let currentMarkdown = "";
  let currentComparison = null;

  function parseIso(value) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, day, 12));
  }

  function toIso(value) {
    return value.toISOString().slice(0, 10);
  }

  function addDays(isoDate, amount) {
    const value = parseIso(isoDate);
    value.setUTCDate(value.getUTCDate() + amount);
    return toIso(value);
  }

  function daysInclusive(start, end) {
    return Math.round((parseIso(end) - parseIso(start)) / 86400000) + 1;
  }

  function compareIso(left, right) {
    return left.localeCompare(right);
  }

  function orlandoToday() {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: config.timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = Object.fromEntries(
      formatter.formatToParts(new Date()).filter((part) => part.type !== "literal").map((part) => [part.type, part.value]),
    );
    return `${parts.year}-${parts.month}-${parts.day}`;
  }

  function dateLabel(isoDate) {
    return new Intl.DateTimeFormat("es-AR", {
      timeZone: "UTC",
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(parseIso(isoDate));
  }

  function formatNumber(value, digits = 1) {
    return value === null || value === undefined || Number.isNaN(value)
      ? "—"
      : Number(value).toLocaleString("es-AR", {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        });
  }

  function average(values) {
    const usable = values.filter((value) => Number.isFinite(value));
    return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
  }

  function percentile(values, ratio) {
    const ordered = values.filter(Number.isFinite).sort((a, b) => a - b);
    if (!ordered.length) return null;
    if (ordered.length === 1) return ordered[0];
    const position = (ordered.length - 1) * ratio;
    const lower = Math.floor(position);
    const upper = Math.min(lower + 1, ordered.length - 1);
    const fraction = position - lower;
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction;
  }

  function condition(code) {
    return code === null || code === undefined ? "—" : (weatherCodes[code] || `Código ${code}`);
  }

  function commonParams() {
    return {
      latitude: config.latitude,
      longitude: config.longitude,
      timezone: config.timezone,
      temperature_unit: "celsius",
      wind_speed_unit: "kmh",
      precipitation_unit: "mm",
    };
  }

  async function rawJsonFetch(url, parameters) {
    const query = new URLSearchParams();
    Object.entries(parameters).forEach(([key, value]) => query.set(key, String(value)));
    const response = await fetch(`${url}?${query.toString()}`, {
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.error || payload?.errorMessage) {
      throw new Error(payload?.reason || payload?.errorMessage || `Error HTTP ${response.status}`);
    }
    return payload;
  }

  async function apiFetch(url, parameters) {
    const payload = await rawJsonFetch(url, parameters);
    if (!payload?.daily) throw new Error("La API no devolvió datos diarios.");
    return payload;
  }

  function parseDaily(payload) {
    const daily = payload.daily;
    return daily.time.map((time, index) => ({
      date: time,
      weather_code: daily.weather_code?.[index] ?? null,
      temperature_max_c: daily.temperature_2m_max?.[index] ?? null,
      temperature_min_c: daily.temperature_2m_min?.[index] ?? null,
      apparent_temperature_max_c: daily.apparent_temperature_max?.[index] ?? null,
      apparent_temperature_min_c: daily.apparent_temperature_min?.[index] ?? null,
      precipitation_sum_mm: daily.precipitation_sum?.[index] ?? null,
      rain_sum_mm: daily.rain_sum?.[index] ?? null,
      precipitation_hours: daily.precipitation_hours?.[index] ?? null,
      precipitation_probability_max_pct: daily.precipitation_probability_max?.[index] ?? null,
      wind_speed_max_kmh: daily.wind_speed_10m_max?.[index] ?? null,
      wind_gusts_max_kmh: daily.wind_gusts_10m_max?.[index] ?? null,
      sunshine_duration_seconds: daily.sunshine_duration?.[index] ?? null,
    }));
  }

  async function queryForecast(start, end) {
    const payload = await apiFetch(endpoints.forecast, {
      ...commonParams(),
      start_date: start,
      end_date: end,
      daily: DAILY_FORECAST_FIELDS,
      models: "best_match",
    });
    return parseDaily(payload);
  }

  function noaaNumber(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim();
    if (!text || ["T", "M", "NULL", "NAN"].includes(text.toUpperCase())) return null;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function noaaAttributes(value) {
    const parts = String(value ?? "").split(",");
    return {
      measurement: parts[0] || "",
      quality: parts[1] || "",
      source: parts[2] || "",
      observationTime: parts[3] || "",
    };
  }

  function parseNoaaRow(row) {
    const precipitationAttributes = noaaAttributes(row.PRCP_ATTRIBUTES);
    const trace = String(row.PRCP ?? "").trim().toUpperCase() === "T" || precipitationAttributes.measurement === "T";
    const windValues = [noaaNumber(row.WSF2), noaaNumber(row.WSF5)].filter(Number.isFinite);
    const qualityFlags = {};
    ["TMAX", "TMIN", "PRCP", "AWND", "WSF2", "WSF5"].forEach((key) => {
      const attr = noaaAttributes(row[`${key}_ATTRIBUTES`]);
      if (attr.quality) qualityFlags[key] = attr.quality;
    });
    return {
      date: String(row.DATE).slice(0, 10),
      weather_code: null,
      temperature_max_c: noaaNumber(row.TMAX),
      temperature_min_c: noaaNumber(row.TMIN),
      precipitation_sum_mm: trace ? 0 : noaaNumber(row.PRCP),
      precipitation_trace: trace,
      precipitation_probability_max_pct: null,
      wind_speed_mean_kmh: noaaNumber(row.AWND) == null ? null : noaaNumber(row.AWND) * 3.6,
      wind_speed_max_kmh: windValues.length ? Math.max(...windValues) * 3.6 : null,
      quality_flags: qualityFlags,
    };
  }

  function yearChunks(start, end) {
    const chunks = [];
    let current = start;
    while (compareIso(current, end) <= 0) {
      const year = dateParts(current).year;
      const chunkEnd = compareIso(`${year}-12-31`, end) < 0 ? `${year}-12-31` : end;
      chunks.push([current, chunkEnd]);
      current = addDays(chunkEnd, 1);
    }
    return chunks;
  }

  async function queryHistorical(start, end, progress = () => {}) {
    const effectiveStart = compareIso(start, config.observedStation.recordStart) < 0
      ? config.observedStation.recordStart
      : start;
    const rows = [];
    const chunks = compareIso(effectiveStart, end) <= 0 ? yearChunks(effectiveStart, end) : [];
    for (let index = 0; index < chunks.length; index += 1) {
      const [chunkStart, chunkEnd] = chunks[index];
      progress(`Consultando observaciones NOAA ${index + 1} de ${chunks.length}: ${chunkStart} a ${chunkEnd}`);
      const payload = await rawJsonFetch(endpoints.noaa, {
        dataset: "daily-summaries",
        stations: config.observedStation.id,
        startDate: chunkStart,
        endDate: chunkEnd,
        dataTypes: "TMAX,TMIN,PRCP,AWND,WSF2,WSF5",
        format: "json",
        units: "metric",
        includeAttributes: "true",
        includeStationName: "true",
        includeStationLocation: "true",
      });
      if (!Array.isArray(payload)) throw new Error("NOAA/NCEI devolvió un formato inesperado.");
      rows.push(...payload.map(parseNoaaRow));
    }
    const byDate = new Map(rows.map((row) => [row.date, row]));
    const daily = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
    const requestedDays = daysInclusive(start, end);
    const missingDates = [];
    for (let index = 0; index < requestedDays; index += 1) {
      const target = addDays(start, index);
      if (!byDate.has(target)) missingDates.push(target);
    }
    return {
      dataset: "GHCN-Daily Daily Summaries",
      station_id: config.observedStation.id,
      station_name: config.observedStation.name,
      station_latitude: config.observedStation.latitude,
      station_longitude: config.observedStation.longitude,
      station_distance_from_target_km: config.observedStation.distanceFromTargetKm,
      station_record_start: config.observedStation.recordStart,
      coverage_start: daily[0]?.date ?? null,
      coverage_end: daily.at(-1)?.date ?? null,
      requested_days: requestedDays,
      returned_days: daily.length,
      missing_dates: missingDates,
      daily,
    };
  }

  function safeIso(year, month, day) {
    const lastDay = new Date(Date.UTC(year, month, 0, 12)).getUTCDate();
    return `${year}-${String(month).padStart(2, "0")}-${String(Math.min(day, lastDay)).padStart(2, "0")}`;
  }

  function dateParts(isoDate) {
    const [year, month, day] = isoDate.split("-").map(Number);
    return { year, month, day };
  }

  function monthDay(isoDate) {
    return isoDate.slice(5);
  }

  async function queryClimateReference(start, end, yearsCount, progress) {
    const todayYear = dateParts(orlandoToday()).year;
    const startParts = dateParts(start);
    const endParts = dateParts(end);
    const yearSpan = endParts.year - startParts.year;
    const samplesByTarget = new Map();
    const targetDates = Array.from({ length: daysInclusive(start, end) }, (_, index) => addDays(start, index));
    targetDates.forEach((target) => samplesByTarget.set(target, []));
    const usedYears = [];

    for (let offset = yearsCount; offset >= 1; offset -= 1) {
      const sampleYear = todayYear - offset;
      progress(`Consultando referencia histórica ${yearsCount - offset + 1} de ${yearsCount}: ${sampleYear}`);
      const sampleStart = safeIso(sampleYear, startParts.month, startParts.day);
      const sampleEnd = safeIso(sampleYear + yearSpan, endParts.month, endParts.day);
      const payload = await apiFetch(endpoints.archive, {
        ...commonParams(),
        start_date: sampleStart,
        end_date: sampleEnd,
        daily: DAILY_ARCHIVE_FIELDS,
        models: "era5_land",
      });
      const days = parseDaily(payload);
      const byMonthDay = new Map(days.map((day) => [monthDay(day.date), day]));
      let contributed = false;
      targetDates.forEach((target) => {
        const sample = byMonthDay.get(monthDay(target));
        if (sample) {
          samplesByTarget.get(target).push(sample);
          contributed = true;
        }
      });
      if (contributed) usedYears.push(sampleYear);
    }

    const reference = targetDates.map((target) => {
      const rows = samplesByTarget.get(target);
      if (!rows.length) throw new Error(`No se obtuvo referencia histórica para ${target}.`);
      const maximums = rows.map((row) => row.temperature_max_c);
      const minimums = rows.map((row) => row.temperature_min_c);
      const rain = rows.map((row) => row.precipitation_sum_mm);
      return {
        date: target,
        sample_years: rows.length,
        temperature_max_mean_c: average(maximums),
        temperature_max_p10_c: percentile(maximums, 0.1),
        temperature_max_p90_c: percentile(maximums, 0.9),
        temperature_min_mean_c: average(minimums),
        temperature_min_p10_c: percentile(minimums, 0.1),
        temperature_min_p90_c: percentile(minimums, 0.9),
        precipitation_mean_mm: average(rain),
        precipitation_p90_mm: percentile(rain, 0.9),
        rain_frequency_pct: 100 * rows.filter((row) => row.precipitation_sum_mm >= 0.1).length / rows.length,
      };
    });
    return { reference, usedYears };
  }

  function seriesValues(daily, baseKey, index) {
    return Object.keys(daily)
      .filter((key) => key === baseKey || key.startsWith(`${baseKey}_member`))
      .map((key) => daily[key]?.[index])
      .filter(Number.isFinite);
  }

  async function querySeasonal(start, end) {
    if (compareIso(start, end) > 0) return [];
    const payload = await apiFetch(endpoints.seasonal, {
      ...commonParams(),
      daily: SEASONAL_FIELDS,
      forecast_days: config.seasonalHorizonDays,
    });
    return payload.daily.time.flatMap((time, index) => {
      if (compareIso(time, start) < 0 || compareIso(time, end) > 0) return [];
      const maximums = seriesValues(payload.daily, "temperature_2m_max", index);
      const minimums = seriesValues(payload.daily, "temperature_2m_min", index);
      const rain = seriesValues(payload.daily, "precipitation_sum", index);
      return [{
        date: time,
        members: Math.max(maximums.length, minimums.length, rain.length, 1),
        temperature_max_mean_c: average(maximums),
        temperature_max_p10_c: percentile(maximums, 0.1),
        temperature_max_p90_c: percentile(maximums, 0.9),
        temperature_min_mean_c: average(minimums),
        temperature_min_p10_c: percentile(minimums, 0.1),
        temperature_min_p90_c: percentile(minimums, 0.9),
        precipitation_mean_mm: average(rain),
        precipitation_p90_mm: percentile(rain, 0.9),
      }];
    });
  }

  function validate(start, end, mode) {
    if (!start || !end) throw new Error("Completá ambas fechas.");
    if (compareIso(end, start) < 0) throw new Error("La fecha hasta no puede ser anterior a la fecha desde.");
    const today = orlandoToday();
    if (mode === "historical" && compareIso(end, today) >= 0) {
      throw new Error("La consulta histórica solo admite fechas anteriores a hoy.");
    }
    if ((mode === "future" || mode === "capture") && compareIso(start, today) < 0) {
      throw new Error("La consulta futura no admite fechas anteriores a hoy.");
    }
    if (mode === "auto" && compareIso(start, today) < 0 && compareIso(end, today) >= 0) {
      throw new Error("El período cruza pasado y futuro. Hacé dos consultas separadas.");
    }
  }

  function resolveMode(mode, start, end) {
    if (mode !== "auto") return mode;
    return compareIso(end, orlandoToday()) < 0 ? "historical" : "future";
  }

  function setLoading(active, detail = "") {
    elements.loading.classList.toggle("hidden", !active);
    if (detail) elements.loadingDetail.textContent = detail;
  }

  function showError(message) {
    elements.validation.textContent = message;
    elements.validation.classList.remove("hidden");
  }

  function clearError() {
    elements.validation.classList.add("hidden");
    elements.validation.textContent = "";
  }

  function summaryCard(label, value, detail = "", className = "") {
    const classes = ["summary-card", className].filter(Boolean).join(" ");
    return `<article class="${classes}"><small>${label}</small><strong>${value}</strong>${detail ? `<small>${detail}</small>` : ""}</article>`;
  }

  function observedRainMetrics(rows, requestedDays = rows.length) {
    const numericRows = rows.filter((row) => !row.precipitation_trace && Number.isFinite(row.precipitation_sum_mm));
    const traceDays = rows.filter((row) => row.precipitation_trace).length;
    const rainValues = numericRows.map((row) => row.precipitation_sum_mm);
    const totalRain = rainValues.length ? rainValues.reduce((sum, value) => sum + value, 0) : null;
    const rainyDays = rainValues.filter((value) => value >= 0.1).length;
    const dryDays = rainValues.filter((value) => value < 0.1).length;
    const lightDays = rainValues.filter((value) => value >= 0.1 && value < 5).length;
    const moderateDays = rainValues.filter((value) => value >= 5 && value < 20).length;
    const intenseDays = rainValues.filter((value) => value >= 20).length;
    const measuredDays = numericRows.length + traceDays;
    const noDataDays = Math.max(0, requestedDays - measuredDays);
    const rainyPercentage = measuredDays ? (rainyDays / measuredDays) * 100 : null;
    const averagePerRainyDay = rainyDays && totalRain !== null ? totalRain / rainyDays : null;
    return {
      totalRain,
      rainyDays,
      dryDays,
      traceDays,
      lightDays,
      moderateDays,
      intenseDays,
      measuredDays,
      noDataDays,
      rainyPercentage,
      averagePerRainyDay,
    };
  }

  function rainDaysCard(metrics) {
    if (!metrics.measuredDays) {
      return summaryCard("Días con lluvia", "Sin datos", "NOAA no informó precipitación", "summary-card-rain");
    }
    const percentage = Math.round(metrics.rainyPercentage ?? 0);
    const detail = [
      `${percentage}% de los días medidos`,
      metrics.traceDays ? `${metrics.traceDays} con traza` : "sin trazas",
    ].join(" · ");
    return `<article class="summary-card summary-card-rain">
      <div class="summary-label-row"><small>Días con lluvia</small><span class="summary-badge">Dato clave</span></div>
      <strong><span class="rain-days-number">${metrics.rainyDays}</span><span class="rain-days-total"> de ${metrics.measuredDays}</span></strong>
      <div class="rain-progress" role="progressbar" aria-label="Porcentaje de días con lluvia" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percentage}"><span style="width:${Math.max(0, Math.min(100, percentage))}%"></span></div>
      <small>${detail}</small>
    </article>`;
  }

  function rainBreakdown(metrics) {
    const items = [
      ["Sin lluvia", metrics.dryDays, "rain-stat-dry"],
      ["Lluvia leve", metrics.lightDays, "rain-stat-light"],
      ["Moderada", metrics.moderateDays, "rain-stat-moderate"],
      ["Intensa", metrics.intenseDays, "rain-stat-intense"],
      ["Traza", metrics.traceDays, "rain-stat-trace"],
    ];
    if (metrics.noDataDays) items.push(["Sin dato", metrics.noDataDays, "rain-stat-missing"]);
    return `<section class="rain-summary" aria-labelledby="rain-summary-title">
      <div class="rain-summary-heading">
        <div><p class="step">Detalle de precipitación</p><h3 id="rain-summary-title">Cómo se repartieron los días</h3></div>
        <p>Se considera día con lluvia cuando NOAA midió al menos 0,1 mm. Las trazas se informan aparte.</p>
      </div>
      <div class="rain-breakdown" role="list">
        ${items.map(([label, value, className]) => `<article class="rain-stat ${className}" role="listitem"><strong>${value}</strong><span>${label}</span></article>`).join("")}
      </div>
    </section>`;
  }

  function sampledRows(rows, maximum = 160) {
    if (rows.length <= maximum) return rows;
    const step = (rows.length - 1) / (maximum - 1);
    return Array.from({ length: maximum }, (_, index) => rows[Math.round(index * step)]);
  }

  function createTemperatureChart(rows, maxKey, minKey) {
    const chartRows = sampledRows(rows).filter((row) => Number.isFinite(row[maxKey]) || Number.isFinite(row[minKey]));
    if (!chartRows.length) return "";
    const width = 900;
    const height = 240;
    const pad = { left: 44, right: 18, top: 18, bottom: 36 };
    const values = chartRows.flatMap((row) => [row[maxKey], row[minKey]]).filter(Number.isFinite);
    if (!values.length) return "";
    const minimum = Math.floor(Math.min(...values) - 2);
    const maximum = Math.ceil(Math.max(...values) + 2);
    const x = (index) => pad.left + index * ((width - pad.left - pad.right) / Math.max(chartRows.length - 1, 1));
    const y = (value) => pad.top + (maximum - value) * ((height - pad.top - pad.bottom) / Math.max(maximum - minimum, 1));
    const points = (key) => chartRows.flatMap((row, index) => Number.isFinite(row[key]) ? [`${x(index)},${y(row[key])}`] : []).join(" ");
    const grid = [minimum, Math.round((minimum + maximum) / 2), maximum].map((value) => `
      <line class="chart-grid" x1="${pad.left}" y1="${y(value)}" x2="${width - pad.right}" y2="${y(value)}"></line>
      <text class="chart-label" x="4" y="${y(value) + 4}">${value}°</text>
    `).join("");
    const labelEvery = Math.max(1, Math.ceil(chartRows.length / 12));
    const labels = chartRows.map((row, index) => index % labelEvery === 0 || index === chartRows.length - 1 ? `
      <text class="chart-label" text-anchor="middle" x="${x(index)}" y="${height - 10}">${row.date.slice(5).replace("-", "/")}</text>
    ` : "").join("");
    return `
      <div class="chart-card">
        <h3>Evolución de temperaturas</h3>
        <div class="chart-legend"><span><i class="legend-dot legend-max"></i>Máxima</span><span><i class="legend-dot legend-min"></i>Mínima</span></div>
        <svg class="temperature-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Gráfico de temperaturas máximas y mínimas">
          ${grid}
          <polyline class="chart-max" points="${points(maxKey)}"></polyline>
          <polyline class="chart-min" points="${points(minKey)}"></polyline>
          ${labels}
        </svg>
        ${rows.length > chartRows.length ? `<p class="muted">El gráfico muestra una muestra de ${chartRows.length} puntos. El JSON conserva los ${rows.length} días.</p>` : ""}
      </div>`;
  }

  function observedRainClass(day) {
    if (day.precipitation_trace) return "observed-trace-row";
    if (!Number.isFinite(day.precipitation_sum_mm)) return "";
    if (day.precipitation_sum_mm >= 20) return "observed-rain-row observed-rain-intense-row";
    if (day.precipitation_sum_mm >= 5) return "observed-rain-row observed-rain-moderate-row";
    if (day.precipitation_sum_mm >= 0.1) return "observed-rain-row";
    return "";
  }

  function observedRainCell(day) {
    if (day.precipitation_trace) return '<span class="rain-value rain-value-trace">Traza</span>';
    if (!Number.isFinite(day.precipitation_sum_mm)) return '<span class="rain-value rain-value-missing">Sin dato</span>';
    const value = `${formatNumber(day.precipitation_sum_mm)} mm`;
    if (day.precipitation_sum_mm >= 20) return `<span class="rain-value rain-value-intense">${value}</span>`;
    if (day.precipitation_sum_mm >= 5) return `<span class="rain-value rain-value-moderate">${value}</span>`;
    if (day.precipitation_sum_mm >= 0.1) return `<span class="rain-value rain-value-light">${value}</span>`;
    return `<span class="rain-value rain-value-dry">${value}</span>`;
  }

  function dailyTable(rows, options = {}) {
    const probability = options.probability !== false;
    const observed = options.observed === true;
    return `<div class="table-wrap"><table>
      <thead><tr><th>Fecha</th>${observed ? "" : "<th>Condición</th>"}<th class="numeric">Máx.</th><th class="numeric">Mín.</th><th class="numeric">Lluvia</th>${probability ? '<th class="numeric">Prob.</th>' : ""}<th class="numeric">Viento</th></tr></thead>
      <tbody>${rows.map((day) => `<tr class="${observed ? observedRainClass(day) : ""}">
        <td>${dateLabel(day.date)}</td>
        ${observed ? "" : `<td>${condition(day.weather_code)}</td>`}
        <td class="numeric">${formatNumber(day.temperature_max_c)} °C</td>
        <td class="numeric">${formatNumber(day.temperature_min_c)} °C</td>
        <td class="numeric">${observed ? observedRainCell(day) : day.precipitation_trace ? "Traza" : day.precipitation_sum_mm == null ? "Sin dato" : `${formatNumber(day.precipitation_sum_mm)} mm`}</td>
        ${probability ? `<td class="numeric">${day.precipitation_probability_max_pct == null ? "—" : `${formatNumber(day.precipitation_probability_max_pct, 0)}%`}</td>` : ""}
        <td class="numeric">${formatNumber(day.wind_speed_max_kmh)} km/h</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function monthlyObservedTable(rows) {
    const groups = new Map();
    rows.forEach((row) => {
      const key = row.date.slice(0, 7);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });
    return `<div class="table-wrap"><table>
      <thead><tr><th>Mes</th><th class="numeric">Días</th><th class="numeric">Máx. media</th><th class="numeric">Mín. media</th><th class="numeric">Lluvia</th><th class="numeric">Días lluvia</th><th class="numeric">Trazas</th></tr></thead>
      <tbody>${[...groups.entries()].map(([month, values]) => {
        const rain = values.map((row) => row.precipitation_sum_mm).filter(Number.isFinite);
        return `<tr><td>${month}</td><td class="numeric">${values.length}</td><td class="numeric">${formatNumber(average(values.map((row) => row.temperature_max_c)))} °C</td><td class="numeric">${formatNumber(average(values.map((row) => row.temperature_min_c)))} °C</td><td class="numeric">${formatNumber(rain.length ? rain.reduce((sum, value) => sum + value, 0) : null)} mm</td><td class="numeric">${rain.filter((value) => value >= 0.1).length}</td><td class="numeric">${values.filter((row) => row.precipitation_trace).length}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderHistorical(result) {
    const rows = result.daily;
    const averageMax = average(rows.map((row) => row.temperature_max_c));
    const averageMin = average(rows.map((row) => row.temperature_min_c));
    const rain = observedRainMetrics(rows, result.requested_days);
    const coveragePercentage = result.requested_days ? (result.returned_days / result.requested_days) * 100 : null;
    elements.resultKicker.textContent = "Observado en estación oficial";
    elements.resultTitle.textContent = `${dateLabel(result.requested_start)} al ${dateLabel(result.requested_end)}`;
    elements.resultContent.innerHTML = `
      <div class="summary-grid historical-summary-grid">
        ${rainDaysCard(rain)}
        ${summaryCard("Lluvia acumulada", rain.totalRain == null ? "Sin dato" : `${formatNumber(rain.totalRain)} mm`, rain.averagePerRainyDay == null ? "Sin lluvia medible" : `${formatNumber(rain.averagePerRainyDay)} mm por día con lluvia`, "summary-card-rain-total")}
        ${summaryCard("Máxima promedio", `${formatNumber(averageMax)} °C`)}
        ${summaryCard("Mínima promedio", `${formatNumber(averageMin)} °C`)}
        ${summaryCard("Cobertura NOAA", `${result.returned_days} de ${result.requested_days} días`, coveragePercentage == null ? "Sin dato" : `${formatNumber(coveragePercentage, 0)}% del período`)}
      </div>
      ${rainBreakdown(rain)}
      <div class="notice"><strong>Fuente:</strong> NOAA/NCEI · ${result.dataset} · <strong>${result.station_name} (${result.station_id})</strong>, a unos ${formatNumber(result.station_distance_from_target_km)} km de Disney. Son mediciones reales en KMCO, no dentro de los parques.</div>
      ${result.missing_dates.length ? `<div class="notice warning"><strong>Cobertura incompleta:</strong> faltan ${result.missing_dates.length} fechas. Los datos ausentes no se convierten en cero ni se completan con un modelo.</div>` : ""}
      ${createTemperatureChart(rows, "temperature_max_c", "temperature_min_c")}
      ${rows.length > 180 ? `<h3>Resumen mensual</h3>${monthlyObservedTable(rows)}<p class="muted">El JSON descargado conserva los ${rows.length} registros diarios.</p>` : dailyTable(rows, { probability: false, observed: true })}`;
  }

  function seasonalTable(rows) {
    return `<div class="table-wrap"><table>
      <thead><tr><th>Fecha</th><th class="numeric">Máx. media y rango</th><th class="numeric">Mín. media y rango</th><th class="numeric">Lluvia media / P90</th><th class="numeric">Miembros</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <td>${dateLabel(row.date)}</td>
        <td class="numeric">${formatNumber(row.temperature_max_mean_c)} °C · ${formatNumber(row.temperature_max_p10_c)}–${formatNumber(row.temperature_max_p90_c)}</td>
        <td class="numeric">${formatNumber(row.temperature_min_mean_c)} °C · ${formatNumber(row.temperature_min_p10_c)}–${formatNumber(row.temperature_min_p90_c)}</td>
        <td class="numeric">${formatNumber(row.precipitation_mean_mm)} / ${formatNumber(row.precipitation_p90_mm)} mm</td>
        <td class="numeric">${row.members}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function climateTable(rows) {
    return `<div class="table-wrap"><table>
      <thead><tr><th>Fecha objetivo</th><th class="numeric">Máx. media y rango</th><th class="numeric">Mín. media y rango</th><th class="numeric">Lluvia media / P90</th><th class="numeric">Frecuencia lluvia</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <td>${dateLabel(row.date)}</td>
        <td class="numeric">${formatNumber(row.temperature_max_mean_c)} °C · ${formatNumber(row.temperature_max_p10_c)}–${formatNumber(row.temperature_max_p90_c)}</td>
        <td class="numeric">${formatNumber(row.temperature_min_mean_c)} °C · ${formatNumber(row.temperature_min_p10_c)}–${formatNumber(row.temperature_min_p90_c)}</td>
        <td class="numeric">${formatNumber(row.precipitation_mean_mm)} / ${formatNumber(row.precipitation_p90_mm)} mm</td>
        <td class="numeric">${formatNumber(row.rain_frequency_pct, 0)}%</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function renderFuture(result) {
    const preferredRows = result.live_forecast.length
      ? result.live_forecast
      : result.climate_reference.map((row) => ({
          date: row.date,
          temperature_max_c: row.temperature_max_mean_c,
          temperature_min_c: row.temperature_min_mean_c,
        }));
    const averageMax = average(preferredRows.map((row) => row.temperature_max_c));
    const averageMin = average(preferredRows.map((row) => row.temperature_min_c));
    const rainFrequency = result.climate_reference.length
      ? average(result.climate_reference.map((row) => row.rain_frequency_pct))
      : null;
    const predictedRain = result.live_forecast.reduce((sum, row) => sum + row.precipitation_sum_mm, 0);
    const level = result.live_forecast.length === daysInclusive(result.requested_start, result.requested_end)
      ? "Pronóstico diario completo"
      : result.seasonal_estimate.length
        ? "Pronóstico parcial + tendencia"
        : "Referencia climática";
    elements.resultKicker.textContent = "Mejor información futura disponible";
    elements.resultTitle.textContent = `${dateLabel(result.requested_start)} al ${dateLabel(result.requested_end)}`;
    elements.resultContent.innerHTML = `
      <div class="summary-grid">
        ${summaryCard("Nivel de información", level)}
        ${summaryCard("Máxima orientativa", `${formatNumber(averageMax)} °C`)}
        ${summaryCard("Mínima orientativa", `${formatNumber(averageMin)} °C`)}
        ${result.climate_reference.length
          ? summaryCard("Frecuencia histórica de lluvia", `${formatNumber(rainFrequency, 0)}%`)
          : summaryCard("Lluvia prevista acumulada", `${formatNumber(predictedRain)} mm`)}
      </div>
      <div class="notice warning"><strong>Lectura correcta:</strong> solamente los días hasta ${dateLabel(result.forecast_available_through)} tienen pronóstico meteorológico diario. Los demás datos son tendencias o antecedentes.</div>
      ${result.live_forecast.length ? `<section class="source-section"><h3>Pronóstico diario vigente <span class="source-pill">hasta 16 días</span></h3>${createTemperatureChart(result.live_forecast, "temperature_max_c", "temperature_min_c")}${dailyTable(result.live_forecast)}</section>` : ""}
      ${result.seasonal_estimate.length ? `<section class="source-section"><h3>Tendencia estacional <span class="source-pill">Ensamble probabilístico</span></h3><p class="muted">El rango P10–P90 representa la dispersión de los miembros del modelo; no es una promesa para cada fecha.</p>${seasonalTable(result.seasonal_estimate)}</section>` : ""}
      ${result.climate_reference.length ? `<section class="source-section"><h3>Referencia climática <span class="source-pill">${result.climate_reference_years.length} años</span></h3><p class="muted">Promedios de las mismas fechas durante ${result.climate_reference_years[0]}–${result.climate_reference_years.at(-1)}.</p>${climateTable(result.climate_reference)}</section>` : ""}`;
  }

  function historicalMarkdown(result) {
    const rain = observedRainMetrics(result.daily, result.requested_days);
    const lines = [
      "# Observaciones meteorológicas oficiales — Orlando",
      "",
      `Período solicitado: ${result.requested_start} al ${result.requested_end}`,
      `Estación: ${result.station_name} (${result.station_id})`,
      `Fuente: NOAA/NCEI — ${result.dataset}`,
      `Distancia aproximada a Disney: ${formatNumber(result.station_distance_from_target_km)} km`,
      `Cobertura: ${result.returned_days} de ${result.requested_days} días`,
      `Días con lluvia medible: ${rain.rainyDays} de ${rain.measuredDays}`,
      `Días con traza: ${rain.traceDays}`,
      `Días sin lluvia: ${rain.dryDays}`,
      `Lluvia acumulada: ${rain.totalRain == null ? "Sin dato" : `${formatNumber(rain.totalRain)} mm`}`,
      `Intensidad diaria: ${rain.lightDays} leves · ${rain.moderateDays} moderados · ${rain.intenseDays} intensos`,
      "",
      "> Son observaciones reales en KMCO, no mediciones dentro de Walt Disney World. Los faltantes no se reemplazan por cero ni por un modelo.",
      "",
    ];
    if (result.daily.length <= 180) {
      lines.push("| Fecha | Máx. °C | Mín. °C | Precipitación mm | Viento máx. km/h |", "|---|---:|---:|---:|---:|");
      result.daily.forEach((day) => lines.push(`| ${day.date} | ${formatNumber(day.temperature_max_c)} | ${formatNumber(day.temperature_min_c)} | ${day.precipitation_trace ? "Traza" : day.precipitation_sum_mm == null ? "Sin dato" : formatNumber(day.precipitation_sum_mm)} | ${formatNumber(day.wind_speed_max_kmh)} |`));
    } else {
      lines.push("El archivo JSON conserva todos los registros diarios. La interfaz muestra un resumen mensual para períodos extensos.");
    }
    return lines.join("\n");
  }

  function futureMarkdown(result) {
    const lines = [
      "# Perspectiva meteorológica futura — Disney Orlando",
      "",
      `Período: ${result.requested_start} al ${result.requested_end}`,
      `Pronóstico diario disponible hasta: ${result.forecast_available_through}`,
      "",
    ];
    if (result.live_forecast.length) {
      lines.push("## Pronóstico diario", "", "| Fecha | Máx. °C | Mín. °C | Lluvia mm | Prob. |", "|---|---:|---:|---:|---:|");
      result.live_forecast.forEach((day) => lines.push(`| ${day.date} | ${formatNumber(day.temperature_max_c)} | ${formatNumber(day.temperature_min_c)} | ${formatNumber(day.precipitation_sum_mm)} | ${day.precipitation_probability_max_pct == null ? "—" : `${formatNumber(day.precipitation_probability_max_pct, 0)}%`} |`));
      lines.push("");
    }
    if (result.seasonal_estimate.length) {
      lines.push("## Tendencia estacional", "", "| Fecha | Máx. media P10–P90 | Mín. media P10–P90 | Lluvia media/P90 |", "|---|---:|---:|---:|");
      result.seasonal_estimate.forEach((day) => lines.push(`| ${day.date} | ${formatNumber(day.temperature_max_mean_c)} (${formatNumber(day.temperature_max_p10_c)}–${formatNumber(day.temperature_max_p90_c)}) | ${formatNumber(day.temperature_min_mean_c)} (${formatNumber(day.temperature_min_p10_c)}–${formatNumber(day.temperature_min_p90_c)}) | ${formatNumber(day.precipitation_mean_mm)}/${formatNumber(day.precipitation_p90_mm)} |`));
      lines.push("");
    }
    if (result.climate_reference.length) {
      lines.push("## Referencia climática", "", "| Fecha | Máx. media P10–P90 | Mín. media P10–P90 | Lluvia media/P90 | Frecuencia lluvia |", "|---|---:|---:|---:|---:|");
      result.climate_reference.forEach((day) => lines.push(`| ${day.date} | ${formatNumber(day.temperature_max_mean_c)} (${formatNumber(day.temperature_max_p10_c)}–${formatNumber(day.temperature_max_p90_c)}) | ${formatNumber(day.temperature_min_mean_c)} (${formatNumber(day.temperature_min_p10_c)}–${formatNumber(day.temperature_min_p90_c)}) | ${formatNumber(day.precipitation_mean_mm)}/${formatNumber(day.precipitation_p90_mm)} | ${formatNumber(day.rain_frequency_pct, 0)}% |`));
    }
    lines.push("", "> Fuera de la ventana diaria, los valores son probabilísticos o históricos; no indican el tiempo exacto de cada día.");
    return lines.join("\n");
  }

  function snapshotFromResult(result) {
    const days = result.query_type === "forecast_snapshot" ? result.daily : result.live_forecast;
    if (!days?.length) return null;
    return {
      schema_version: "4.0",
      query_type: "forecast_snapshot",
      provider: "open-meteo",
      model: "best_match",
      location_name: config.locationName,
      latitude: config.latitude,
      longitude: config.longitude,
      timezone: config.timezone,
      requested_start: days[0].date,
      requested_end: days.at(-1).date,
      captured_at_utc: new Date().toISOString(),
      daily: days,
    };
  }

  function loadSnapshots() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(value) ? value : [];
    } catch {
      return [];
    }
  }

  function persistSnapshots(snapshots) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshots));
  }

  function saveSnapshot(snapshot, silent = false) {
    const snapshots = loadSnapshots();
    const duplicate = snapshots.some((item) => item.captured_at_utc === snapshot.captured_at_utc);
    if (!duplicate) {
      snapshots.push(snapshot);
      persistSnapshots(snapshots);
    }
    renderSnapshots();
    if (!silent) window.alert("Captura guardada en este dispositivo.");
  }

  function download(name, content, type) {
    const blob = new Blob([content], { type });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function renderSnapshots() {
    const snapshots = loadSnapshots().sort((a, b) => b.captured_at_utc.localeCompare(a.captured_at_utc));
    if (!snapshots.length) {
      elements.capturesList.innerHTML = '<div class="empty-state">Todavía no hay capturas. Consultá una fecha dentro de los próximos 16 días y guardá el resultado.</div>';
      return;
    }
    const today = orlandoToday();
    elements.capturesList.innerHTML = snapshots.map((snapshot) => {
      const comparable = snapshot.daily.some((day) => compareIso(day.date, today) < 0);
      return `<article class="capture-card" data-capture="${snapshot.captured_at_utc}">
        <div><strong>${snapshot.requested_start} al ${snapshot.requested_end}</strong><p>Capturado: ${new Date(snapshot.captured_at_utc).toLocaleString("es-AR")}</p><small>${snapshot.daily.length} días · ${snapshot.model}</small></div>
        <div class="capture-actions">
          <button class="secondary-button" data-action="compare" ${comparable ? "" : "disabled"}>Comparar</button>
          <button class="secondary-button" data-action="export">Exportar</button>
          <button class="secondary-button danger-button" data-action="delete">Eliminar</button>
        </div>
      </article>`;
    }).join("");
  }

  function metricError(forecast, actual) {
    if (!Number.isFinite(forecast) || !Number.isFinite(actual)) return null;
    const signed = forecast - actual;
    return { signed, absolute: Math.abs(signed) };
  }

  async function compareSnapshot(snapshot) {
    const pastDays = snapshot.daily.filter((day) => compareIso(day.date, orlandoToday()) < 0);
    if (!pastDays.length) throw new Error("La captura todavía no tiene fechas finalizadas para comparar.");
    setLoading(true, "Recuperando observaciones oficiales para comparar…");
    const start = pastDays[0].date;
    const end = pastDays.at(-1).date;
    const historical = await queryHistorical(start, end, (detail) => {
      elements.loadingDetail.textContent = detail;
    });
    const actualByDate = new Map(historical.daily.map((day) => [day.date, day]));
    const rows = pastDays.flatMap((forecast) => {
      const actual = actualByDate.get(forecast.date);
      if (!actual) return [];
      const forecastRain = Number.isFinite(forecast.precipitation_sum_mm) ? forecast.precipitation_sum_mm >= 0.1 : null;
      const actualRain = Number.isFinite(actual.precipitation_sum_mm) ? actual.precipitation_sum_mm >= 0.1 : null;
      return [{
        target_date: forecast.date,
        lead_days: Math.round((parseIso(forecast.date) - parseIso(snapshot.captured_at_utc.slice(0, 10))) / 86400000),
        forecast,
        actual,
        temperature_max_error_c: metricError(forecast.temperature_max_c, actual.temperature_max_c),
        temperature_min_error_c: metricError(forecast.temperature_min_c, actual.temperature_min_c),
        precipitation_error_mm: metricError(forecast.precipitation_sum_mm, actual.precipitation_sum_mm),
        rain_event_forecast: forecastRain,
        rain_event_actual: actualRain,
        rain_event_correct: forecastRain === null || actualRain === null ? null : forecastRain === actualRain,
      }];
    });
    currentComparison = {
      schema_version: "4.0",
      query_type: "comparison",
      provider: "open-meteo-vs-noaa-ncei",
      location_name: config.locationName,
      requested_start: start,
      requested_end: end,
      generated_at_utc: new Date().toISOString(),
      snapshot_captured_at_utc: snapshot.captured_at_utc,
      actual_dataset: historical.dataset,
      actual_station_id: historical.station_id,
      actual_station_name: historical.station_name,
      actual_station_distance_from_target_km: historical.station_distance_from_target_km,
      daily: rows,
    };
    renderComparison(currentComparison);
    elements.comparisonPanel.classList.remove("hidden");
    elements.comparisonPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderComparison(report) {
    const maxMae = average(report.daily.map((row) => row.temperature_max_error_c?.absolute));
    const minMae = average(report.daily.map((row) => row.temperature_min_error_c?.absolute));
    const rainMae = average(report.daily.map((row) => row.precipitation_error_mm?.absolute));
    const comparableRain = report.daily.filter((row) => row.rain_event_correct !== null);
    const rainAccuracy = comparableRain.length ? 100 * comparableRain.filter((row) => row.rain_event_correct).length / comparableRain.length : null;
    elements.comparisonContent.innerHTML = `
      <div class="summary-grid">
        ${summaryCard("MAE máxima", `${formatNumber(maxMae, 2)} °C`)}
        ${summaryCard("MAE mínima", `${formatNumber(minMae, 2)} °C`)}
        ${summaryCard("MAE lluvia", `${formatNumber(rainMae, 2)} mm`)}
        ${summaryCard("Acierto lluvia", rainAccuracy == null ? "Sin datos" : `${formatNumber(rainAccuracy, 0)}%`)}
      </div>
      <div class="notice">Pronóstico para Disney capturado el <strong>${new Date(report.snapshot_captured_at_utc).toLocaleString("es-AR")}</strong>. Observación: <strong>${report.actual_station_name} (${report.actual_station_id})</strong>, a unos ${formatNumber(report.actual_station_distance_from_target_km)} km. La lluvia puede diferir localmente.</div>
      <div class="table-wrap"><table>
        <thead><tr><th>Fecha</th><th class="numeric">Anticipación</th><th class="numeric">Máx. pron./obs.</th><th class="numeric">Mín. pron./obs.</th><th class="numeric">Lluvia pron./obs.</th><th>Acierto lluvia</th></tr></thead>
        <tbody>${report.daily.map((row) => `<tr><td>${dateLabel(row.target_date)}</td><td class="numeric">${row.lead_days} días</td><td class="numeric">${formatNumber(row.forecast.temperature_max_c)}/${formatNumber(row.actual.temperature_max_c)} °C</td><td class="numeric">${formatNumber(row.forecast.temperature_min_c)}/${formatNumber(row.actual.temperature_min_c)} °C</td><td class="numeric">${formatNumber(row.forecast.precipitation_sum_mm)}/${row.actual.precipitation_sum_mm == null ? "Sin dato" : formatNumber(row.actual.precipitation_sum_mm)} mm</td><td>${row.rain_event_correct === null ? "Sin dato" : row.rain_event_correct ? "Sí" : "No"}</td></tr>`).join("")}</tbody>
      </table></div>`;
  }

  async function handleQuery(event) {
    event.preventDefault();
    clearError();
    elements.resultPanel.classList.add("hidden");
    elements.saveCapture.classList.add("hidden");
    const start = elements.start.value;
    const end = elements.end.value;
    const selectedMode = elements.mode.value;
    try {
      validate(start, end, selectedMode);
      const mode = resolveMode(selectedMode, start, end);
      setLoading(true, "Validando disponibilidad de datos…");
      if (mode === "historical") {
        elements.loadingDetail.textContent = "Recuperando observaciones oficiales NOAA…";
        const historical = await queryHistorical(start, end, (detail) => {
          elements.loadingDetail.textContent = detail;
        });
        currentResult = {
          schema_version: "4.0",
          query_type: "historical",
          provider: "noaa-ncei",
          dataset: historical.dataset,
          location_name: config.locationName,
          latitude: config.latitude,
          longitude: config.longitude,
          timezone: config.timezone,
          station_id: historical.station_id,
          station_name: historical.station_name,
          station_latitude: historical.station_latitude,
          station_longitude: historical.station_longitude,
          station_distance_from_target_km: historical.station_distance_from_target_km,
          station_record_start: historical.station_record_start,
          requested_start: start,
          requested_end: end,
          retrieved_at_utc: new Date().toISOString(),
          coverage_start: historical.coverage_start,
          coverage_end: historical.coverage_end,
          requested_days: historical.requested_days,
          returned_days: historical.returned_days,
          missing_dates: historical.missing_dates,
          daily: historical.daily,
        };
        currentMarkdown = historicalMarkdown(currentResult);
        renderHistorical(currentResult);
      } else if (mode === "capture") {
        const today = orlandoToday();
        const availableEnd = addDays(today, config.forecastHorizonDays - 1);
        if (compareIso(start, today) < 0 || compareIso(end, availableEnd) > 0) {
          throw new Error(`Solo se puede capturar el pronóstico entre ${today} y ${availableEnd}.`);
        }
        elements.loadingDetail.textContent = "Capturando el pronóstico vigente…";
        const days = await queryForecast(start, end);
        currentResult = {
          schema_version: "4.0",
          query_type: "forecast_snapshot",
          provider: "open-meteo",
          model: "best_match",
          location_name: config.locationName,
          latitude: config.latitude,
          longitude: config.longitude,
          timezone: config.timezone,
          requested_start: start,
          requested_end: end,
          captured_at_utc: new Date().toISOString(),
          daily: days,
        };
        currentMarkdown = futureMarkdown({
          requested_start: start,
          requested_end: end,
          forecast_available_through: availableEnd,
          live_forecast: days,
          seasonal_estimate: [],
          climate_reference: [],
        });
        renderFuture({
          ...currentResult,
          forecast_available_through: availableEnd,
          live_forecast: days,
          seasonal_estimate: [],
          climate_reference_years: [],
          climate_reference: [],
        });
        saveSnapshot(currentResult, true);
        elements.resultKicker.textContent = "Captura guardada";
      } else {
        const today = orlandoToday();
        const forecastEnd = addDays(today, config.forecastHorizonDays - 1);
        const seasonalEnd = addDays(today, config.seasonalHorizonDays - 1);
        let liveForecast = [];
        if (compareIso(start, forecastEnd) <= 0) {
          const liveStart = compareIso(start, today) < 0 ? today : start;
          const liveEnd = compareIso(end, forecastEnd) < 0 ? end : forecastEnd;
          elements.loadingDetail.textContent = "Recuperando el pronóstico diario disponible…";
          liveForecast = await queryForecast(liveStart, liveEnd);
        }
        let seasonalEstimate = [];
        if (compareIso(end, forecastEnd) > 0 && compareIso(start, seasonalEnd) <= 0) {
          elements.loadingDetail.textContent = "Recuperando la tendencia estacional…";
          try {
            seasonalEstimate = await querySeasonal(
              compareIso(start, addDays(forecastEnd, 1)) > 0 ? start : addDays(forecastEnd, 1),
              compareIso(end, seasonalEnd) < 0 ? end : seasonalEnd,
            );
          } catch (error) {
            console.warn("Tendencia estacional no disponible", error);
          }
        }
        const yearsCount = Number(elements.historyYears.value);
        const climate = await queryClimateReference(start, end, yearsCount, (detail) => {
          elements.loadingDetail.textContent = detail;
        });
        currentResult = {
          schema_version: "4.0",
          query_type: "future_outlook",
          provider: "open-meteo",
          location_name: config.locationName,
          latitude: config.latitude,
          longitude: config.longitude,
          timezone: config.timezone,
          requested_start: start,
          requested_end: end,
          generated_at_utc: new Date().toISOString(),
          forecast_available_through: forecastEnd,
          live_forecast: liveForecast,
          seasonal_estimate: seasonalEstimate,
          climate_reference_years: climate.usedYears,
          climate_reference: climate.reference,
          notes: [
            "Hasta 16 días se muestra un pronóstico diario vigente.",
            "Fuera de esa ventana, la tendencia es probabilística.",
            "La referencia climática resume años anteriores.",
          ],
        };
        currentMarkdown = futureMarkdown(currentResult);
        renderFuture(currentResult);
        if (liveForecast.length) elements.saveCapture.classList.remove("hidden");
      }
      elements.resultPanel.classList.remove("hidden");
      elements.resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showError(error instanceof Error ? error.message : "No se pudo completar la consulta.");
    } finally {
      setLoading(false);
    }
  }

  function setupRepositoryLink() {
    let repositoryUrl = config.repositoryUrl;
    if (!repositoryUrl && location.hostname.endsWith("github.io")) {
      const owner = location.hostname.split(".")[0];
      const repository = location.pathname.split("/").filter(Boolean)[0];
      if (owner && repository) repositoryUrl = `https://github.com/${owner}/${repository}`;
    }
    if (repositoryUrl) {
      elements.actionsLink.href = `${repositoryUrl.replace(/\/$/, "")}/actions/workflows/weather-query.yml`;
      elements.actionsLink.classList.remove("hidden");
    }
  }

  async function loadRepositoryLatest() {
    try {
      const catalogResponse = await fetch("generated/catalog.json", { cache: "no-store" });
      if (!catalogResponse.ok) return;
      const catalog = await catalogResponse.json();
      const latestResponse = await fetch(`generated/${catalog.latest_json}`, { cache: "no-store" });
      if (!latestResponse.ok) return;
      const latest = await latestResponse.json();
      elements.latestContent.innerHTML = `<p><strong>Tipo:</strong> ${latest.query_type}</p><p><strong>Actualizado:</strong> ${new Date(catalog.updated_at_utc).toLocaleString("es-AR")}</p><p class="muted">Esta copia se generó mediante una ejecución manual de GitHub Actions.</p>`;
      elements.repositoryLatest.classList.remove("hidden");
    } catch {
      // No persisted query yet.
    }
  }

  elements.form.addEventListener("submit", handleQuery);
  elements.saveCapture.addEventListener("click", () => {
    const snapshot = snapshotFromResult(currentResult);
    if (snapshot) saveSnapshot(snapshot);
  });
  elements.exportJson.addEventListener("click", () => {
    if (!currentResult) return;
    download(`disney-weather-${currentResult.requested_start}-${currentResult.requested_end}.json`, `${JSON.stringify(currentResult, null, 2)}\n`, "application/json");
  });
  elements.exportMd.addEventListener("click", () => {
    if (!currentMarkdown) return;
    download(`disney-weather-${currentResult.requested_start}-${currentResult.requested_end}.md`, currentMarkdown, "text/markdown");
  });
  elements.exportComparison.addEventListener("click", () => {
    if (!currentComparison) return;
    download(`comparacion-${currentComparison.requested_start}-${currentComparison.requested_end}.json`, `${JSON.stringify(currentComparison, null, 2)}\n`, "application/json");
  });

  elements.capturesList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const card = button.closest("[data-capture]");
    const capturedAt = card.dataset.capture;
    const snapshots = loadSnapshots();
    const snapshot = snapshots.find((item) => item.captured_at_utc === capturedAt);
    if (!snapshot) return;
    try {
      if (button.dataset.action === "delete") {
        persistSnapshots(snapshots.filter((item) => item.captured_at_utc !== capturedAt));
        renderSnapshots();
      } else if (button.dataset.action === "export") {
        download(`pronostico-${snapshot.requested_start}-${snapshot.requested_end}.json`, `${JSON.stringify(snapshot, null, 2)}\n`, "application/json");
      } else if (button.dataset.action === "compare") {
        clearError();
        await compareSnapshot(snapshot);
      }
    } catch (error) {
      showError(error instanceof Error ? error.message : "No se pudo comparar la captura.");
    } finally {
      setLoading(false);
    }
  });

  elements.importFile.addEventListener("change", async () => {
    const file = elements.importFile.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const candidates = Array.isArray(parsed) ? parsed : [parsed];
      const snapshots = loadSnapshots();
      candidates.forEach((candidate) => {
        if (candidate.query_type !== "forecast_snapshot" || !Array.isArray(candidate.daily)) {
          throw new Error("El archivo no contiene una captura de pronóstico válida.");
        }
        if (!snapshots.some((item) => item.captured_at_utc === candidate.captured_at_utc)) snapshots.push(candidate);
      });
      persistSnapshots(snapshots);
      renderSnapshots();
    } catch (error) {
      showError(error instanceof Error ? error.message : "No se pudo importar el archivo.");
    } finally {
      elements.importFile.value = "";
    }
  });

  const today = orlandoToday();
  elements.start.value = addDays(today, 1);
  elements.end.value = addDays(today, 30);
  setupRepositoryLink();
  renderSnapshots();
  loadRepositoryLatest();
})();
