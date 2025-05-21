const mongoose = require('mongoose');

const commandSchema = new mongoose.Schema({
    protocol: { type: String, enum: ['CAN', 'LIN'], required: true },
    wiperType: { type: String, enum: ['front', 'back', 'both'], required: true },
    speed: { type: String, enum: ['normal', 'fast'], required: true },
    cycles: { type: Number, min: 1, max: 5, required: true },
    status: { type: String, enum: ['pending', 'completed', 'ignored'], default: 'pending' },
    timestamp: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Command', commandSchema);