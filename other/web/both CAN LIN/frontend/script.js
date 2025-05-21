document.addEventListener('DOMContentLoaded', () => {
    const activateBtn = document.getElementById('activate-btn');
    const statusDiv = document.getElementById('status');

    // Front wiper LEDs
    const frontLeds = [
        document.getElementById('front-led-1'),
        document.getElementById('front-led-2'),
        document.getElementById('front-led-3')
    ];

    // Back wiper LEDs
    const backLeds = [
        document.getElementById('back-led-1'),
        document.getElementById('back-led-2'),
        document.getElementById('back-led-3')
    ];
    // Sensor-related elements
    const temperatureSpan = document.getElementById('temperature');
    const humiditySpan = document.getElementById('humidity');
    const sensorTimestampSpan = document.getElementById('sensor-timestamp');
    const refreshSensorBtn = document.getElementById('refresh-sensor-btn');

    // Function to fetch and display sensor data
    async function fetchSensorData() {
        try {
            const response = await fetch('http://localhost:3001/api/sensor');
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const data = await response.json();

            if (data.temperature != null) {
                temperatureSpan.textContent = data.temperature;
            } else {
                temperatureSpan.textContent = 'N/A';
            }
            if (data.humidity != null) {
                humiditySpan.textContent = data.humidity;
            } else {
                humiditySpan.textContent = 'N/A';
            }
            if (data.timestamp) {
                sensorTimestampSpan.textContent = new Date(data.timestamp).toLocaleString();
            } else {
                sensorTimestampSpan.textContent = 'N/A';
            }
        } catch (error) {
            console.error('Error fetching sensor data:', error);
            statusDiv.textContent = `Error fetching sensor data: ${error.message}`;
            statusDiv.style.color = 'red';
            temperatureSpan.textContent = 'N/A';
            humiditySpan.textContent = 'N/A';
            sensorTimestampSpan.textContent = 'N/A';
        }
    }

    // Refresh sensor data button
    refreshSensorBtn.addEventListener('click', fetchSensorData);

    // Fetch sensor data every 10 seconds
    fetchSensorData();
    setInterval(fetchSensorData, 10000);

    // Function to simulate wiper movement
    function simulateWiper(leds, cycles, speed) {
        const delay = speed === 'fast' ? 300 : 600; // ms between LED changes

        for (let i = 0; i < cycles; i++) {
            // Forward sweep (left to right)
            setTimeout(() => leds[0].classList.add('active'), i * (delay * 6));
            setTimeout(() => leds[1].classList.add('active'), i * (delay * 6) + delay);
            setTimeout(() => leds[2].classList.add('active'), i * (delay * 6) + delay * 2);

            // Backward sweep (right to left)
            setTimeout(() => leds[2].classList.remove('active'), i * (delay * 6) + delay * 3);
            setTimeout(() => leds[1].classList.remove('active'), i * (delay * 6) + delay * 4);
            setTimeout(() => leds[0].classList.remove('active'), i * (delay * 6) + delay * 5);
        }
    }

    // Function to clear all LED simulations
    function clearSimulation() {
        frontLeds.forEach(led => led.classList.remove('active'));
        backLeds.forEach(led => led.classList.remove('active'));
    }

    activateBtn.addEventListener('click', async () => {
        const protocol = document.querySelector('input[name="protocol"]:checked').value;
        const wiperType = document.querySelector('input[name="wiper"]:checked').value;
        const speed = document.querySelector('input[name="speed"]:checked').value;
        const cycles = parseInt(document.getElementById('cycles').value);

        // Clear any existing simulation
        clearSimulation();

        try {
            const response = await fetch('http://localhost:3001/api/commands', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    protocol,
                    wiperType,
                    speed,
                    cycles
                })
            });

            const data = await response.json();
            statusDiv.textContent = `Command sent successfully! Protocol: ${protocol}, Wiper: ${wiperType}, Speed: ${speed}, Cycles: ${cycles}`;
            statusDiv.style.color = 'green';

            // Simulate the wiper movement in the UI
            if (wiperType === 'front' || wiperType === 'both') {
                simulateWiper(frontLeds, cycles, speed);
            }
            if (wiperType === 'back' || wiperType === 'both') {
                simulateWiper(backLeds, cycles, speed);
            }

        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
            statusDiv.style.color = 'red';
        }
    });
});