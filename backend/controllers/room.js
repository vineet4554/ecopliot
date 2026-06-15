const axios = require('axios');
const FormData = require('form-data');
const RoomAnalysis = require('../models/RoomAnalysis');

const scanRoomImage = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ detail: 'No room image file uploaded.' });
    }

    const userId = req.user._id;
    const roomType = req.body.room_type || 'living_room';
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8001';

    // 1. Forward to Python AI microservice
    const form = new FormData();
    form.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype
    });
    form.append('room_type', roomType);

    let aiResponse;
    try {
      aiResponse = await axios.post(`${aiServiceUrl}/ai/ocr/room`, form, {
        headers: {
          ...form.getHeaders()
        }
      });
    } catch (err) {
      console.error('Failed to analyze room snapshot on AI microservice:', err.message);
      return res.status(502).json({ detail: 'AI microservice is unavailable or returned an error.' });
    }

    const {
      detected_appliances,
      total_energy_waste_kwh,
      total_carbon_impact_kg,
      total_yearly_cost_usd,
      overall_room_eco_score,
      recommendations
    } = aiResponse.data;

    // 2. Save RoomAnalysis document
    const analysis = new RoomAnalysis({
      user_id: userId,
      image_url: req.file.originalname,
      room_type: roomType,
      detected_appliances,
      total_energy_waste_kwh,
      total_carbon_impact_kg,
      total_yearly_cost_usd,
      overall_room_eco_score,
      recommendations,
      analyzed_at: new Date()
    });

    const saved = await analysis.save();

    const resObj = saved.toObject();
    resObj._id = resObj._id.toString();
    resObj.user_id = resObj.user_id.toString();

    res.json(resObj);
  } catch (error) {
    console.error('Scan room image error:', error);
    res.status(500).json({ detail: 'Internal Server Error' });
  }
};

const listRoomScans = async (req, res) => {
  try {
    const userId = req.user._id;
    const list = await RoomAnalysis.find({ user_id: userId }).sort({ analyzed_at: -1 });

    const formatted = list.map(item => {
      const itemObj = item.toObject();
      itemObj._id = itemObj._id.toString();
      itemObj.user_id = itemObj.user_id.toString();
      return itemObj;
    });

    res.json(formatted);
  } catch (error) {
    console.error('List room scans error:', error);
    res.status(500).json({ detail: 'Internal Server Error' });
  }
};

module.exports = {
  scanRoomImage,
  listRoomScans
};
