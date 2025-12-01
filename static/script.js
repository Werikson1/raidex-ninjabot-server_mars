document.addEventListener('DOMContentLoaded', () => {
    const configForm = document.getElementById('configForm');
    const toggleBotBtn = document.getElementById('toggleBotBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const logContainer = document.getElementById('logContainer');
    const fleetGroupSelect = document.getElementById('FLEET_GROUP_NAME');
    const fleetGroupValueInput = document.getElementById('FLEET_GROUP_VALUE');

    let isRunning = false;

    const syncFleetValueFromSelect = () => {
        if (fleetGroupSelect && fleetGroupValueInput) {
            fleetGroupValueInput.value = fleetGroupSelect.value || '';
        }
    };

    async function populateFleetGroups(currentName, currentValue) {
        if (!fleetGroupSelect) return;
        try {
            const res = await fetch('/api/fleet/groups');
            const data = await res.json();
            const groups = data.groups || [];
            fleetGroupSelect.innerHTML = '';

            if (!groups.length) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No fleet groups found';
                fleetGroupSelect.appendChild(opt);
                syncFleetValueFromSelect();
                return;
            }

            groups.forEach((g) => {
                const opt = document.createElement('option');
                opt.value = g.value;
                opt.textContent = g.name;
                fleetGroupSelect.appendChild(opt);
            });

            let selectedValue = '';
            if (currentValue && groups.some((g) => g.value === currentValue)) {
                selectedValue = currentValue;
            } else if (currentName) {
                const match = groups.find((g) => g.name === currentName);
                if (match) selectedValue = match.value;
            }

            if (!selectedValue && groups.length) {
                selectedValue = groups[0].value;
            }

            if (selectedValue) {
                fleetGroupSelect.value = selectedValue;
            }

            syncFleetValueFromSelect();
        } catch (error) {
            console.error('Error loading fleet groups:', error);
        }
    }

    if (fleetGroupSelect) {
        fleetGroupSelect.addEventListener('change', syncFleetValueFromSelect);
    }

    // Load Config
    async function loadConfig() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();

            // Populate form
            for (const [key, value] of Object.entries(config)) {
                if (key === 'FLEET_GROUP_NAME' || key === 'FLEET_GROUP_VALUE') {
                    continue; // handled after options load
                }
                const input = document.getElementById(key);
                if (input) {
                    if (input.type === 'checkbox') {
                        input.checked = value;
                    } else {
                        input.value = value;
                    }
                }
            }

            if (fleetGroupSelect) {
                await populateFleetGroups(config.FLEET_GROUP_NAME, config.FLEET_GROUP_VALUE);
            }
        } catch (error) {
            console.error('Error loading config:', error);
        }
    }

    // Save Config
    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(configForm);
            const config = {};

            // Convert FormData to JSON object
            // Handle checkboxes specifically
            const checkboxes = configForm.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => {
                config[cb.id] = cb.checked;
            });

            // Handle other inputs
            const inputs = configForm.querySelectorAll('input:not([type="checkbox"]), select');
            inputs.forEach(input => {
                // Convert numbers
                if (input.type === 'number') {
                    config[input.id] = parseFloat(input.value);
                } else {
                    config[input.id] = input.value;
                }
            });

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(config)
                });

                if (response.ok) {
                    alert('Configuration saved!');
                } else {
                    alert('Error saving configuration');
                }
            } catch (error) {
                console.error('Error saving config:', error);
                alert('Error saving configuration');
            }
        });
    }

    // Toggle Bot
    if (toggleBotBtn) {
        toggleBotBtn.addEventListener('click', async () => {
            const endpoint = isRunning ? '/api/stop' : '/api/start';
            try {
                const response = await fetch(endpoint, { method: 'POST' });
                const data = await response.json();
                console.log(data);
                updateStatus(); // Immediate update
            } catch (error) {
                console.error('Error toggling bot:', error);
            }
        });
    }

    // Update Status & Logs
    async function updateStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            isRunning = data.running;

            // Update UI
            if (statusDot && statusText && toggleBotBtn) {
                if (isRunning) {
                    statusDot.classList.add('running');
                    statusText.textContent = 'Running';
                    toggleBotBtn.textContent = 'Stop';
                    toggleBotBtn.classList.add('btn-stop');
                    toggleBotBtn.classList.remove('btn-start');
                } else {
                    statusDot.classList.remove('running');
                    statusText.textContent = 'Stopped';
                    toggleBotBtn.textContent = 'Start';
                    toggleBotBtn.classList.add('btn-start');
                    toggleBotBtn.classList.remove('btn-stop');
                }
            }

            // Update Logs
            if (logContainer) {
                // Clear and rebuild (simple approach, can be optimized)
                logContainer.innerHTML = '';
                data.logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'log-entry';

                    // Parse timestamp if possible for styling
                    // Log format: [HH:MM:SS] Message
                    const match = log.match(/^\[(.*?)\] (.*)/);
                    if (match) {
                        div.innerHTML = `<span class="log-time">[${match[1]}]</span> ${match[2]}`;
                    } else {
                        div.textContent = log;
                    }

                    logContainer.appendChild(div);
                });

                // Scroll to bottom
                logContainer.scrollTop = logContainer.scrollHeight;
            }

        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }

    // Update Cooldowns
    async function updateCooldowns() {
        try {
            const response = await fetch('/api/cooldowns');
            const cooldowns = await response.json();
            const cooldownList = document.getElementById('cooldownList');
            const cooldownHoursInput = document.getElementById('COOLDOWN_HOURS');

            if (!cooldownList) return;

            const cooldownHours = cooldownHoursInput ? (parseFloat(cooldownHoursInput.value) || 1.0) : 1.0;
            const cooldownSeconds = cooldownHours * 3600;

            cooldownList.innerHTML = '';

            const entries = Object.entries(cooldowns);

            if (entries.length === 0) {
                cooldownList.innerHTML = '<div class="cooldown-empty">No active cooldowns</div>';
                return;
            }

            // Sort by remaining time (ascending)
            const now = Date.now() / 1000;
            const sortedEntries = entries.map(([key, sentTime]) => {
                const elapsed = now - sentTime;
                const remaining = Math.max(0, cooldownSeconds - elapsed);
                return { key, remaining };
            }).sort((a, b) => a.remaining - b.remaining);

            sortedEntries.forEach(item => {
                const div = document.createElement('div');
                div.className = 'cooldown-item';

                // Format time HH:MM:SS
                const h = Math.floor(item.remaining / 3600);
                const m = Math.floor((item.remaining % 3600) / 60);
                const s = Math.floor(item.remaining % 60);
                const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

                div.innerHTML = `
                    <span class="cooldown-coord">[${item.key}]</span>
                    <span class="cooldown-timer">${timeStr}</span>
                `;
                cooldownList.appendChild(div);
            });

        } catch (error) {
            console.error('Error fetching cooldowns:', error);
        }
    }

    // Initialize based on page
    if (configForm) {
        loadConfig();
        // Only update cooldowns on miner page
        updateCooldowns();
    setInterval(updateCooldowns, 2000);
    }

    // Empire Tab Logic
    const crawlerBtn = document.getElementById('crawlerBtn');
    const empireTable = document.getElementById('empireTable');
    const emptyState = document.getElementById('emptyState');

    function formatNumber(num) {
        if (!num) return '0';
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }

    // Configuration for table rows
    const tableConfig = [
        { type: 'header', label: 'Resources' },
        { type: 'data', label: 'Metal', category: 'resources', key: 'metal' },
        { type: 'data', label: 'Crystal', category: 'resources', key: 'crystal' },
        { type: 'data', label: 'Deuterium', category: 'resources', key: 'deuterium' },
        { type: 'data', label: 'Energy', category: 'resources', key: 'energy' },

        { type: 'header', label: 'Production (Hourly)' },
        { type: 'data', label: 'Metal', category: 'production', key: 'metal_hourly' },
        { type: 'data', label: 'Crystal', category: 'production', key: 'crystal_hourly' },
        { type: 'data', label: 'Deuterium', category: 'production', key: 'deuterium_hourly' },

        { type: 'header', label: 'Facilities' },
        { type: 'data', label: 'Robot Factory', category: 'facilities', key: 'robot_factory' },
        { type: 'data', label: 'Shipyard', category: 'facilities', key: 'shipyard' },
        { type: 'data', label: 'Research Lab', category: 'facilities', key: 'research_lab' },
        { type: 'data', label: 'Nanite Factory', category: 'facilities', key: 'nanite_factory' },
        { type: 'data', label: 'Missile Silo', category: 'facilities', key: 'missile_silo' },

        { type: 'header', label: 'Mines' },
        { type: 'data', label: 'Metal Mine', category: 'facilities', key: 'metal_mine' },
        { type: 'data', label: 'Crystal Mine', category: 'facilities', key: 'crystal_mine' },
        { type: 'data', label: 'Deuterium Refinery', category: 'facilities', key: 'deuterium_refinery' },
        { type: 'data', label: 'Solar Plant', category: 'facilities', key: 'solar_power_plant' },
        { type: 'data', label: 'Fusion Reactor', category: 'facilities', key: 'fusion_reactor' },

        { type: 'header', label: 'Ships' },
        { type: 'data', label: 'Small Cargo', category: 'ships', key: 'light_cargo' },
        { type: 'data', label: 'Large Cargo', category: 'ships', key: 'heavy_cargo' },
        { type: 'data', label: 'Light Fighter', category: 'ships', key: 'light_fighter' },
        { type: 'data', label: 'Heavy Fighter', category: 'ships', key: 'heavy_fighter' },
        { type: 'data', label: 'Cruiser', category: 'ships', key: 'cruiser' },
        { type: 'data', label: 'Battleship', category: 'ships', key: 'battleship' },
        { type: 'data', label: 'Colony Ship', category: 'ships', key: 'colony_ship' },
        { type: 'data', label: 'Recycler', category: 'ships', key: 'recycler' },
        { type: 'data', label: 'Espionage Probe', category: 'ships', key: 'spy_probe' },
        { type: 'data', label: 'Solar Satellite', category: 'ships', key: 'solar_satellite' },
        { type: 'data', label: 'Destroyer', category: 'ships', key: 'destroyer' },
        { type: 'data', label: 'Deathstar', category: 'ships', key: 'death_star' },
        { type: 'data', label: 'Battlecruiser', category: 'ships', key: 'battle_cruiser' },

        { type: 'header', label: 'Defense' },
        { type: 'data', label: 'Rocket Launcher', category: 'defense', key: 'missile_launcher' },
        { type: 'data', label: 'Light Laser', category: 'defense', key: 'light_laser_turret' },
        { type: 'data', label: 'Heavy Laser', category: 'defense', key: 'heavy_laser_turret' },
        { type: 'data', label: 'Gauss Cannon', category: 'defense', key: 'gauss_cannon' },
        { type: 'data', label: 'Ion Cannon', category: 'defense', key: 'ion_cannon' },
        { type: 'data', label: 'Plasma Turret', category: 'defense', key: 'plasma_cannon' },
        { type: 'data', label: 'Small Shield', category: 'defense', key: 'small_shield_dome' },
        { type: 'data', label: 'Large Shield', category: 'defense', key: 'large_shield_dome' },
    ];

    function renderEmpireTable(data) {
        console.log('Rendering Empire Table with data:', data);
        if (!data || !data.planets || data.planets.length === 0) {
            console.log('No planets found in data');
            if (empireTable) empireTable.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (empireTable) empireTable.style.display = 'table';
        if (emptyState) emptyState.style.display = 'none';

        const thead = empireTable.querySelector('thead');
        const tbody = empireTable.querySelector('tbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';

        // 1. Render Header Row (Planet Names)
        const headerRow = document.createElement('tr');
        // Corner cell
        const cornerTh = document.createElement('th');
        cornerTh.textContent = 'Crawl';
        headerRow.appendChild(cornerTh);

        data.planets.forEach(planet => {
            const th = document.createElement('th');
            th.innerHTML = `
                <span class="planet-header-name">${planet.name}</span>
                <span class="planet-header-coords">${planet.coords}</span>
            `;
            headerRow.appendChild(th);
        });

        // Total Header
        const totalTh = document.createElement('th');
        totalTh.innerHTML = '<span class="planet-header-name">Total</span>';
        headerRow.appendChild(totalTh);

        thead.appendChild(headerRow);

        // 2. Render Data Rows
        tableConfig.forEach(rowConfig => {
            const tr = document.createElement('tr');

            if (rowConfig.type === 'header') {
                tr.className = 'row-category';
                const td = document.createElement('td');
                td.textContent = rowConfig.label;
                td.colSpan = data.planets.length + 2; // Span all columns + Total + Label
                tr.appendChild(td);
            } else {
                // Label Cell
                const labelTd = document.createElement('td');
                labelTd.textContent = rowConfig.label;
                tr.appendChild(labelTd);

                let rowTotal = 0;

                // Planet Data Cells
                data.planets.forEach(planet => {
                    const td = document.createElement('td');
                    let value = 0;
                    let displayValue = '0';

                    if (planet[rowConfig.category] && planet[rowConfig.category][rowConfig.key]) {
                        // Remove dots for calculation if string
                        const rawVal = planet[rowConfig.category][rowConfig.key];
                        value = parseInt(rawVal.toString().replace(/\./g, '')) || 0;
                        displayValue = formatNumber(value);
                    }

                    td.textContent = displayValue;

                    // Accumulate total
                    rowTotal += value;

                    // Optional: Add class based on value > 0
                    if (value > 0) {
                        td.style.color = '#fff'; // Highlight non-zero
                    } else {
                        td.style.color = '#555'; // Dim zero
                    }

                    tr.appendChild(td);
                });

                // Total Cell
                const totalTd = document.createElement('td');
                totalTd.textContent = formatNumber(rowTotal);
                totalTd.style.fontWeight = 'bold';
                totalTd.style.color = '#4fc3f7';
                tr.appendChild(totalTd);
            }
            tbody.appendChild(tr);
        });
    }

    function loadEmpireData() {
        console.log('Loading Empire Data...');
        fetch('/api/empire/data')
            .then(response => response.json())
            .then(data => {
                console.log('Empire Data Loaded:', data);
                renderEmpireTable(data);
            })
            .catch(error => console.error('Error loading empire data:', error));
    }

    if (crawlerBtn) {
        crawlerBtn.addEventListener('click', function () {
            crawlerBtn.disabled = true;
            crawlerBtn.textContent = 'Crawling...';

            fetch('/api/empire/crawl', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    loadEmpireData(); // Reload data after crawl
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to start crawl');
                })
                .finally(() => {
                    crawlerBtn.disabled = false;
                    crawlerBtn.textContent = 'Run Crawler';
                });
        });
    }

    // Initial load
    if (document.getElementById('empireTable')) {
        loadEmpireData();
    }

    // Global updates (Status & Logs)
    updateStatus();
    setInterval(updateStatus, 2000);
});
