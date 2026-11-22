"use strict";

const STORAGE_KEY = "krisha-list.catalog.v1";
const AREA_KEY = "krisha-list.area.v1";
const $ = (selector) => document.querySelector(selector);
const isLocalHost = ["127.0.0.1", "localhost"].includes(window.location.hostname);
const legacyBrowserListings = readSaved();
const state = { listings: isLocalHost ? [] : legacyBrowserListings, runs: [], storageWarning: false, revision: 0 };
let shownCount = 100;
const numberFormat = new Intl.NumberFormat("ru-RU");
const decimalFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });
let resultsView = "table";
let breakdownMode = "rooms";
let currentVisible = [];
let currentSelection = null;
let renderedRevision = -1;
let lastVisibleSignature = "";
let viewTransitioning = false;
let resultsMap = null;
let resultsMapLayer = null;
let resultsAreaLayer = null;
let selectedMapMarker = null;
let collectionMode = "text";
const collectionCities = {
  almaty: { name: "Алматы", center: [43.249, 76.9] },
  astana: { name: "Астана", center: [51.16, 71.43] },
  shymkent: { name: "Шымкент", center: [42.34, 69.59] },
  aktau: { name: "Актау", center: [43.652, 51.157] },
  aktobe: { name: "Актобе", center: [50.283, 57.167] },
  atyrau: { name: "Атырау", center: [47.094, 51.923] },
  karaganda: { name: "Караганда", center: [49.806, 73.085] },
  pavlodar: { name: "Павлодар", center: [52.287, 76.967] },
  semej: { name: "Семей", center: [50.411, 80.228] },
  taraz: { name: "Тараз", center: [42.9, 71.365] }
};
const knownPlaces = [
  { city: "almaty", label: "Алатауский р-н", alias: "almaty-alatauskij" },
  { city: "almaty", label: "Алмалинский р-н", alias: "almaty-almalinskij" },
  { city: "almaty", label: "Ауэзовский р-н", alias: "almaty-aujezovskij" },
  { city: "almaty", label: "Бостандыкский р-н", alias: "almaty-bostandykskij" },
  { city: "almaty", label: "Жетысуский р-н", alias: "almaty-zhetysuskij" },
  { city: "almaty", label: "Медеуский р-н", alias: "almaty-medeuskij" },
  { city: "almaty", label: "Наурызбайский р-н", alias: "almaty-nauryzbajskiy" },
  { city: "almaty", label: "Турксибский р-н", alias: "almaty-turksibskij" },
  { city: "almaty", label: "мкр Тастак-2", alias: "almaty-almalinskijj-tastak-2" },
  { city: "almaty", label: "мкр Тастак-3", alias: "almaty-almalinskij-tastak-3" }
];

function readSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved.filter((row) => row && /^\d+$/.test(String(row.id))) : [];
  } catch {
    return [];
  }
}

function save(listings) {
  state.listings = listings;
  state.revision++;
  if (!isLocalHost) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(listings));
      state.storageWarning = false;
    } catch {
      state.storageWarning = true;
    }
  }
  render();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function cleanText(node) {
  return node?.textContent?.replace(/\s+/g, " ").trim() || "";
}

function numberFromText(value) {
  const digits = String(value || "").replace(/\D/g, "");
  return digits ? Number(digits) : null;
}

function decimalFromTitle(title, pattern) {
  const match = title.match(pattern);
  return match ? Number(match[1].replace(",", ".")) : null;
}

