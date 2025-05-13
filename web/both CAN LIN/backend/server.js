const express = require('express');
const mongoose = require('mongoose');
const bodyParser = require('body-parser');
const cors = require('cors');
const Command = require('./models/commands');
const Sensor = require('./models/sensor');

const app = express();
const PORT = 3001;

// Middleware
app.use(cors());
app.use(bodyParser.json());

// MongoDB connection
mongoose.connect('mongodb://192.168.1.14:27017/CAN_LIN_wiper777', {
    useNewUrlParser: true,
    useUnifiedTopology: true
});

const db = mongoose.connection;
db.on('error', console.error.bind(console, 'connection error:'));
db.once('open', () => {
    console.log('Connected to MongoDB');
});

// API Routes
app.post('/api/commands', async (req, res) => {
    try {
        const { protocol, wiperType, speed, cycles } = req.body;
        const newCommand = new Command({ protocol, wiperType, speed, cycles });
        await newCommand.save();
        res.status(201).json(newCommand);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/commands/pending', async (req, res) => {
    try {
        const commands = await Command.find({ status: 'pending' });
        res.json(commands);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.put('/api/commands/:id/complete', async (req, res) => {
    try {
        const command = await Command.findByIdAndUpdate(
            req.params.id,
            { status: 'completed' },
            { new: true }
        );
        res.json(command);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.post('/api/sensor', async (req, res) => {
    try {
        const { temperature, humidity } = req.body;
        const newSensorData = new Sensor({ temperature, humidity });
        await newSensorData.save();
        res.status(201).json(newSensorData);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/sensor', async (req, res) => {
    try {
        const latestData = await Sensor.findOne().sort({ timestamp: -1 });
        console.log('Latest sensor data:', latestData);
        res.json(latestData || { temperature: null, humidity: null });
    } catch (error) {
        console.error('Error fetching sensor data:', error);
        res.status(500).json({ error: error.message });
    }
});

// Start server
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});