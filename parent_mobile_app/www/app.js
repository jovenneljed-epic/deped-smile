// DepEd Project S.M.I.L.E. - Parent Mobile App Logic
const API_BASE = "https://deped-smile.vercel.app";
let currentLrn = localStorage.getItem("smile_parent_lrn") || "";
let pollTimer = null;
let lastScanId = null;

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  if (currentLrn) {
    showMainApp();
    loadDashboardData();
    startPolling();
  } else {
    showLoginView();
  }
});

function showLoginView() {
  document.getElementById("loginView").classList.remove("hidden");
  document.getElementById("mainAppViews").classList.add("hidden");
  document.getElementById("bottomNav").classList.add("hidden");
}

function showMainApp() {
  document.getElementById("loginView").classList.add("hidden");
  document.getElementById("mainAppViews").classList.remove("hidden");
  document.getElementById("bottomNav").classList.remove("hidden");
}

async function loginWithLrn() {
  const input = document.getElementById("inputLrn");
  const lrn = (input.value || "").trim();
  if (!lrn || lrn.length < 10) {
    alert("Please enter a valid 12-digit student LRN.");
    return;
  }

  currentLrn = lrn;
  localStorage.setItem("smile_parent_lrn", lrn);
  showMainApp();
  await loadDashboardData();
  startPolling();
}

function logoutMobile() {
  if (confirm("Disconnect and clear saved student LRN on this device?")) {
    localStorage.removeItem("smile_parent_lrn");
    currentLrn = "";
    if (pollTimer) clearInterval(pollTimer);
    showLoginView();
  }
}

// -------------------------------------------------------------
// Data Fetching & Dashboard Rendering
// -------------------------------------------------------------
async function loadDashboardData() {
  if (!currentLrn) return;

  try {
    const res = await fetch(`${API_BASE}/api/mobile/home/${currentLrn}`);
    if (!res.ok) throw new Error("Failed to load student data");
    const data = await res.json();
    if (!data.success) return;

    const s = data.student;
    document.getElementById("studentFullName").innerText = s.full_name;
    document.getElementById("studentGradeSection").innerText = s.grade_section;
    document.getElementById("studentLrnLabel").innerText = s.lrn;
    document.getElementById("todayDateLabel").innerText = data.today_date;

    if (s.photo_path) {
      document.getElementById("studentAvatar").innerHTML = `<img src="${API_BASE}${s.photo_path}" class="w-full h-full object-cover">`;
    }

    // Guardian Pass QR
    const qrImg = document.getElementById("passQrImg");
    if (qrImg) {
      qrImg.src = `${API_BASE}/static/qrcodes/${s.lrn}.png`;
    }

    // Presence Badge
    updatePresenceBadge(data.status, data.latest_log);

    // Featured Event
    if (data.featured_event) {
      const fe = data.featured_event;
      document.getElementById("featEventTitle").innerText = fe.title;
      document.getElementById("featEventDate").innerText = `${fe.short_month} ${fe.day_num}`;
      document.getElementById("featEventLoc").innerHTML = `<i class="fa-solid fa-location-dot text-rose-400 text-[10px]"></i> ${fe.location}`;
      document.getElementById("featuredEventBanner").classList.remove("hidden");
    } else {
      document.getElementById("featuredEventBanner").classList.add("hidden");
    }

    // Today's Timeline
    renderTimeline(data.today_logs);

    // Load sub-tabs in background
    loadNotifications();
    loadAnnouncements();
    loadEvents();
  } catch (err) {
    console.warn("Offline or load error:", err);
  }
}

function updatePresenceBadge(status, latestLog) {
  const badge = document.getElementById("statusBadge");
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");

  if (status === "INSIDE_CAMPUS") {
    badge.className = "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-black bg-emerald-100 text-emerald-900 border border-emerald-300";
    dot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse";
    text.innerText = `INSIDE CAMPUS (Since ${latestLog ? latestLog.time_formatted : 'Today'})`;
  } else if (status === "SAFELY_EXITED") {
    badge.className = "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-black bg-blue-100 text-blue-900 border border-blue-300";
    dot.className = "w-2.5 h-2.5 rounded-full bg-blue-500";
    text.innerText = `SAFELY EXITED (At ${latestLog ? latestLog.time_formatted : 'Today'})`;
  } else {
    badge.className = "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-black bg-slate-100 text-slate-600 border border-slate-200";
    dot.className = "w-2.5 h-2.5 rounded-full bg-slate-400";
    text.innerText = "AWAITING ARRIVAL AT GATE";
  }
}