function parsePage(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const canonical = doc.querySelector('link[rel="canonical"]')?.getAttribute("href") || "";
  const pageCategory = canonical.includes("/kvartiry/") ? "apartment" : "house";
  const section = doc.querySelector("section.a-search-list");
  const subtitle = cleanText(doc.querySelector(".a-search-subtitle"));
  const countMatch = subtitle.match(/Найдено\s+([\d\s\u00a0]+)\s+объявлен/i);
  const found = countMatch ? numberFromText(countMatch[1]) : null;
  if (!section) {
    if (doc.querySelector(".a-search-empty") || found === 0) return [];
    throw new Error("Основной список объявлений не найден. Проверьте, что это сохранённая страница выдачи.");
  }
  const cards = [...section.querySelectorAll(".a-card[data-id]")];
  if (!cards.length && found !== 0 && !doc.querySelector(".a-search-empty")) {
    throw new Error("В файле есть список, но нет карточек. Возможно, изменилась разметка страницы.");
  }
  const ids = new Set();
  return cards.map((card) => {
    const id = card.getAttribute("data-id") || "";
    const titleNode = card.querySelector("a.a-card__title[href]");
    const title = cleanText(titleNode);
    const href = titleNode?.getAttribute("href") || "";
    const hrefId = href.match(/\/a\/show\/(\d+)(?:[/?#]|$)/)?.[1];
    if (!/^\d+$/.test(id) || !title || hrefId !== id || ids.has(id)) {
      throw new Error("Одна из карточек не содержит корректный ID, заголовок или ссылку.");
    }
    ids.add(id);
    const location = cleanText(card.querySelector(".a-card__subtitle"));
    const comma = location.indexOf(",");
    const stats = [...card.querySelectorAll(".a-card__stats-item")];
    const roomsMatch = title.match(/(\d+)\s+комнат(?:а|ы)?(?=\s|·|$)|(\d+)[-\s]комнатн\p{L}*/iu);
    const preview = cleanText(card.querySelector(".a-card__text-preview"));
    const floors = preview.match(/(\d+)\s*этаж(?:а|ей)?(?=\s|,|$)/iu);
    const year = preview.match(/((?:18|19|20)\d{2})\s*г\.?\s*п\.?(?=\s|,|$)/iu);
    const category = pageCategory === "apartment" || /квартир/iu.test(title) ? "apartment" : "house";
    const area = decimalFromTitle(title, /([\d.,]+)\s*м(?:²|2)(?=\s|·|$)/iu);
    const apartmentFloor = category === "apartment" ? title.match(/(\d+)\s*\/\s*(\d+)\s*этаж/iu) : null;
    const complex = category === "apartment" ? preview.match(/жил\.\s*комплекс\s+([^,]+)/iu) : null;
    return {
      id, url: `https://krisha.kz/a/show/${id}`, title,
      category,
      objectType: title.split("·")[0].trim(),
      rooms: roomsMatch ? Number(roomsMatch[1] || roomsMatch[2]) : null,
      houseArea: category === "house" ? area : null,
      apartmentArea: category === "apartment" ? area : null,
      plotArea: category === "house" ? decimalFromTitle(title, /([\d.,]+)\s*сот(?:ок|ки|ка)?\.?(?=\s|·|$)/iu) : null,
      floor: apartmentFloor ? Number(apartmentFloor[1]) : null,
      buildingFloors: apartmentFloor ? Number(apartmentFloor[2]) : null,
      residentialComplex: complex ? complex[1].trim() : null,
      price: numberFromText(cleanText(card.querySelector(".a-card__price"))),
      district: comma >= 0 ? location.slice(0, comma).trim() : "",
      address: comma >= 0 ? location.slice(comma + 1).trim() : location,
      preview,
      seller: cleanText(card.querySelector(".a-card__owner-label")) || cleanText(card.querySelector(".a-card__owner")),
      city: cleanText(stats[0]), posted: cleanText(stats[1]),
      floors: category === "house" && floors ? Number(floors[1]) : null,
      yearBuilt: year ? Number(year[1]) : null
    };
  });
}

function mergeImported(pages, demo, { cached = false, observedAt = new Date().toISOString() } = {}) {
  const retained = demo ? state.listings : state.listings.filter((item) => !item.demo);
  const next = new Map(retained.map((item) => [String(item.id), item]));
  let count = 0;
  for (const page of pages) {
    for (const item of page) {
      const previous = next.get(item.id);
      if (cached && previous) {
        const enriched = { ...previous };
        for (const key of ["latitude", "longitude", "geoSource", "geoZoom", "geoType"]) {
          if (enriched[key] == null && item[key] != null) enriched[key] = item[key];
        }
        next.set(item.id, enriched);
        continue;
      }
      const history = Array.isArray(previous?.history) ? [...previous.history] : [];
      if (item.price != null && (!history.length || history.at(-1).price !== item.price)) {
        history.push({ price: item.price, observedAt });
      }
      next.set(item.id, {
        ...item,
        category: item.category || previous?.category || "house",
        latitude: item.latitude ?? previous?.latitude ?? null,
        longitude: item.longitude ?? previous?.longitude ?? null,
        geoSource: item.geoSource ?? previous?.geoSource ?? null,
        geoZoom: item.geoZoom ?? previous?.geoZoom ?? null,
        geoType: item.geoType ?? previous?.geoType ?? null,
        price: item.price ?? previous?.price ?? null,
        firstSeenAt: previous?.firstSeenAt || observedAt,
        lastSeenAt: observedAt,
        history,
        demo: demo && (previous?.demo ?? true)
      });
      count++;
    }
  }
  save([...next.values()]);
  return count;
}

function setStatus(message, error = false) {
  const node = $("#status");
  node.textContent = message;
  node.classList.toggle("error", error);
  animateChange(node);
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
function animateChange(node) {
  if (!node || reducedMotion.matches || !node.animate) return;
  node.animate([{ opacity: .45, transform: "translateY(4px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 230, easing: "cubic-bezier(.22,1,.36,1)" });
}

function updateText(selector, value) {
  const node = $(selector);
  if (node.textContent === value) return;
  node.textContent = value;
  animateChange(node);
}

function formatPrice(price) {
  return price == null ? "Цена не указана" : `${numberFormat.format(price)} ₸`;
}

function formatArea(value, unit) {
  return value == null ? "" : `${numberFormat.format(value)} ${unit}`;
}

function medianOf(values) {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length ? (sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2) : null;
}

function compactMoney(value) {
  if (value == null) return "—";
  if (value >= 1_000_000) return `${decimalFormat.format(value / 1_000_000)} млн ₸`;
  if (value >= 1_000) return `${decimalFormat.format(value / 1_000)} тыс. ₸`;
  return `${numberFormat.format(Math.round(value))} ₸`;
}

function hasCoordinates(item) {
  return Number.isFinite(item.latitude) && Number.isFinite(item.longitude) &&
    Math.abs(item.latitude) <= 90 && Math.abs(item.longitude) <= 180 &&
    !(item.latitude === 0 && item.longitude === 0);
}

function analyticsRows(listings, category) {
  const areaKey = category === "apartment" ? "apartmentArea" : "houseArea";
  const unitKey = category === "apartment" ? "apartmentArea" : "plotArea";
  return listings.filter((item) => (item.category || "house") === category &&
    Number.isFinite(item.price) && item.price > 0 &&
    Number.isFinite(item[unitKey]) && item[unitKey] > 0
  ).map((item) => ({ item, unitPrice: item.price / item[unitKey], area: item[areaKey] }));
}

function distributionGroups(rows, category) {
  if (breakdownMode === "rooms") {
    const groups = [1, 2, 3, 4, 5].map((room) => ({ label: `${room} комн.`, rows: rows.filter(({ item }) => item.rooms === room) }));
    groups.push({ label: "6+ комн.", rows: rows.filter(({ item }) => Number.isFinite(item.rooms) && item.rooms >= 6) });
    return groups.filter((group) => group.rows.length);
  }
  const thresholds = category === "apartment" ? [0, 40, 60, 80, 120, Infinity] : [0, 80, 120, 180, 250, Infinity];
  return thresholds.slice(0, -1).map((lower, index) => {
    const upper = thresholds[index + 1];
    const label = index === 0 ? `< ${upper} м²` : upper === Infinity ? `${lower}+ м²` : `${lower}–${upper - 1} м²`;
    return { label, rows: rows.filter(({ area }) => Number.isFinite(area) && area >= lower && area < upper) };
  }).filter((group) => group.rows.length);
}

function renderAnalysis(visible) {
  const prices = visible.map((item) => item.price).filter((value) => Number.isFinite(value) && value > 0);
  const changes = visible.reduce((sum, item) => sum + Math.max(0, (item.history?.length || 0) - 1), 0);
  const geolocated = visible.filter(hasCoordinates).length;
  const houseRows = analyticsRows(visible, "house");
  const apartmentRows = analyticsRows(visible, "apartment");
  const categoryFilter = $("#category-filter").value;
  const mixedCategories = !categoryFilter && new Set(visible.map((item) => item.category || "house")).size > 1;
  const category = categoryFilter === "apartment" || (!houseRows.length && apartmentRows.length) ? "apartment" : "house";
  const rows = mixedCategories ? [] : category === "apartment" ? apartmentRows : houseRows;
  const unit = category === "apartment" ? "м²" : "сот.";
  const dated = visible.map((item) => item.lastSeenAt ? new Date(item.lastSeenAt) : null)
    .filter((date) => date && !Number.isNaN(date.getTime())).sort((a, b) => a - b);
  const latestDate = dated.at(-1);
  const earliestDate = dated[0];
  const mixedDates = latestDate && earliestDate &&
    latestDate.toDateString() !== earliestDate.toDateString();
  const recentCount = dated.filter((date) => Date.now() - date.getTime() >= 0 && Date.now() - date.getTime() <= 86_400_000).length;
  updateText("#data-freshness", latestDate ?
    `Последнее наблюдение: ${latestDate.toLocaleString("ru-RU")} · за 24 ч: ${recentCount} из ${visible.length}${mixedDates ? " · есть данные прежних дат" : ""}` :
    "Даты наблюдения в текущей выборке неизвестны.");
  const missingCoordinates = state.listings.filter((item) => !hasCoordinates(item)).length;
  $("#area-coverage-note").hidden = !currentSelection || !missingCoordinates;
  if (currentSelection && missingCoordinates) updateText("#area-coverage-note", `В каталоге ${numberFormat.format(missingCoordinates)} ${listingWord(missingCoordinates)} без координат: их принадлежность области неизвестна.`);
  updateText("#metric-count", numberFormat.format(visible.length));
  updateText("#metric-geo", numberFormat.format(geolocated));
  updateText("#metric-price", !mixedCategories && prices.length >= 5 ? compactMoney(medianOf(prices)) : "—");
  updateText("#metric-price-label", mixedCategories ? "выберите категорию" : `медиана цены · n=${prices.length}`);
  updateText("#metric-unit", !mixedCategories && rows.length >= 5 ? compactMoney(medianOf(rows.map((row) => row.unitPrice))) : "—");
  updateText("#metric-unit-label", mixedCategories ? "выберите категорию" : category === "apartment" ? `за 1 ${unit} · n=${rows.length}` : `цена объекта / ${unit} · n=${rows.length}`);
  updateText("#metric-changes", numberFormat.format(changes));
  updateText("#map-count", numberFormat.format(geolocated));
  updateText("#analysis-scope", `${numberFormat.format(visible.length)} из ${numberFormat.format(state.listings.length)} в текущей выборке`);
  updateText("#breakdown-title", mixedCategories ? "Сравнение стоимости" : category === "apartment" ? "Цена квартиры за м²" : "Цена объекта в расчёте на сотку");
  updateText("#analysis-note", mixedCategories ? "Выберите дома или квартиры: цены разных типов не объединяются." : category === "apartment" ? `Цена квартиры ÷ площадь · n=${rows.length}. Группы менее 5 объектов без медианы.` : `Цена дома с участком ÷ площадь участка · n=${rows.length}. Группы менее 5 объектов без медианы.`);
  const groups = distributionGroups(rows, category).map((group) => ({ label: group.label, count: group.rows.length, median: medianOf(group.rows.map((row) => row.unitPrice)) }));
  const maximum = Math.max(...groups.filter((group) => group.count >= 5).map((group) => group.median), 1);
  const container = $("#distribution");
  if (!groups.length) {
    container.innerHTML = `<p class="distribution-empty">${mixedCategories ? "Выберите категорию в фильтрах." : rows.length ? "Для этой группировки не хватает данных." : category === "apartment" ? "Нужны цена и площадь квартир." : "Нужны цена и площадь участков."}</p>`;
  } else {
    container.innerHTML = groups.map((group) => `<div class="distribution-row${group.count < 5 ? " is-small" : ""}"><span class="distribution-label">${escapeHtml(group.label)}</span><span class="distribution-track">${group.count >= 5 ? `<span class="distribution-fill" style="width:${Math.max(4, Math.round(group.median / maximum * 100))}%"></span>` : ""}</span><strong title="${group.count >= 5 ? escapeHtml(formatPrice(Math.round(group.median))) + ` за 1 ${unit}` : "Менее 5 объектов"}">${group.count >= 5 ? escapeHtml(compactMoney(group.median)) : "—"}</strong><span class="distribution-count">n=${numberFormat.format(group.count)}</span></div>`).join("");
  }
  animateChange(container);
}

function listingWord(count) {
  const lastTwo = count % 100;
  if (lastTwo >= 11 && lastTwo <= 14) return "объявлений";
  const last = count % 10;
  return last === 1 ? "объявление" : last >= 2 && last <= 4 ? "объявления" : "объявлений";
}

function vertexWord(count) {
  const lastTwo = count % 100;
  if (lastTwo >= 11 && lastTwo <= 14) return "вершин";
  const last = count % 10;
  return last === 1 ? "вершина" : last >= 2 && last <= 4 ? "вершины" : "вершин";
}

let polygonMap = null;
let polygonLayer = null;
let polygonVertices = [];
let polygonFinished = false;
let polygonDraftVertices = [];
let polygonDraftFinished = false;
let polygonDraftDrawing = false;

function pointOnSegment(point, start, end) {
  const [lat, lon] = point;
  const [lat1, lon1] = start;
  const [lat2, lon2] = end;
  const cross = (lon - lon1) * (lat2 - lat1) - (lat - lat1) * (lon2 - lon1);
  return Math.abs(cross) <= 1e-12 && lon >= Math.min(lon1, lon2) - 1e-12 && lon <= Math.max(lon1, lon2) + 1e-12 && lat >= Math.min(lat1, lat2) - 1e-12 && lat <= Math.max(lat1, lat2) + 1e-12;
}

function orientation(a, b, c) {
  return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1]);
}

function segmentsIntersect(a, b, c, d) {
  const ac = orientation(a, b, c), ad = orientation(a, b, d);
  const ca = orientation(c, d, a), cb = orientation(c, d, b);
  return ((ac > 0 && ad < 0 || ac < 0 && ad > 0) && (ca > 0 && cb < 0 || ca < 0 && cb > 0)) ||
    pointOnSegment(c, a, b) || pointOnSegment(d, a, b) || pointOnSegment(a, c, d) || pointOnSegment(b, c, d);
}

function validatePolygon(points) {
  if (!Array.isArray(points) || points.length < 3 || points.length > 100) throw new Error("Полигону нужны от 3 до 100 вершин.");
  if (points.some((point) => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite) || Math.abs(point[0]) > 90 || Math.abs(point[1]) > 180)) throw new Error("Некорректные координаты полигона.");
  if (new Set(points.map((point) => point.join(","))).size !== points.length) throw new Error("Вершины полигона не должны повторяться.");
  const area = points.reduce((sum, point, i) => {
    const next = points[(i + 1) % points.length];
    return sum + point[1] * next[0] - next[1] * point[0];
  }, 0);
  if (Math.abs(area) <= 1e-12) throw new Error("Полигон должен охватывать площадь.");
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      if (j === i + 1 || (i === 0 && j === points.length - 1)) continue;
      if (segmentsIntersect(points[i], points[(i + 1) % points.length], points[j], points[(j + 1) % points.length])) throw new Error("Стороны полигона не должны пересекаться.");
    }
  }
}

function polygonBounds(points) {
  const latitudes = points.map((point) => point[0]);
  const longitudes = points.map((point) => point[1]);
  return { north: Math.max(...latitudes), west: Math.min(...longitudes), south: Math.min(...latitudes), east: Math.max(...longitudes) };
}

function polygonContains(points, latitude, longitude) {
  let inside = false;
  for (let i = 0; i < points.length; i++) {
    const a = points[i], b = points[(i + 1) % points.length];
    if (pointOnSegment([latitude, longitude], a, b)) return true;
    if ((a[0] > latitude) !== (b[0] > latitude)) {
      const crossing = a[1] + (b[1] - a[1]) * (latitude - a[0]) / (b[0] - a[0]);
      if (longitude < crossing) inside = !inside;
    }
  }
  return inside;
}

function readAreaSelection() {
  if (collectionMode !== "map") return null;
  if (!$("#area-enabled").checked) return null;
  if ($("#area-mode").value === "polygon") {
    if (!polygonFinished) throw new Error("Завершите полигон на карте.");
    validatePolygon(polygonVertices);
    return { kind: "polygon", bounds: polygonBounds(polygonVertices), vertices: polygonVertices.map((point) => [...point]) };
  }
  const names = ["north", "west", "south", "east"];
  const values = names.map((name) => $("#area-" + name).value.trim());
  if (values.some((value) => !value)) throw new Error("Заполните четыре границы области.");
  const [north, west, south, east] = values.map(Number);
  if (![north, west, south, east].every(Number.isFinite)) throw new Error("Координаты области должны быть числами.");
  if (!(south >= -90 && north <= 90 && south < north)) throw new Error("Северная широта должна быть больше южной.");
  if (!(west >= -180 && east <= 180 && west < east)) throw new Error("Восточная долгота должна быть больше западной.");
  return { kind: "rectangle", bounds: { north, west, south, east } };
}

function areaQuery(bounds) {
  return [bounds.north, bounds.west, bounds.south, bounds.east].join(",");
}

function saveAreaSettings() {
  localStorage.setItem(AREA_KEY, JSON.stringify({
    collectionMode,
    city: $("#live-city").value,
    place: $("#live-place").value,
    enabled: $("#area-enabled").checked,
    mode: $("#area-mode").value,
    polygon: polygonFinished ? polygonVertices : [],
    north: $("#area-north").value, west: $("#area-west").value,
    south: $("#area-south").value, east: $("#area-east").value
  }));
}

function restoreAreaSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(AREA_KEY) || "null");
    if (!saved || typeof saved !== "object") return;
    if (collectionCities[saved.city]) $("#live-city").value = saved.city;
    if (typeof saved.place === "string" && saved.place.length <= 120) $("#live-place").value = saved.place;
    collectionMode = saved.collectionMode === "map" || (!saved.collectionMode && saved.enabled) ? "map" : "text";
    for (const name of ["north", "west", "south", "east"]) {
      if (saved[name] != null) $("#area-" + name).value = String(saved[name]);
    }
    $("#area-mode").value = saved.mode === "polygon" ? "polygon" : "rectangle";
    if (Array.isArray(saved.polygon) && saved.polygon.length) {
      validatePolygon(saved.polygon);
      polygonVertices = saved.polygon;
      polygonFinished = true;
    }
    $("#area-enabled").checked = saved.enabled === true && (saved.mode !== "polygon" || polygonFinished);
    $("#area-controls").open = false;
  } catch { /* Keep the example coordinates. */ }
}

