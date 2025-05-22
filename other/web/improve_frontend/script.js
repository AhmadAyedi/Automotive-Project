document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const activateBtn = document.getElementById('activate-btn');
    const statusDiv = document.getElementById('status');
    const frontWiperBlade = document.getElementById('front-wiper-blade');
    const rearWiperBlade = document.getElementById('rear-wiper-blade');

    // Sensor elements
    const temperatureSpan = document.getElementById('temperature');
    const humiditySpan = document.getElementById('humidity');
    const sensorTimestampSpan = document.getElementById('sensor-timestamp');
    const refreshSensorBtn = document.getElementById('refresh-sensor-btn');

    // Initialize status panel
    updateStatus('ready', 'System ready for commands');

    // Function to update status panel
    function updateStatus(type, message) {
        const icon = statusDiv.querySelector('.status-icon');
        const text = statusDiv.querySelector('p');

        // Remove all existing classes
        icon.className = 'status-icon';
        statusDiv.className = 'status-content';

        // Add appropriate classes based on status type
        if (type === 'ready') {
            icon.classList.add('fas', 'fa-check-circle', 'ready');
            statusDiv.classList.add('ready');
        } else if (type === 'error') {
            icon.classList.add('fas', 'fa-exclamation-circle', 'error');
            statusDiv.classList.add('error');
        } else if (type === 'processing') {
            icon.classList.add('fas', 'fa-cog', 'processing', 'fa-spin');
            statusDiv.classList.add('processing');
        } else if (type === 'success') {
            icon.classList.add('fas', 'fa-check-circle', 'success');
            statusDiv.classList.add('success');
        }

        text.textContent = message;
    }

    // Function to fetch and display sensor data
    async function fetchSensorData() {
        updateStatus('processing', 'Fetching sensor data...');

        try {
            const response = await fetch('http://localhost:3001/api/sensor');
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();

            // Update temperature display with animation
            animateValueChange(temperatureSpan, data.temperature != null ? data.temperature : 'N/A', '°C');

            // Update humidity display with animation
            animateValueChange(humiditySpan, data.humidity != null ? data.humidity : 'N/A', '%');

            // Update timestamp
            if (data.timestamp) {
                sensorTimestampSpan.textContent = new Date(data.timestamp).toLocaleString();
            } else {
                sensorTimestampSpan.textContent = 'N/A';
            }

            updateStatus('ready', 'Sensor data updated successfully');

            // Visual feedback for successful update
            refreshSensorBtn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => {
                refreshSensorBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
            }, 2000);

        } catch (error) {
            console.error('Error fetching sensor data:', error);
            updateStatus('error', `Error fetching sensor data: ${error.message}`);

            // Update displays with error state
            temperatureSpan.textContent = 'N/A';
            humiditySpan.textContent = 'N/A';
            sensorTimestampSpan.textContent = 'N/A';

            // Visual feedback for error
            refreshSensorBtn.innerHTML = '<i class="fas fa-times"></i>';
            setTimeout(() => {
                refreshSensorBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
            }, 2000);
        }
    }

    // Helper function to animate value changes
    function animateValueChange(element, newValue, unit = '') {
        const oldValue = element.textContent;
        if (oldValue === newValue.toString()) return;

        element.style.transform = 'scale(1.2)';
        element.style.color = '#e74c3c';

        setTimeout(() => {
            element.textContent = newValue;
            element.style.transform = 'scale(1)';
            element.style.color = '';
        }, 300);
    }

    // Refresh sensor data button
    refreshSensorBtn.addEventListener('click', () => {
        refreshSensorBtn.classList.add('rotate');
        fetchSensorData();
        setTimeout(() => {
            refreshSensorBtn.classList.remove('rotate');
        }, 1000);
    });

    // Fetch sensor data every 10 seconds
    fetchSensorData();
    setInterval(fetchSensorData, 10000);

    // Function to simulate wiper movement
    function simulateWiper(wiperElement, cycles, speed) {
        // Clear any existing animations
        wiperElement.style.animation = 'none';
        void wiperElement.offsetWidth; // Trigger reflow

        // Set appropriate animation class based on speed
        const animationClass = speed === 'fast' ? 'wiper-fast' : 'wiper-active';
        wiperElement.classList.add(animationClass);

        // Stop animation after the specified number of cycles
        const animationDuration = speed === 'fast' ? 600 : 1000;
        const totalDuration = cycles * animationDuration;

        setTimeout(() => {
            wiperElement.classList.remove(animationClass);
        }, totalDuration);
    }

    activateBtn.addEventListener('click', async () => {
        const wiperType = document.querySelector('input[name="wiper"]:checked').value;
        const speed = document.querySelector('input[name="speed"]:checked').value;
        const cycles = parseInt(document.getElementById('cycles').value);

        // Update status to processing
        updateStatus('processing', 'Sending command to wiper system...');

        try {
            const response = await fetch('http://localhost:3001/api/commands', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    wiperType,
                    speed,
                    cycles
                })
            });

            const data = await response.json();

            // Update status to success
            updateStatus('success', `Command sent successfully! Wiper: ${wiperType}, Speed: ${speed}, Cycles: ${cycles}`);

            // Simulate the wiper movement in the UI
            if (wiperType === 'front' || wiperType === 'both') {
                simulateWiper(frontWiperBlade, cycles, speed);
            }
            if (wiperType === 'back' || wiperType === 'both') {
                simulateWiper(rearWiperBlade, cycles, speed);
            }

            // Add visual feedback to button
            activateBtn.innerHTML = '<i class="fas fa-check"></i> Command Sent!';
            activateBtn.style.backgroundColor = 'var(--success-color)';

            setTimeout(() => {
                activateBtn.innerHTML = '<i class="fas fa-play"></i> Activate Wipers';
                activateBtn.style.backgroundColor = 'var(--secondary-color)';
            }, 2000);

        } catch (error) {
            updateStatus('error', `Error: ${error.message}`);

            // Add visual feedback to button
            activateBtn.innerHTML = '<i class="fas fa-times"></i> Failed!';
            activateBtn.style.backgroundColor = 'var(--danger-color)';

            setTimeout(() => {
                activateBtn.innerHTML = '<i class="fas fa-play"></i> Activate Wipers';
                activateBtn.style.backgroundColor = 'var(--secondary-color)';
            }, 2000);
        }
    });
});