function renderTimeline(logs) {
  const container = document.getElementById("timelineList");
  if (!container) return;

  if (!logs || logs.length === 0) {
    container.innerHTML = `
      <div class="p-6 text-center bg-white rounded-2xl border border-slate-200 text-slate-400 space-y-1">
        <i class="fa-solid fa-school text-2xl text-slate-300"></i>
        <p class="text-xs font-medium">No gate scans recorded yet today.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = logs.map(l => {
    const isEntry = (l.scan_type === "TIME_IN");
    return `
      <div class="p-3 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-xl ${isEntry ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-blue-50 text-blue-600 border border-blue-200'} flex items-center justify-center text-xs font-bold shrink-0">
            <i class="fa-solid ${isEntry ? 'fa-right-to-bracket' : 'fa-right-from-bracket'}"></i>
          </div>
          <div>
            <span class="text-xs font-black uppercase text-slate-800">${isEntry ? 'Entry (TIME-IN)' : 'Exit (TIME-OUT)'}</span>
            <p class="text-[10px] text-slate-400 font-mono">${l.timestamp}</p>
          </div>
        </div>
        <div class="text-right">
          <span class="text-xs font-black text-slate-700 block">${l.time_formatted}</span>
          <span class="text-[9px] text-emerald-600 font-bold"><i class="fa-solid fa-check"></i> Verified</span>
        </div>
      </div>
    `;
  }).join("");
}

// -------------------------------------------------------------
// Notifications Center
// -------------------------------------------------------------
async function loadNotifications() {
  if (!currentLrn) return;
  try {
    const res = await fetch(`${API_BASE}/api/mobile/notifications/${currentLrn}`);
    const data = await res.json();
    if (!data.success) return;

    const list = document.getElementById("notificationsList");
    if (!list) return;

    if (data.unread_count > 0) {
      const badge = document.getElementById("notifBadge");
      const navBadge = document.getElementById("navAlertBadge");
      [badge, navBadge].forEach(b => {
        if (b) {
          b.innerText = data.unread_count;
          b.classList.remove("hidden");
        }
      });
    }

    if (!data.notifications || data.notifications.length === 0) {
      list.innerHTML = `<div class="p-8 text-center bg-white rounded-2xl border border-slate-200 text-slate-400 text-xs">No alerts recorded yet.</div>`;
      return;
    }

    list.innerHTML = data.notifications.map(n => `
      <div class="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-start gap-3">
        <div class="w-8 h-8 rounded-xl bg-${n.color}-50 text-${n.color}-600 border border-${n.color}-200 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
          <i class="fa-solid ${n.icon}"></i>
        </div>
        <div class="flex-grow">
          <div class="flex items-center justify-between">
            <span class="text-xs font-black text-slate-900">${n.title}</span>
            <span class="text-[10px] text-slate-400 font-mono">${n.timestamp}</span>
          </div>
          <p class="text-xs text-slate-600 mt-0.5 leading-snug">${n.body}</p>
        </div>
      </div>
    `).join("");
  } catch (e) {
    console.warn("Notifications load error:", e);
  }
}

// -------------------------------------------------------------
// Announcements Feed
// -------------------------------------------------------------
async function loadAnnouncements() {
  try {
    const res = await fetch(`${API_BASE}/api/announcements`);
    const data = await res.json();
    if (!data.success) return;

    const container = document.getElementById("announcementsList");
    if (!container) return;

    container.innerHTML = (data.announcements || []).map(a => `
      <div class="announcement-item p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-1.5" data-cat="${a.category}">
        <div class="flex items-center justify-between">
          <span class="px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-blue-100 text-deped-blue">${a.category}</span>
          <span class="text-[10px] text-slate-400 font-mono">${a.date_formatted || a.created_at}</span>
        </div>
        <h4 class="text-xs font-black text-slate-900">${a.title}</h4>
        <p class="text-xs text-slate-600 leading-relaxed">${a.content}</p>
      </div>
    `).join("");
  } catch (e) {
    console.warn("Announcements load error:", e);
  }
}

function filterMobileAnnouncements(cat) {
  document.querySelectorAll(".ann-filter-btn").forEach(btn => {
    if (btn.getAttribute("data-category") === cat) {
      btn.className = "ann-filter-btn px-3 py-1 rounded-full text-xs font-bold bg-deped-blue text-white shrink-0 shadow-sm";
    } else {
      btn.className = "ann-filter-btn px-3 py-1 rounded-full text-xs font-bold bg-white text-slate-600 border border-slate-200 shrink-0";
    }
  });

  document.querySelectorAll(".announcement-item").forEach(card => {
    const c = card.getAttribute("data-cat");
    if (cat === "ALL" || c === cat) {
      card.classList.remove("hidden");
    } else {
      card.classList.add("hidden");
    }
  });
}

// -------------------------------------------------------------
// School Events & Calendar
// -------------------------------------------------------------
async function loadEvents() {
  try {
    const res = await fetch(`${API_BASE}/api/mobile/events`);
    const data = await res.json();
    if (!data.success) return;

    const container = document.getElementById("eventsList");
    if (!container) return;

    container.innerHTML = (data.events || []).map(ev => `
      <div class="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-2">
        <div class="flex items-start gap-3">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-b from-blue-600 to-indigo-700 text-white flex flex-col items-center justify-center p-1 shadow-sm shrink-0">
            <span class="text-[9px] font-black uppercase leading-none">${ev.short_month}</span>
            <span class="text-base font-black font-heading leading-tight">${ev.day_num}</span>
          </div>
          <div>
            <span class="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase bg-blue-100 text-blue-800">${ev.category}</span>
            <h4 class="text-xs font-black text-slate-900 mt-1">${ev.title}</h4>
          </div>
        </div>
        <p class="text-xs text-slate-600 leading-relaxed">${ev.description}</p>
        <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-600">
          <span class="truncate max-w-[200px]"><i class="fa-solid fa-location-dot text-rose-500 text-[10px]"></i> ${ev.location}</span>
          <button onclick="downloadIcsCalendar('${ev.title}', '${ev.description}', '${ev.event_date}', '${ev.location}')" class="px-2 py-1 rounded-lg bg-blue-50 text-deped-blue font-bold text-[10px] border border-blue-200">
            <i class="fa-solid fa-calendar-plus text-[9px]"></i> Add to Cal
          </button>
        </div>
      </div>
    `).join("");
  } catch (e) {
    console.warn("Events load error:", e);
  }
}

// -------------------------------------------------------------
// Real-time Polling & Push Alert Engine
// -------------------------------------------------------------
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (!currentLrn) return;
    try {
      const res = await fetch(`${API_BASE}/api/parent/poll/${currentLrn}?last_scan_id=${lastScanId || 0}`);
      const data = await res.json();
      if (data.has_update && data.latest_scan) {
        lastScanId = data.latest_scan.id;
        triggerGateAlert(data.latest_scan);
        loadDashboardData();
      }
    } catch (e) {}
  }, 8000);
}

function triggerGateAlert(scan) {
  testAppChime();
  const banner = document.getElementById("liveBanner");
  const title = document.getElementById("bannerTitle");
  const desc = document.getElementById("bannerDesc");

  title.innerText = scan.scan_type === "TIME_IN" ? "STUDENT ENTERED CAMPUS" : "STUDENT SAFELY EXITED";
  desc.innerText = `Verified at ${scan.time_formatted} (${scan.verification_method || 'AI Gate'}).`;
  banner.classList.remove("hidden");
  setTimeout(() => banner.classList.add("hidden"), 8000);
}

function testAppChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, now);
    osc.frequency.setValueAtTime(880.00, now + 0.15);
    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.7);
  } catch (e) {}
}

// -------------------------------------------------------------
// Navigation Tabs
// -------------------------------------------------------------
function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.className = "nav-btn relative flex flex-col items-center text-slate-400 hover:text-deped-blue flex-1 py-1 transition";
  });

  if (tabId === "home") {
    document.getElementById("tabHome").classList.remove("hidden");
    document.getElementById("navBtnHome").className = "nav-btn flex flex-col items-center text-deped-blue font-bold flex-1 py-1";
  } else if (tabId === "alerts") {
    document.getElementById("tabAlerts").classList.remove("hidden");
    document.getElementById("navBtnAlerts").className = "nav-btn relative flex flex-col items-center text-deped-blue font-bold flex-1 py-1";
    document.getElementById("notifBadge").classList.add("hidden");
    document.getElementById("navAlertBadge").classList.add("hidden");
  } else if (tabId === "advisories") {
    document.getElementById("tabAdvisories").classList.remove("hidden");
    document.getElementById("navBtnAdvisories").className = "nav-btn flex flex-col items-center text-deped-blue font-bold flex-1 py-1";
  } else if (tabId === "events") {
    document.getElementById("tabEvents").classList.remove("hidden");
    document.getElementById("navBtnEvents").className = "nav-btn flex flex-col items-center text-deped-blue font-bold flex-1 py-1";
  } else if (tabId === "profile") {
    document.getElementById("tabProfile").classList.remove("hidden");
    document.getElementById("navBtnProfile").className = "nav-btn flex flex-col items-center text-deped-blue font-bold flex-1 py-1";
  }
  window.scrollTo(0, 0);
}

function downloadIcsCalendar(title, desc, eventDate, location) {
  const dateStr = (eventDate || '').replace(/-/g, '');
  const icsContent = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//DepEd Project S.M.I.L.E.//Parent App//EN',
    'BEGIN:VEVENT',
    `SUMMARY:${(title || 'School Event').replace(/[\n\r]/g, ' ')}`,
    `DESCRIPTION:${(desc || '').replace(/[\n\r]/g, ' ')}`,
    `LOCATION:${(location || '').replace(/[\n\r]/g, ' ')}`,
    `DTSTART;VALUE=DATE:${dateStr}`,
    `DTEND;VALUE=DATE:${dateStr}`,
    'STATUS:CONFIRMED',
    'END:VEVENT',
    'END:VCALENDAR'
  ].join('\r\n');

  const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${(title || 'event').replace(/[^a-zA-Z0-9]/g, '_')}.ics`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