function updatePolygonMap() {
  if (polygonLayer) {
    polygonLayer.clearLayers();
    if (polygonDraftVertices.length >= 3 && polygonDraftFinished) {
      L.polygon(polygonDraftVertices, { color: "#0071e3", weight: 3, fillColor: "#0071e3", fillOpacity: .18, interactive: false }).addTo(polygonLayer);
    } else if (polygonDraftVertices.length >= 2) {
      L.polyline(polygonDraftVertices, { color: "#0071e3", weight: 3, dashArray: "6 5", interactive: false }).addTo(polygonLayer);
    }
    for (const point of polygonDraftVertices) L.circleMarker(point, { radius: 6, color: "#fff", weight: 2, fillColor: "#0071e3", fillOpacity: 1, interactive: false }).addTo(polygonLayer);
  }
  $("#polygon-map").classList.toggle("is-drawing", polygonDraftDrawing);
  $("#polygon-undo").disabled = !polygonDraftDrawing || !polygonDraftVertices.length;
  $("#polygon-done").disabled = polygonDraftDrawing ? polygonDraftVertices.length < 3 : !polygonDraftVertices.length && !polygonFinished;
  $("#polygon-done").textContent = !polygonDraftDrawing && !polygonDraftVertices.length && polygonFinished ? "Удалить область" : "Сохранить область";
  $("#polygon-clear").disabled = !polygonDraftVertices.length;
  const message = polygonDraftFinished ? `Полигон: ${polygonDraftVertices.length} ${vertexWord(polygonDraftVertices.length)}. Можно сохранить или изменить.` : polygonDraftDrawing ? `Отмечено вершин: ${polygonDraftVertices.length}. После третьей сохраните область.` : polygonFinished ? "Область будет удалена после сохранения." : "Нажмите «Нарисовать заново», чтобы отметить область.";
  updateText("#polygon-message", message);
  $("#polygon-message").classList.remove("error");
}

function initAreaMap() {
  if (polygonMap) {
    requestAnimationFrame(() => polygonMap.invalidateSize());
    return;
  }
  if (!window.L) {
    $("#polygon-message").textContent = "Не удалось загрузить карту.";
    $("#polygon-message").classList.add("error");
    return;
  }
  polygonMap = L.map("polygon-map", { doubleClickZoom: false }).setView(collectionCities[$("#live-city").value].center, 13);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
  }).addTo(polygonMap);
  polygonLayer = L.layerGroup().addTo(polygonMap);
  polygonMap.on("click", (event) => {
    if (!polygonDraftDrawing) return;
    if (polygonDraftVertices.length >= 100) {
      $("#polygon-message").textContent = "Достигнут предел: 100 вершин.";
      $("#polygon-message").classList.add("error");
      return;
    }
    polygonDraftVertices.push([Number(event.latlng.lat.toFixed(6)), Number(event.latlng.lng.toFixed(6))]);
    updatePolygonMap();
  });
  if (polygonDraftFinished) polygonMap.fitBounds(polygonDraftVertices, { padding: [25, 25], maxZoom: 16 });
  updatePolygonMap();
  requestAnimationFrame(() => polygonMap.invalidateSize());
}

function showAreaMode() {
  const polygonMode = $("#area-mode").value === "polygon";
  $("#rectangle-fields").hidden = polygonMode;
  $("#polygon-mode-help").hidden = !polygonMode;
  animateChange(polygonMode ? $("#polygon-mode-help") : $("#rectangle-fields"));
  if (!polygonMode && $("#polygon-dialog").open) closePolygonDialog();
}

function showCollectionMode() {
  const mapMode = collectionMode === "map";
  $("#method-text").setAttribute("aria-pressed", String(!mapMode));
  $("#method-map").setAttribute("aria-pressed", String(mapMode));
  $("#text-location-controls").hidden = mapMode;
  $("#area-controls").hidden = !mapMode;
  animateChange(mapMode ? $("#area-controls") : $("#text-location-controls"));
}

function openPolygonDialog() {
  const dialog = $("#polygon-dialog");
  if (dialog.open) return;
  polygonDraftVertices = polygonVertices.map((point) => [...point]);
  polygonDraftFinished = polygonFinished;
  polygonDraftDrawing = false;
  dialog.showModal();
  initAreaMap();
  updatePolygonMap();
  if (polygonDraftFinished) polygonMap?.fitBounds(polygonDraftVertices, { padding: [25, 25], maxZoom: 16 });
  else polygonMap?.setView(collectionCities[$("#live-city").value].center, 13);
  requestAnimationFrame(() => polygonMap?.invalidateSize());
}

