(function() {
    "use strict";

    let currentPath = "";
    let currentTab = "ext";
    let currentMode = "both";
    let pollInterval = null;

    function showToast(message) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.style.display = "block";
        setTimeout(function() {
            toast.style.display = "none";
        }, 3000);
    }

    function setTab(tab, button) {
        currentTab = tab;
        document.querySelectorAll(".tab").forEach(function(t) {
            t.classList.remove("active");
        });
        button.classList.add("active");
        document.getElementById("ext-view").style.display = tab === "ext" ? "flex" : "none";
        document.getElementById("dmp-view").style.display = tab === "dmp" ? "flex" : "none";
    }

    function setMode(mode, button) {
        currentMode = mode;
        document.querySelectorAll(".mode-btn").forEach(function(b) {
            b.classList.remove("active");
        });
        button.classList.add("active");
    }

    function setFile(path) {
        currentPath = path;
        var name = path.split(/[\\/]/).pop();
        var targetId = currentTab === "ext" ? "ext-name" : "dmp-name";
        document.getElementById(targetId).textContent = name.toLowerCase();
        showToast("selected");
    }

    async function pickFile() {
        try {
            var path = await pywebview.api.pick();
            if (path) {
                setFile(path);
            }
        } catch (e) {
            showToast("api error");
        }
    }

    async function startJob(endpoint) {
        if (!currentPath) {
            showToast("no file");
            return;
        }
        try {
            var response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: currentPath, mode: currentMode })
            });
            var data = await response.json();
            showToast(data.ok ? "started" : "error");
        } catch (e) {
            showToast("network error");
        }
    }

    function updateProgress(data) {
        var barId = currentTab === "ext" ? "bar" : "dmp-bar";
        var statId = currentTab === "ext" ? "stat" : "dmp-stat";
        var percId = currentTab === "ext" ? "perc" : "dmp-perc";

        var bar = document.getElementById(barId);
        var stat = document.getElementById(statId);
        var perc = document.getElementById(percId);

        if (data.stat === "run") {
            var pct = Math.round((data.cur / data.tot) * 100) || 0;
            bar.style.width = pct + "%";
            perc.textContent = pct + "%";
            stat.textContent = data.msg;
        } else if (data.stat === "done") {
            bar.style.width = "100%";
            perc.textContent = "100%";
            stat.textContent = "finished";
        } else if (data.stat === "err") {
            stat.textContent = data.msg || "error";
        }
    }

    async function pollState() {
        try {
            var response = await fetch("/state");
            if (!response.ok) return;
            var data = await response.json();
            updateProgress(data);
        } catch (e) {}
    }

    function init() {
        document.getElementById("ext-zone").addEventListener("click", pickFile);
        document.getElementById("dmp-zone").addEventListener("click", pickFile);
        document.getElementById("run-reup").addEventListener("click", function() {
            startJob("/start");
        });
        document.getElementById("run-dump").addEventListener("click", function() {
            startJob("/dump");
        });

        document.querySelectorAll(".tab").forEach(function(tab) {
            tab.addEventListener("click", function() {
                setTab(tab.dataset.tab, tab);
            });
        });

        document.querySelectorAll(".mode-btn").forEach(function(btn) {
            btn.addEventListener("click", function() {
                setMode(btn.dataset.mode, btn);
            });
        });

        pollInterval = setInterval(pollState, 1000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