function closePolygonDialog() {
  const dialog = $("#polygon-dialog");
  if (!dialog.open || dialog.classList.contains("is-closing")) return;
  if (reducedMotion.matches) { dialog.close(); return; }
  dialog.classList.add("is-closing");
  setTimeout(() => { dialog.close(); dialog.classList.remove("is-closing"); }, 180);
}

function renderTypes() {
  const select = $("#type-filter");
  const selected = select.value;
  const category = $("#category-filter").value;
  const types = [...new Set(state.listings.filter((item) => !category || (item.category || "house") === category).map((item) => item.objectType).filter(Boolean))].sort();
  select.replaceChildren(new Option("Все типы", ""), ...types.map((type) => new Option(type, type)));
  select.value = types.includes(selected) ? selected : "";
}

function locationKey(value) {
  return String(value || "").toLocaleLowerCase("ru").replaceAll("ё", "е")
    .replace(/микрорайон|мкр-?н/gu, "мкр").replace(/\s+/g, " ").trim();
}

function microdistrictFromAddress(address) {
  const match = String(address || "").match(/(?:^|[\s,;])(?:мкр(?:-?н)?\.?|микрорайон)\s+([^\s,;—]+)/iu);
  return match ? `мкр ${match[1]}` : "";
}

function placeLookupKey(value) {
  return locationKey(value).replace(/^мкр\.?\s+|^район\s+/u, "").replace(/\s+(?:р-н|район)$/u, "").trim();
}

function knownPlaceForText(city, value) {
  const key = placeLookupKey(value);
  return key ? knownPlaces.find((place) => place.city === city && placeLookupKey(place.label) === key) || null : null;
}

function matchesPlace(value, term) {
  if (!value) return false;
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`, "u").test(placeLookupKey(value));
}

function locationSuggestions() {
  const city = $("#live-city").value;
  const places = new Map(knownPlaces.filter((place) => place.city === city)
    .map((place) => [placeLookupKey(place.label), { ...place, value: place.label.replace(/^мкр\s+/iu, "") }]));
  for (const item of state.listings) {
    if (item.city !== collectionCities[city].name) continue;
    for (const label of [item.district, microdistrictFromAddress(item.address)]) {
      if (!label) continue;
      const key = placeLookupKey(label);
      const value = label.replace(/^мкр\s+/iu, "");
      if (!places.has(key)) places.set(key, { label, value, city });
    }
  }
  return [...places.values()].sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

function updateLocationHint() {
  const place = $("#live-place").value.trim();
  const known = knownPlaceForText($("#live-city").value, place);
  updateText("#location-note", !place ? "Поиск по всему городу." : known ?
    "Krisha отфильтрует выдачу по выбранной области." :
    "Сервис проверит адреса на загруженных страницах города. Для полного охвата выберите «Все страницы».");
}

function closePlaceSuggestions() {
  $("#live-place").setAttribute("aria-expanded", "false");
  $("#live-place").closest(".place-combobox").classList.remove("is-open");
}

function showPlaceSuggestions() {
  const input = $("#live-place");
  const menu = $("#place-suggestions");
  const query = locationKey(input.value);
  const suggestions = locationSuggestions().filter((place) => !query || locationKey(place.label).includes(query) || locationKey(place.value).includes(query)).slice(0, 8);
  menu.replaceChildren();
  for (const place of suggestions) {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.className = "place-suggestion";
    choice.setAttribute("role", "option");
    choice.setAttribute("aria-selected", String(locationKey(place.value) === query));
    const name = document.createElement("span");
    name.textContent = place.label;
    choice.append(name);
    choice.addEventListener("click", () => {
      input.value = place.value;
      closePlaceSuggestions();
      saveAreaSettings();
      render();
      input.focus();
      closePlaceSuggestions();
    });
    menu.append(choice);
  }
  const open = suggestions.length > 0 && document.activeElement === input;
  input.closest(".place-combobox").classList.toggle("opens-up", input.getBoundingClientRect().bottom + Math.min(menu.scrollHeight, 230) + 10 > innerHeight);
  input.setAttribute("aria-expanded", String(open));
  input.closest(".place-combobox").classList.toggle("is-open", open);
}

function selectionContains(selection, latitude, longitude) {
  if (!selection) return true;
  const bounds = selection.bounds;
  return Number.isFinite(latitude) && Number.isFinite(longitude) &&
    latitude >= bounds.south && latitude <= bounds.north && longitude >= bounds.west && longitude <= bounds.east &&
    (selection.kind !== "polygon" || polygonContains(selection.vertices, latitude, longitude));
}

function getVisibleListings(selection) {
  const search = $("#search").value.trim().toLocaleLowerCase("ru");
  const category = $("#category-filter").value;
  const type = $("#type-filter").value;
  const city = collectionMode === "text" ? collectionCities[$("#live-city").value].name : null;
  const place = collectionMode === "text" ? placeLookupKey($("#live-place").value) : "";
  const sort = $("#sort").value;
  const visible = state.listings.filter((item) =>
    selectionContains(selection, item.latitude, item.longitude) &&
    (!category || (item.category || "house") === category) &&
    (!type || item.objectType === type) &&
    (!city || item.city === city) &&
    (!place || [item.district, item.address].some((field) => matchesPlace(field, place))) &&
    (!search || [item.id, item.title, item.address, item.district, item.residentialComplex, item.preview].some((field) => String(field || "").toLocaleLowerCase("ru").includes(search)))
  );
  if (sort === "price-asc") visible.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
  else if (sort === "price-desc") visible.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
  else if (sort === "area-desc") visible.sort((a, b) => (b.apartmentArea ?? b.houseArea ?? -Infinity) - (a.apartmentArea ?? a.houseArea ?? -Infinity));
  else visible.sort((a, b) => (Date.parse(b.lastSeenAt || "") || 0) - (Date.parse(a.lastSeenAt || "") || 0) || Number(b.id) - Number(a.id));
  return visible;
}

function closeMapCard() {
  $("#map-card").classList.remove("is-visible");
  if (selectedMapMarker) selectedMapMarker.setStyle({ fillColor: "#1d1d1f" });
  selectedMapMarker = null;
}

function initResultsMap() {
  if (resultsMap || !window.L) return;
  resultsMap = L.map("results-map", { scrollWheelZoom: false }).setView([43.249, 76.9], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
  }).addTo(resultsMap);
  resultsAreaLayer = L.layerGroup().addTo(resultsMap);
  resultsMapLayer = L.layerGroup().addTo(resultsMap);
}

function updateResultsMap(visible, selection) {
  if ($("#results-map-panel").hidden) return;
  const geocoded = visible.filter(hasCoordinates);
  $("#results-map-empty").hidden = Boolean(geocoded.length);
  closeMapCard();
  if (!geocoded.length) {
    resultsMapLayer?.clearLayers();
    resultsAreaLayer?.clearLayers();
    return;
  }
  initResultsMap();
  if (!resultsMap) {
    $("#results-map-empty").hidden = false;
    $("#results-map-empty").textContent = "Не удалось загрузить карту.";
    return;
  }
  requestAnimationFrame(() => resultsMap.invalidateSize());
  resultsMapLayer.clearLayers();
  resultsAreaLayer.clearLayers();
  if (selection) {
    const outline = { color: "#0071e3", weight: 2, fillOpacity: 0, interactive: false, dashArray: "5 5" };
    if (selection.kind === "polygon") L.polygon(selection.vertices, outline).addTo(resultsAreaLayer);
    else L.rectangle([[selection.bounds.south, selection.bounds.west], [selection.bounds.north, selection.bounds.east]], outline).addTo(resultsAreaLayer);
  }
  for (const item of geocoded) {
    const marker = L.circleMarker([item.latitude, item.longitude], { radius: 7, color: "#fff", weight: 2, fillColor: "#1d1d1f", fillOpacity: 1, className: "results-marker" }).addTo(resultsMapLayer);
    marker.on("mouseover", () => marker.setStyle({ fillColor: "#0071e3" }));
    marker.on("mouseout", () => { if (selectedMapMarker !== marker) marker.setStyle({ fillColor: "#1d1d1f" }); });
    marker.on("click", () => {
      closeMapCard();
      selectedMapMarker = marker;
      marker.setStyle({ fillColor: "#0071e3" });
      $("#map-card-content").innerHTML = `<span class="map-card-label">№ ${escapeHtml(item.id)} · ${item.category === "apartment" ? "Квартира" : "Дом / дача"}</span><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(formatPrice(item.price))}</span><span>${escapeHtml([item.district, item.address].filter(Boolean).join(", ") || "Адрес не указан")}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">Открыть объявление</a>`;
      $("#map-card").classList.add("is-visible");
    });
  }
  const points = geocoded.map((item) => [item.latitude, item.longitude]);
  if (points.length === 1) resultsMap.setView(points[0], 15, { animate: true });
  else resultsMap.fitBounds(points, { padding: [38, 38], maxZoom: 16, animate: true });
}

async function setResultsView(view) {
  if (viewTransitioning || view === resultsView) return;
  viewTransitioning = true;
  const oldPanel = resultsView === "table" ? $("#listings") : $("#results-map-panel");
  const nextPanel = view === "table" ? $("#listings") : $("#results-map-panel");
  resultsView = view;
  $("#view-table").setAttribute("aria-pressed", String(view === "table"));
  $("#view-map").setAttribute("aria-pressed", String(view === "map"));
  $("#view-table").disabled = $("#view-map").disabled = true;
  try {
    if (!reducedMotion.matches && oldPanel.animate) {
      await oldPanel.animate([{ opacity: 1, transform: "translateY(0)" }, { opacity: 0, transform: "translateY(9px)" }], { duration: 170, easing: "ease-in" }).finished;
    }
    oldPanel.hidden = true;
    nextPanel.hidden = false;
    if (view === "map") updateResultsMap(currentVisible, currentSelection);
    if (!reducedMotion.matches && nextPanel.animate) {
      await nextPanel.animate([{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 290, easing: "cubic-bezier(.22,1,.36,1)" }).finished;
    }
  } finally {
    $("#view-table").disabled = $("#view-map").disabled = false;
    viewTransitioning = false;
  }
}

function render() {
  const listings = state.listings;
  $("#clear-button").disabled = !listings.length;
  $("#demo-button").disabled = listings.some((item) => !item.demo);
  renderTypes();
  updateLocationHint();

  let selection = null;
  let areaError = null;
  try { selection = readAreaSelection(); } catch (error) { areaError = error.message; }
  const areaMessage = $("#area-message");
  updateText("#area-message", areaError || (selection ? (selection.kind === "polygon" ? `Активный полигон: ${selection.vertices.length} ${vertexWord(selection.vertices.length)}. Охватывающий прямоугольник: ${areaQuery(selection.bounds)}` : `Активная область: ${areaQuery(selection.bounds)}`) : "Область не ограничена."));
  areaMessage.classList.toggle("error", Boolean(areaError));
  updateText("#area-summary", areaError ? "Проверьте координаты" : selection ? (selection.kind === "polygon" ? `Полигон · ${selection.vertices.length} ${vertexWord(selection.vertices.length)}` : "Прямоугольник") : "Весь город");
  const visible = areaError ? [] : getVisibleListings(selection);
  const freshData = renderedRevision !== state.revision;
  renderedRevision = state.revision;
  currentVisible = visible;
  currentSelection = selection;
  renderAnalysis(visible);
  $("#export-button").disabled = !visible.length;

  updateText("#visible-count", numberFormat.format(visible.length));
  const container = $("#listings");
  const previousScroll = container.querySelector(".table-scroll");
  const previousPosition = { top: previousScroll?.scrollTop || 0, left: previousScroll?.scrollLeft || 0 };
  const signature = visible.map((item) => item.id).join(",");
  const keepPosition = signature === lastVisibleSignature;
  lastVisibleSignature = signature;
  if (!visible.length) {
    const initial = !listings.length;
    container.innerHTML = `<div class="empty"><h3>${initial ? "Пока нет объявлений" : "Ничего не найдено"}</h3><p>${initial ? "Соберите объявления или загрузите сохранённый HTML." : areaError || (selection ? "Измените область или фильтры каталога." : "Измените запрос или фильтры.")}</p></div>`;
    if (!container.hidden) animateChange(container);
    if (resultsView === "map") updateResultsMap(visible, selection);
    return;
  }
  const rows = visible.slice(0, shownCount).map((item) => {
    const isApartment = item.category === "apartment";
    const details = [
      item.rooms && `${item.rooms} комн.`,
      formatArea(isApartment ? item.apartmentArea : item.houseArea, "м²"),
      isApartment && item.floor && item.buildingFloors ? `${item.floor}/${item.buildingFloors} этаж` : null,
      isApartment ? item.residentialComplex : formatArea(item.plotArea, "сот.")
    ].filter(Boolean);
    const changeCount = Math.max(0, (item.history?.length || 0) - 1);
    const hasGeo = hasCoordinates(item);
    const geoUrl = hasGeo ? `https://www.openstreetmap.org/?mlat=${item.latitude}&mlon=${item.longitude}#map=16/${item.latitude}/${item.longitude}` : "";
    const address = [item.district, item.address].filter(Boolean).join(", ") || "Адрес не указан";
    const detail = [item.preview ? `<p>${escapeHtml(item.preview)}</p>` : "", hasGeo ? `<p>Координаты: ${escapeHtml(item.latitude)}, ${escapeHtml(item.longitude)} · <a href="${escapeHtml(geoUrl)}" target="_blank" rel="noopener noreferrer">Открыть на карте ↗</a></p>` : "", changeCount ? `<p>Изменений цены: ${changeCount}</p>` : "", item.seller ? `<p>Продавец: ${escapeHtml(item.seller)}</p>` : ""].filter(Boolean).join("");
    return `<tr class="listing-row">
      <td class="object-cell"><a class="object-title" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a><span class="object-meta">№ ${escapeHtml(item.id)} · ${isApartment ? "Квартира" : "Дом / дача"}${item.demo ? " · Демо" : ""}</span></td>
      <td class="price-cell">${escapeHtml(formatPrice(item.price))}</td>
      <td class="parameters-cell">${details.length ? details.map(escapeHtml).join(" · ") : "—"}</td>
      <td class="address-cell">${escapeHtml(address)}</td>
      <td class="geo-cell">${hasGeo ? '<span class="geo-dot" aria-hidden="true"></span>Есть' : "—"}</td>
      <td class="detail-cell"><button type="button" class="row-expand" data-detail-id="${escapeHtml(item.id)}" aria-expanded="false" aria-label="Подробнее об объекте № ${escapeHtml(item.id)}">⌄</button></td>
    </tr><tr class="detail-row" data-detail-row="${escapeHtml(item.id)}" hidden><td colspan="6"><div class="detail-content">${detail || "Дополнительных сведений нет."}<span class="detail-posted">${escapeHtml(item.posted || "")}</span></div></td></tr>`;
  }).join("");
  container.innerHTML = `<div class="table-scroll"><table class="results-table"><caption class="sr-only">Собранные объявления</caption><thead><tr><th scope="col">Объект</th><th scope="col">Цена</th><th scope="col">Параметры</th><th scope="col">Расположение</th><th scope="col">Карта</th><th scope="col"><span class="sr-only">Детали</span></th></tr></thead><tbody>${rows}</tbody></table></div>`;
  const scroll = container.querySelector(".table-scroll");
  if (keepPosition) { scroll.scrollTop = previousPosition.top; scroll.scrollLeft = previousPosition.left; }
  if (visible.length > shownCount) {
    container.insertAdjacentHTML("beforeend", `<button type="button" class="secondary-button" id="show-more">Показать ещё 100 из ${numberFormat.format(visible.length)}</button>`);
    $("#show-more").addEventListener("click", () => { shownCount += 100; render(); });
  }
  if (!container.hidden) {
    if (freshData && !reducedMotion.matches) {
      scroll.animate([{ opacity: 0, transform: "translateY(16px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 420, easing: "cubic-bezier(.22,1,.36,1)" });
      [...scroll.querySelectorAll(".listing-row")].slice(0, 8).forEach((row, index) => row.animate([{ opacity: 0, transform: "translateY(9px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 330, delay: 90 + index * 38, easing: "cubic-bezier(.22,1,.36,1)", fill: "backwards" }));
    } else animateChange(scroll);
  }
  if (resultsView === "map") updateResultsMap(visible, selection);
}

function csvCell(value) {
  let text = String(value ?? "");
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

async function exportCsv() {
  let selection;
  try { selection = readAreaSelection(); } catch (error) { setStatus(error.message, true); return; }
  const visible = getVisibleListings(selection);
  if (isLocalHost) {
    try {
      const response = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: visible.map((item) => Number(item.id)) }) });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "Не удалось выгрузить данные из SQLite.");
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = $("#category-filter").value === "apartment" ? "krisha-apartments.csv" : "krisha-list.csv";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setStatus(`Экспортировано ${visible.length} ${listingWord(visible.length)} из SQLite. Учтены текущая область и фильтры.`);
    } catch (error) { setStatus(error.message, true); }
    return;
  }
  const fields = ["id", "url", "category", "title", "objectType", "rooms", "houseArea", "apartmentArea", "plotArea", "floor", "buildingFloors", "residentialComplex", "price", "district", "address", "latitude", "longitude", "geoSource", "geoZoom", "geoType", "preview", "seller", "city", "posted", "floors", "yearBuilt", "firstSeenAt", "lastSeenAt", "priceChanges", "demo"];
  const rows = [fields.join(","), ...visible.map((item) => fields.map((field) => csvCell(field === "priceChanges" ? Math.max(0, (item.history?.length || 0) - 1) : item[field])).join(","))];
  const blob = new Blob(["\ufeff", rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = $("#category-filter").value === "apartment" ? "krisha-apartments.csv" : "krisha-list.csv";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  setStatus(`Экспортировано ${visible.length} ${listingWord(visible.length)} из ${state.listings.length}. Учтены текущая область и фильтры каталога.`);
}

$("#html-files").addEventListener("change", async (event) => {
  const files = [...event.target.files];
  if (!files.length) return;
  try {
    if (isLocalHost) {
      let count = 0;
      try {
        for (const file of files) {
          if (file.size > 15 * 1024 * 1024) throw new Error(`${file.name}: файл больше 15 МБ.`);
          const response = await fetch("/api/import-html", { method: "POST", headers: { "Content-Type": "text/html; charset=utf-8" }, body: await file.text() });
          const result = await response.json();
          if (!response.ok) throw new Error(`${file.name}: ${result.error || "не удалось импортировать"}`);
          count += result.unique_ids;
        }
      } finally {
        await refreshCatalog();
      }
      setStatus(`Импортировано ${count} карточек из ${files.length} HTML-файлов в SQLite.`);
      return;
    }
    const pages = [];
    for (const file of files) {
      if (file.size > 15 * 1024 * 1024) throw new Error(`${file.name}: файл больше 15 МБ.`);
      pages.push(parsePage(await file.text()));
    }
    const count = mergeImported(pages, false);
    setStatus(`Добавлено или обновлено: ${count}. Файлов: ${files.length}.`);
  } catch (error) {
    setStatus(error.message || "Не удалось прочитать файл.", true);
  } finally { event.target.value = ""; }
});
$(".upload-button").addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    $("#html-files").click();
  }
});

$("#demo-button").addEventListener("click", async () => {
  try {
    const response = await fetch("sample.html");
    if (!response.ok) throw new Error("Демонстрационный файл недоступен.");
    const count = mergeImported([parsePage(await response.text())], true);
    setStatus(`Загружено ${count} демонстрационных объекта. Это вымышленные данные.`);
  } catch (error) {
    setStatus(error.message || "Не удалось открыть пример.", true);
  }
});

$("#search").addEventListener("input", render);
$("#live-city").addEventListener("change", () => {
  $("#live-place").value = "";
  $("#area-enabled").checked = false;
  closePlaceSuggestions();
  saveAreaSettings();
  render();
});
$("#method-text").addEventListener("click", () => {
  collectionMode = "text";
  showCollectionMode();
  saveAreaSettings();
  render();
});
$("#method-map").addEventListener("click", () => {
  collectionMode = "map";
  showCollectionMode();
  saveAreaSettings();
  render();
});
$("#live-place").addEventListener("input", () => { saveAreaSettings(); render(); showPlaceSuggestions(); });
$("#live-place").addEventListener("focus", showPlaceSuggestions);
$("#live-place").addEventListener("keydown", (event) => {
  if (event.key === "Escape") closePlaceSuggestions();
  if (event.key === "ArrowDown" && $("#live-place").getAttribute("aria-expanded") === "true") {
    event.preventDefault();
    $("#place-suggestions .place-suggestion")?.focus();
  }
});
$("#place-suggestions").addEventListener("keydown", (event) => {
  const choices = [...$("#place-suggestions").querySelectorAll(".place-suggestion")];
  const current = choices.indexOf(document.activeElement);
  if (event.key === "Escape") { event.preventDefault(); $("#live-place").focus(); closePlaceSuggestions(); }
  else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1 :
      (current + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
    choices[next]?.focus();
  }
});
$("#live-place").closest(".place-combobox").addEventListener("focusout", (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) closePlaceSuggestions();
});
document.addEventListener("pointerdown", (event) => {
  if (!$("#live-place").closest(".place-combobox").contains(event.target)) closePlaceSuggestions();
});
for (const id of ["area-enabled", "area-north", "area-west", "area-south", "area-east"]) {
  $("#" + id).addEventListener("input", () => { saveAreaSettings(); render(); });
  $("#" + id).addEventListener("change", () => { saveAreaSettings(); render(); });
}
$("#area-mode").addEventListener("change", () => {
  if ($("#area-mode").value === "polygon" && !polygonFinished) $("#area-enabled").checked = false;
  showAreaMode();
  saveAreaSettings();
  render();
});
$("#area-controls").addEventListener("toggle", showAreaMode);
$("#open-polygon-map").addEventListener("click", openPolygonDialog);
$("#close-polygon-map").addEventListener("click", closePolygonDialog);
$("#polygon-cancel").addEventListener("click", closePolygonDialog);
$("#polygon-dialog").addEventListener("cancel", (event) => { event.preventDefault(); closePolygonDialog(); });
$("#polygon-dialog").addEventListener("click", (event) => {
  if (event.target === $("#polygon-dialog")) closePolygonDialog();
});
$("#polygon-start").addEventListener("click", () => {
  polygonDraftVertices = [];
  polygonDraftFinished = false;
  polygonDraftDrawing = true;
  updatePolygonMap();
});
$("#polygon-undo").addEventListener("click", () => {
  if (!polygonDraftDrawing) return;
  polygonDraftVertices.pop();
  updatePolygonMap();
});
$("#polygon-done").addEventListener("click", () => {
  try {
    if (polygonDraftVertices.length) validatePolygon(polygonDraftVertices);
    polygonVertices = polygonDraftVertices.map((point) => [...point]);
    polygonFinished = polygonVertices.length >= 3;
    polygonDraftFinished = polygonFinished;
    polygonDraftDrawing = false;
    $("#area-mode").value = "polygon";
    showAreaMode();
    collectionMode = "map";
    showCollectionMode();
    $("#area-enabled").checked = polygonFinished;
    updatePolygonMap();
    saveAreaSettings();
    render();
    closePolygonDialog();
  } catch (error) {
    $("#polygon-message").textContent = error.message;
    $("#polygon-message").classList.add("error");
  }
});
$("#polygon-clear").addEventListener("click", () => {
  polygonDraftVertices = [];
  polygonDraftFinished = false;
  polygonDraftDrawing = false;
  updatePolygonMap();
});
$("#category-filter").addEventListener("change", render);
$("#type-filter").addEventListener("change", render);
$("#sort").addEventListener("change", render);
$("#view-table").addEventListener("click", () => setResultsView("table"));
$("#view-map").addEventListener("click", () => setResultsView("map"));
$("#map-card-close").addEventListener("click", closeMapCard);
for (const mode of ["rooms", "area"]) {
  $(mode === "rooms" ? "#group-rooms" : "#group-area").addEventListener("click", () => {
    if (breakdownMode === mode) return;
    breakdownMode = mode;
    $("#group-rooms").setAttribute("aria-pressed", String(mode === "rooms"));
    $("#group-area").setAttribute("aria-pressed", String(mode === "area"));
    renderAnalysis(currentVisible);
  });
}
$("#listings").addEventListener("click", (event) => {
  const button = event.target.closest(".row-expand");
  if (!button) return;
  const row = [...$("#listings").querySelectorAll(".detail-row")].find((candidate) => candidate.dataset.detailRow === button.dataset.detailId);
  if (!row) return;
  const content = row.querySelector(".detail-content");
  content.getAnimations().forEach((animation) => animation.cancel());
  const opening = button.getAttribute("aria-expanded") !== "true";
  if (opening) row.hidden = false;
  button.setAttribute("aria-expanded", String(opening));
  if (opening) animateChange(content);
  else if (reducedMotion.matches || !content.animate) row.hidden = true;
  else {
    const animation = content.animate([{ opacity: 1, transform: "translateY(0)" }, { opacity: 0, transform: "translateY(-5px)" }], { duration: 170, easing: "ease-in" });
    animation.onfinish = () => { if (button.getAttribute("aria-expanded") === "false") row.hidden = true; };
  }
});
for (const disclosure of document.querySelectorAll("details")) {
  const summary = disclosure.querySelector(":scope > summary");
  summary?.addEventListener("click", (event) => {
    if (reducedMotion.matches || !disclosure.animate) return;
    event.preventDefault();
    const motionId = (disclosure._motionId || 0) + 1;
    disclosure._motionId = motionId;
    if (disclosure.dataset.closing) {
      disclosure._motion?.forEach((animation) => animation.cancel());
      delete disclosure.dataset.closing;
      disclosure.style.overflow = "";
      return;
    }
    disclosure._motion?.forEach((animation) => animation.cancel());
    const content = [...disclosure.children].filter((child) => child.tagName !== "SUMMARY");
    const popup = disclosure.classList.contains("filter-disclosure") || disclosure.classList.contains("run-disclosure");
    const closing = disclosure.open;
    const summaryHeight = summary.getBoundingClientRect().height;
    const fullHeight = closing ? disclosure.scrollHeight : 0;
    if (!closing) disclosure.open = true;
    const expandedHeight = closing ? fullHeight : disclosure.scrollHeight;
    if (!popup) disclosure.style.overflow = "hidden";
    if (closing) disclosure.dataset.closing = "true";
    const options = { duration: closing ? 190 : 280, easing: closing ? "ease-in" : "cubic-bezier(.22,1,.36,1)" };
    disclosure._motion = [
      ...(!popup ? [disclosure.animate([{ height: `${closing ? expandedHeight : summaryHeight}px` }, { height: `${closing ? summaryHeight : expandedHeight}px` }], options)] : []),
      ...content.map((child) => child.animate(closing ? [{ opacity: 1 }, { opacity: 0 }] : [{ opacity: 0, transform: "translateY(-6px)" }, { opacity: 1, transform: "translateY(0)" }], options))
    ];
    Promise.allSettled(disclosure._motion.map((animation) => animation.finished)).then(() => {
      if (disclosure._motionId !== motionId) return;
      if (closing && disclosure.dataset.closing) disclosure.open = false;
      delete disclosure.dataset.closing;
      disclosure.style.overflow = "";
      disclosure._motion = [];
    });
  });
}
$("#export-button").addEventListener("click", exportCsv);
$("#clear-button").addEventListener("click", () => {
  if (!confirm("Удалить все объявления, сохранённые в этом браузере?")) return;
  save([]);
  setStatus("Каталог очищен.");
});

let liveEnabled = false;
if (isLocalHost) {
  $("#clear-button").hidden = true;
  $("#demo-button").hidden = true;
  $("#catalog-source-note").textContent = "Каталог и история цен сохранены в локальной базе SQLite.";
  $("#run-toolbar").hidden = false;
}
function updateLinkSummary() {
  updateText("#filter-link-summary", $("#live-search-url").value.trim() ? "Ссылка задана" : "По умолчанию");
}

let openSelectShell = null;
function closeSelectMenu(shell = openSelectShell) {
  if (!shell) return;
  shell.classList.remove("is-open");
  shell.querySelector("select")?.setAttribute("aria-expanded", "false");
  if (openSelectShell === shell) openSelectShell = null;
}

function openSelectMenu(shell) {
  if (openSelectShell && openSelectShell !== shell) closeSelectMenu();
  const select = shell.querySelector("select");
  const menu = shell.querySelector(".select-popup");
  menu.replaceChildren();
  for (const option of select.options) {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.className = "select-option";
    choice.setAttribute("role", "option");
    choice.setAttribute("aria-selected", String(option.value === select.value));
    choice.disabled = option.disabled;
    choice.textContent = option.textContent;
    choice.addEventListener("click", () => {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      closeSelectMenu(shell);
      select.focus();
    });
    menu.append(choice);
  }
  shell.classList.toggle("opens-up", select.getBoundingClientRect().bottom + Math.min(menu.scrollHeight, 220) + 10 > innerHeight);
  shell.classList.add("is-open");
  select.setAttribute("aria-expanded", "true");
  openSelectShell = shell;
  menu.querySelector('[aria-selected="true"]')?.focus({ preventScroll: true });
}

function enhanceSelectMenus() {
  for (const select of document.querySelectorAll("select")) {
    const shell = document.createElement("span");
    shell.className = "select-shell";
    const menu = document.createElement("span");
    menu.id = `${select.id}-menu`;
    menu.className = "select-popup";
    menu.setAttribute("role", "listbox");
    const label = document.querySelector(`label[for="${select.id}"]`)?.textContent || select.closest("label")?.querySelector("span")?.textContent || "Выберите значение";
    menu.setAttribute("aria-label", label.trim());
    select.setAttribute("aria-haspopup", "listbox");
    select.setAttribute("aria-controls", menu.id);
    select.setAttribute("aria-expanded", "false");
    select.before(shell);
    shell.append(select, menu);
    select.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      select.focus({ preventScroll: true });
      shell.classList.contains("is-open") ? closeSelectMenu(shell) : openSelectMenu(shell);
    });
    select.addEventListener("click", (event) => event.preventDefault());
    select.addEventListener("keydown", (event) => {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        if (!shell.classList.contains("is-open")) openSelectMenu(shell);
      } else if (event.key === "Escape" && shell.classList.contains("is-open")) {
        event.preventDefault();
        closeSelectMenu(shell);
      }
    });
    menu.addEventListener("keydown", (event) => {
      const choices = [...menu.querySelectorAll(".select-option:not(:disabled)")];
      const current = choices.indexOf(document.activeElement);
      if (event.key === "Escape") { event.preventDefault(); closeSelectMenu(shell); select.focus(); }
      else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1 : (current + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
        choices[next]?.focus();
      }
    });
    shell.addEventListener("focusout", (event) => { if (!shell.contains(event.relatedTarget)) closeSelectMenu(shell); });
  }
  document.addEventListener("pointerdown", (event) => { if (openSelectShell && !openSelectShell.contains(event.target)) closeSelectMenu(); });
}
$("#live-search-url").addEventListener("input", updateLinkSummary);
if (isLocalHost) $("#collect-button").disabled = true;
fetch("/api/status", { cache: "no-store" }).then(async (response) => {
  if (!response.ok) return;
  const status = await response.json();
  if (isLocalHost) await initializeLocalCatalog();
  if (!status.live_enabled) return;
  liveEnabled = true;
  $("#live-local-hint").hidden = true;
  $("#live-controls").hidden = false;
  $("#collect-button").disabled = false;
}).catch((error) => { if (isLocalHost) setStatus(`Не удалось открыть локальную базу: ${error.message}`, true); });

function restoreCollectionHandoff() {
  const prefix = "#collect=";
  if (!isLocalHost || !window.location.hash.startsWith(prefix)) return;
  try {
    const request = JSON.parse(decodeURIComponent(window.location.hash.slice(prefix.length)));
    if (!request || typeof request !== "object") throw new Error("Параметры сбора не распознаны.");
    if (collectionCities[request.city]) $("#live-city").value = request.city;
    if (typeof request.place === "string" && request.place.length <= 120) $("#live-place").value = request.place;
    collectionMode = request.collectionMode === "text" ? "text" : request.collectionMode === "map" || request.area ? "map" : "text";
    const area = request.area;
    if (area?.kind === "polygon") {
      validatePolygon(area.vertices);
      polygonVertices = area.vertices.map((point) => [...point]);
      polygonFinished = true;
      polygonDraftDrawing = false;
      $("#area-mode").value = "polygon";
      $("#area-enabled").checked = true;
    } else if (area?.kind === "rectangle") {
      const bounds = area.bounds;
      if (!bounds || ![bounds.north, bounds.west, bounds.south, bounds.east].every(Number.isFinite) ||
        !(bounds.south >= -90 && bounds.north <= 90 && bounds.south < bounds.north) ||
        !(bounds.west >= -180 && bounds.east <= 180 && bounds.west < bounds.east)) throw new Error("Некорректные границы области.");
      for (const name of ["north", "west", "south", "east"]) $("#area-" + name).value = String(bounds[name]);
      $("#area-mode").value = "rectangle";
      $("#area-enabled").checked = true;
    } else if (area == null) {
      $("#area-enabled").checked = false;
    } else {
      throw new Error("Тип области не распознан.");
    }
    $("#area-controls").open = Boolean(area);
    $("#live-category").value = request.category === "apartment" ? "apartment" : "house";
    $("#live-pages").value = [0, 1, 10].includes(request.pages) ? String(request.pages) : "1";
    $("#live-search-url").value = typeof request.url === "string" && request.url.length <= 2048 ? request.url : "";
    showCollectionMode();
    saveAreaSettings();
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    setStatus("Параметры перенесены. Нажмите «Собрать объявления» для запуска.");
  } catch (error) {
    setStatus(error.message || "Не удалось перенести параметры сбора.", true);
  }
}

function fromServer(item) {
  return {
    id: String(item.id), url: item.url, title: item.title,
    category: item.category || "house",
    objectType: item.object_type, rooms: item.rooms,
    houseArea: item.house_area_m2, apartmentArea: item.apartment_area_m2,
    plotArea: item.plot_area_sot, floor: item.floor,
    buildingFloors: item.building_floors, residentialComplex: item.residential_complex,
    price: item.price_kzt, district: item.district,
    address: item.address, preview: item.description_preview,
    seller: item.seller_type, city: item.city, posted: item.posted_label,
    floors: item.floors, yearBuilt: item.year_built,
    latitude: item.latitude, longitude: item.longitude,
    geoSource: item.geo_source, geoZoom: item.geo_zoom, geoType: item.geo_type,
    firstSeenAt: item.first_seen_at, lastSeenAt: item.last_seen_at,
    history: item.history || []
  };
}

function formatRunDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "дата неизвестна" : date.toLocaleString("ru-RU");
}

function renderRuns() {
  if (!isLocalHost) return;
  const labels = { running: "Выполняется", complete: "Пагинация завершена", limited: "Ограничен страницами",
    partial: "Прерван", blocked: "Доступ закрыт", cached: "Сохранённый снимок",
    failed: "Ошибка", imported: "Импорт" };
  const latest = state.runs[0];
  let stateTitle = "История сборов пока пуста";
  let summary = "Объекты в каталоге могут быть получены из прежних импортов.";
  if (latest) {
    const when = formatRunDate(latest.finished_at || latest.started_at);
    if (latest.status === "cached") {
      stateTitle = "Новая выдача не получена";
      summary = `Попытка ${when}${latest.source_status ? ` · HTTP ${latest.source_status}` : ""} · 0 новых страниц. Снимок от ${formatRunDate(latest.cached_at)}: ${latest.unique_ids} ${listingWord(latest.unique_ids)} в том запросе.`;
    } else if (latest.kind === "browser_import" || latest.status === "imported") {
      stateTitle = "Последнее действие — импорт";
      summary = `${when} · ${latest.unique_ids} ${listingWord(latest.unique_ids)} в том импорте.`;
    } else {
      stateTitle = latest.status === "complete" || latest.status === "limited" ? "Получена новая выдача" :
        latest.status === "running" ? "Сбор выполняется" : "Сбор не завершён";
      summary = `${when} · ${latest.pages} новых стр. · ${latest.unique_ids} ${listingWord(latest.unique_ids)} в том запросе${latest.source_status ? ` · HTTP ${latest.source_status}` : ""}.`;
    }
  }
  updateText("#run-state", stateTitle);
  updateText("#latest-run", summary);
  $("#run-list").innerHTML = state.runs.length ? state.runs.map((run) => {
    const request = run.request || {};
    const url = request.requested_url || request.source_url || request.search_url || request.file || "";
    const area = request.location_query ? `по названию: ${request.location_query}` : request.polygon ? "полигон" : request.bounds ? "прямоугольник" : "без области";
    const scope = run.kind === "html_import" || run.kind === "cli_import" ? "HTML-файл" : run.kind === "browser_import" ?
      `Данные браузера · пакет ${request.items || 0} ${listingWord(request.items || 0)}` : `${request.max_pages === 0 ? "все страницы" : `до ${request.max_pages || 1} стр.`} · ${area}`;
    const detail = [run.kind === "browser_import" ? null : run.status === "cached" ? "0 новых стр." : run.pages + " стр.",
      `${run.unique_ids} ${listingWord(run.unique_ids)}`, run.kind === "browser_import" ? null : run.with_coordinates + " с точкой",
      run.excluded_without_coordinates ? `${run.excluded_without_coordinates} без точки` : null,
      run.excluded_outside_area ? `${run.excluded_outside_area} вне области` : null,
      run.excluded_outside_location ? `${run.excluded_outside_location} другой адрес` : null,
      run.source_status ? `HTTP ${run.source_status}` : null].filter(Boolean).join(" · ");
    return `<div class="run-row"><div><strong>${escapeHtml(labels[run.status] || run.status)}</strong><time>${escapeHtml(formatRunDate(run.finished_at || run.started_at))}</time></div><p>${escapeHtml(scope)} · ${escapeHtml(detail)}</p>${run.cached_at ? `<p>Источник снимка: ${escapeHtml(formatRunDate(run.cached_at))}</p>` : ""}${url ? `<p class="run-url" title="${escapeHtml(url)}">${escapeHtml(url)}</p>` : ""}${run.error ? `<p class="run-error">${escapeHtml(run.error)}</p>` : ""}</div>`;
  }).join("") : "";
  animateChange($("#run-toolbar"));
}

async function refreshCatalog() {
  const response = await fetch("/api/catalog", { cache: "no-store" });
  if (!response.ok) throw new Error("База не ответила на запрос каталога.");
  const result = await response.json();
  state.runs = result.runs || [];
  save((result.listings || []).map(fromServer));
  renderRuns();
}

async function initializeLocalCatalog() {
  const legacy = legacyBrowserListings.filter((item) => !item.demo);
  let migrationError = null;
  try {
    if (legacy.length) {
      for (let start = 0; start < legacy.length; start += 100) {
        const response = await fetch("/api/migrate", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ listings: legacy.slice(start, start + 100) }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Не удалось перенести сохранённые в браузере карточки.");
      }
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch (error) {
    migrationError = error;
  }
  await refreshCatalog();
  if (migrationError) setStatus(`Каталог открыт из SQLite. Перенос прежних данных браузера не завершён: ${migrationError.message}`, true);
}

function buildCollectionRequest(selection) {
  const city = $("#live-city").value;
  const place = collectionMode === "text" ? $("#live-place").value.trim() : "";
  const known = collectionMode === "text" ? knownPlaceForText(city, place) : null;
  const alias = known?.alias || city;
  const custom = $("#live-search-url").value.trim();
  let url;
  if (custom) {
    try { url = new URL(custom); } catch { throw new Error("Ссылка на выдачу некорректна."); }
    if (url.protocol !== "https:" || !["krisha.kz", "www.krisha.kz"].includes(url.hostname) ||
      !/^\/prodazha\/(doma-dachi|kvartiry)(?:\/[a-z0-9-]+)?\/?$/.test(url.pathname)) {
      throw new Error("Нужна HTTPS-ссылка на выдачу домов или квартир Krisha.kz.");
    }
    for (const name of ["bounds", "areas", "lat", "lon", "zoom", "page"]) url.searchParams.delete(name);
  } else {
    const category = $("#live-category").value === "apartment" ? "kvartiry" : "doma-dachi";
    url = new URL(`https://krisha.kz/prodazha/${category}/`);
  }
  const category = url.pathname.split("/")[2];
  url.pathname = `/prodazha/${category}/${alias}/`;
  return {
    url: url.toString(),
    max_pages: Number($("#live-pages").value),
    bounds: selection?.kind === "rectangle" ? areaQuery(selection.bounds) : null,
    polygon: selection?.kind === "polygon" ? selection.vertices : null,
    location_query: place && !known ? place : null
  };
}

$("#collect-button").addEventListener("click", async () => {
  let selection;
  let request;
  try {
    selection = readAreaSelection();
    request = buildCollectionRequest(selection);
  } catch (error) { setStatus(error.message, true); return; }
  if (!liveEnabled) {
    const handoff = {
      category: $("#live-category").value, pages: Number($("#live-pages").value),
      city: $("#live-city").value, place: $("#live-place").value, collectionMode,
      url: $("#live-search-url").value.trim(), area: selection
    };
    window.location.assign(`http://127.0.0.1:8765/#collect=${encodeURIComponent(JSON.stringify(handoff))}`);
    return;
  }
  const button = $("#collect-button");
  button.disabled = true;
  button.textContent = "Собираю…";
  setStatus("Получаю страницы Krisha.kz. Это может занять до минуты.");
  try {
    const response = await fetch("/api/collect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request)
    });
    const result = await response.json();
    if (result.cached) {
      await refreshCatalog();
      const cachedAt = new Date(result.cached_at);
      const when = Number.isNaN(cachedAt.getTime()) ? "предыдущего сбора" : cachedAt.toLocaleString("ru-RU");
      const retryAt = result.next_retry_at ? new Date(result.next_retry_at) : null;
      const retryWhen = retryAt && !Number.isNaN(retryAt.getTime()) ? retryAt.toLocaleString("ru-RU") : "позже";
      const accessReason = result.source_status === 200 ? "страницы проверки доступа" : `HTTP ${result.source_status}`;
      const reason = result.code === "fresh_cache" ? "Недавний сбор с теми же параметрами уже сохранён." :
        result.code === "source_cooldown_cache" ? `После ${accessReason} запрос отложен до ${retryWhen}.` :
        result.source_status === 200 ? "Krisha.kz вернул страницу проверки доступа." : `Krisha.kz вернул ${accessReason}.`;
      setStatus(`${reason} Снимок от ${when}: ${result.unique_ids} ${listingWord(result.unique_ids)}. Новые объявления и цены не проверены.`, result.code !== "fresh_cache");
      return;
    }
    if (!response.ok) {
      await refreshCatalog();
      if (result.partial && result.listings?.length) {
        setStatus(`${result.error || "Сбор прерван."} До остановки собрано ${result.unique_ids} ${listingWord(result.unique_ids)} на ${result.pages} страницах. Выдача неполная; данные сохранены в SQLite.`, true);
        return;
      }
      if (result.code === "source_challenge") {
        setStatus(`${result.error} Ранее сохранённые карточки остаются в каталоге.`, true);
        return;
      }
      if (result.code === "source_cooldown") {
        const retryAt = new Date(result.next_retry_at);
        const retryWhen = Number.isNaN(retryAt.getTime()) ? "позже" : retryAt.toLocaleString("ru-RU");
        const accessReason = result.source_status === 200 ? "страницы проверки доступа" : `HTTP ${result.source_status}`;
        setStatus(`После ${accessReason} новый запрос отложен до ${retryWhen}. Сохранённые карточки остаются в каталоге.`, true);
        return;
      }
      throw new Error(result.error || "Не удалось собрать объявления.");
    }
    await refreshCatalog();
    const scope = result.bounds ? ` Вне области: ${result.excluded_outside_area ?? result.excluded_outside_bounds}; без координат: ${result.excluded_without_coordinates}.` :
      result.location_query ? ` По адресу не подошли: ${result.excluded_outside_location ?? 0}.` : "";
    const pagination = result.pagination_exhausted ? " Доступные страницы выдачи пройдены до конца." : " В выдаче есть следующая страница; выберите «Все страницы» для полного обхода.";
    const geoWarning = result.status === "partial" ? " Выборка по области неполная из-за ошибки карты." : "";
    setStatus(`Собрано ${result.unique_ids} ${listingWord(result.unique_ids)} на ${result.pages} ${result.pages === 1 ? "странице" : "страницах"}; с координатами — ${result.with_coordinates}.${scope}${pagination}${geoWarning} HTML и ответы карты сохранены локально.${result.geo_errors?.length ? ` Ошибки карты: ${result.geo_errors.join("; ")}` : ""}`, result.status === "partial");
  } catch (error) {
    setStatus(error.message || "Не удалось получить страницы.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Собрать объявления";
  }
});

restoreAreaSettings();
restoreCollectionHandoff();
updateLinkSummary();
showAreaMode();
showCollectionMode();
render();
enhanceSelectMenus();
